"""
io/mic.py — sounddevice によるマイク入力ストリーム管理。

VAD モジュールが消費するために PCM チャンクをキューに積む。
サンプルレート: 16000 Hz, モノラル, int16
"""
from __future__ import annotations

import asyncio
import logging
import queue
import threading
from typing import Optional

import numpy as np
import sounddevice as sd  # type: ignore

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000   # Silero VAD / STT backend が期待するサンプルレート
CHANNELS = 1
DTYPE = "int16"
CHUNK_MS = 30          # 1チャンク = 30ms（Silero VAD の最小単位に合わせる）
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_MS / 1000)   # = 480


class MicStream:
    """
    マイク入力を管理するクラス。

    active == True の間だけキューにデータを積む。
    agent.py が SPEAKING 中は active = False に設定することでマイクを実質停止できる。

    使い方:
        mic = MicStream()
        mic.start()
        mic.active = True

        chunk = mic.queue.get()   # bytes (int16 little-endian)
        mic.stop()
    """

    def __init__(self, device: Optional[int] = None) -> None:
        self._device = device
        self.queue: queue.Queue[bytes] = queue.Queue(maxsize=500)
        self.active: bool = False
        self._stream: Optional[sd.InputStream] = None

    # ---- public API ----

    def start(self) -> None:
        """sounddevice ストリームを起動する。"""
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=CHUNK_SAMPLES,
            device=self._device,
            callback=self._callback,
        )
        self._stream.start()
        logger.info(f"マイクストリーム開始: {SAMPLE_RATE}Hz, {CHUNK_MS}ms チャンク")

    def stop(self) -> None:
        """ストリームを停止して後片付けする。"""
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        logger.info("マイクストリーム停止")

    def flush(self) -> None:
        """キューに溜まったデータを捨てる（SPEAKING 終了後のエコー除去用）。"""
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break

    # ---- internal ----

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info,
        status,
    ) -> None:
        if status:
            logger.debug(f"sounddevice status: {status}")
        if self.active:
            try:
                self.queue.put_nowait(indata.tobytes())
            except queue.Full:
                pass  # バッファ溢れは無視（リアルタイム優先）
