"""
utils/logging.py — 構造化ログ（rich）と会話ログ（テキスト永続化）を提供する。

会話ログ形式:
  [YYYY-MM-DD HH:MM:SS] WAKE
  [YYYY-MM-DD HH:MM:SS] USER : テキスト
  [YYYY-MM-DD HH:MM:SS] IMAGE: frame_001.jpg (WxH, saved)   # save_frames=True 時
  [YYYY-MM-DD HH:MM:SS] BOT  : テキスト
  [YYYY-MM-DD HH:MM:SS] LATENCY: stt=Xms llm=Xms tts=Xms total=Xms
  ---
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

# ---------------------------------------------------------------------------
# グローバル rich コンソール
# ---------------------------------------------------------------------------
console = Console(stderr=True)


def setup_logging(level: str = "INFO") -> None:
    """rich ベースのロギングを初期化する。アプリ起動時に一度だけ呼ぶ。"""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


# ---------------------------------------------------------------------------
# 会話ロガー
# ---------------------------------------------------------------------------

class ConversationLogger:
    """日付ごとのテキストファイルにターンを追記する。"""

    def __init__(self, log_dir: str = "./logs", save_frames: bool = False) -> None:
        self._dir = Path(log_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._save_frames = save_frames
        self._frame_counter: int = 0

    # ---- internal ----

    def _log_path(self) -> Path:
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self._dir / f"{date_str}.txt"

    def _ts(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _write(self, line: str) -> None:
        with self._log_path().open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    # ---- public API ----

    def log_wake(self) -> None:
        self._write(f"[{self._ts()}] WAKE")

    def log_user(self, text: str) -> None:
        self._write(f"[{self._ts()}] USER : {text}")

    def log_image(
        self,
        frame,  # np.ndarray | None
        width: int = 0,
        height: int = 0,
    ) -> Optional[Path]:
        """フレームを保存してログに記録する。save_frames=False なら記録のみ。"""
        self._frame_counter += 1
        label = f"frame_{self._frame_counter:04d}.jpg"
        saved_path: Optional[Path] = None

        if self._save_frames and frame is not None:
            import cv2  # type: ignore
            import numpy as np

            frame_dir = self._dir / "frames" / datetime.now().strftime("%Y-%m-%d")
            frame_dir.mkdir(parents=True, exist_ok=True)
            saved_path = frame_dir / label
            h, w = frame.shape[:2]
            cv2.imwrite(str(saved_path), frame)
            self._write(f"[{self._ts()}] IMAGE: {label} ({w}x{h}, saved)")
        else:
            self._write(f"[{self._ts()}] IMAGE: {label} ({width}x{height}, not saved)")

        return saved_path

    def log_bot(self, text: str) -> None:
        self._write(f"[{self._ts()}] BOT  : {text}")

    def log_latency(self, stt_ms: int, llm_ms: int, tts_ms: int) -> None:
        total = stt_ms + llm_ms + tts_ms
        self._write(
            f"[{self._ts()}] LATENCY: stt={stt_ms}ms llm={llm_ms}ms "
            f"tts={tts_ms}ms total={total}ms"
        )
        self._write("---")

    def log_error(self, message: str) -> None:
        self._write(f"[{self._ts()}] ERROR: {message}")
        self._write("---")
