"""
io/speaker.py — WAV バイト列を sounddevice で再生する。

VOICEVOX が返す WAV データをそのまま受け取って再生する。
再生中は is_playing フラグを立てて agent.py が検知できるようにする。
"""
from __future__ import annotations

import io
import logging
import threading
import time
from typing import Optional

import numpy as np
import sounddevice as sd  # type: ignore
import soundfile as sf  # type: ignore

logger = logging.getLogger(__name__)


class Speaker:
    """
    WAV 音声を再生するクラス。

    使い方:
        speaker = Speaker()
        speaker.play(wav_bytes)          # ブロッキング再生
        speaker.play_async(wav_bytes)    # 非同期再生（スレッド）
    """

    def __init__(self, device: Optional[int] = None) -> None:
        self._device = device
        self._lock = threading.Lock()
        self.is_playing: bool = False
        self.last_error: Optional[str] = None
        self.last_played_at: Optional[float] = None
        self.play_count: int = 0

    @property
    def device(self) -> Optional[int]:
        return self._device

    def play(self, wav_bytes: bytes) -> None:
        """WAV バイト列を同期再生する。完了するまでブロックする。"""
        with self._lock:
            self.is_playing = True
            try:
                buf = io.BytesIO(wav_bytes)
                data, samplerate = sf.read(buf, dtype="float32")
                sd.play(data, samplerate=samplerate, device=self._device)
                sd.wait()
                self.last_error = None
                self.last_played_at = time.time()
                self.play_count += 1
            except Exception as e:
                self.last_error = str(e)
                logger.error(f"音声再生エラー: {e}")
                raise
            finally:
                self.is_playing = False

    def play_async(self, wav_bytes: bytes) -> threading.Thread:
        """WAV バイト列をバックグラウンドスレッドで再生する。Thread を返す。"""
        t = threading.Thread(
            target=self.play, args=(wav_bytes,), daemon=True, name="speaker"
        )
        t.start()
        return t

    def stop(self) -> None:
        """再生を強制停止する。"""
        sd.stop()
        self.is_playing = False
