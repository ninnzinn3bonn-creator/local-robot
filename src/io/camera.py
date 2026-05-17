"""
io/camera.py — OpenCV による Webカメラキャプチャとスレッドセーフなフレームバッファ。

設計:
  - バックグラウンドスレッドが指定 FPS でフレームを取得し続ける
  - 常に最新フレームのみ保持（リングバッファではなく上書き）
  - agent.py は get_latest() でいつでも最新フレームを取得できる
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import cv2  # type: ignore
import numpy as np

logger = logging.getLogger(__name__)

# LLM 入力前のリサイズ上限（長辺 px）
RESIZE_LONG_EDGE = 768


def resize_for_llm(frame: np.ndarray) -> np.ndarray:
    """長辺が RESIZE_LONG_EDGE を超える場合にアスペクト比を保ってリサイズする。"""
    h, w = frame.shape[:2]
    long_edge = max(h, w)
    if long_edge <= RESIZE_LONG_EDGE:
        return frame
    scale = RESIZE_LONG_EDGE / long_edge
    new_w = int(w * scale)
    new_h = int(h * scale)
    return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)


class FrameBuffer:
    """スレッドセーフな最新フレーム保持バッファ。"""

    def __init__(self) -> None:
        self._frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()

    def put(self, frame: np.ndarray) -> None:
        with self._lock:
            self._frame = frame

    def get_latest(self) -> Optional[np.ndarray]:
        with self._lock:
            return self._frame.copy() if self._frame is not None else None


class CameraCapture:
    """
    Webカメラキャプチャを管理するクラス。

    使い方:
        cam = CameraCapture(index=0, width=1280, height=720, capture_fps=2)
        cam.start()
        frame = cam.get_latest()   # np.ndarray (BGR) or None
        cam.stop()
    """

    def __init__(
        self,
        index: int = 0,
        width: int = 1280,
        height: int = 720,
        capture_fps: int = 2,
    ) -> None:
        self._index = index
        self._width = width
        self._height = height
        self._interval = 1.0 / max(capture_fps, 1)
        self._buffer = FrameBuffer()
        self._cap: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # ---- public API ----

    def start(self) -> None:
        """キャプチャスレッドを起動する。"""
        if self._thread and self._thread.is_alive():
            logger.warning("CameraCapture はすでに起動中です")
            return
        self._stop_event.clear()
        self._cap = cv2.VideoCapture(self._index, cv2.CAP_DSHOW)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        if not self._cap.isOpened():
            raise RuntimeError(f"カメラ index={self._index} を開けませんでした")
        self._thread = threading.Thread(target=self._loop, daemon=True, name="camera")
        self._thread.start()
        logger.info(f"カメラ起動: index={self._index}, {self._width}x{self._height}")

    def stop(self) -> None:
        """キャプチャスレッドを停止する。"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
        if self._cap:
            self._cap.release()
            self._cap = None
        logger.info("カメラ停止")

    def get_latest(self) -> Optional[np.ndarray]:
        """最新フレーム（BGR ndarray）を返す。未取得の場合は None。"""
        return self._buffer.get_latest()

    def get_latest_for_llm(self) -> Optional[np.ndarray]:
        """LLM 入力用にリサイズした最新フレームを返す。"""
        frame = self.get_latest()
        if frame is None:
            return None
        return resize_for_llm(frame)

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ---- internal ----

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            t0 = time.monotonic()
            if self._cap and self._cap.isOpened():
                ret, frame = self._cap.read()
                if ret and frame is not None:
                    self._buffer.put(frame)
                else:
                    logger.warning("フレーム取得失敗")
            elapsed = time.monotonic() - t0
            wait = self._interval - elapsed
            if wait > 0:
                time.sleep(wait)
