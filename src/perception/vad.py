"""
perception/vad.py — Silero VAD を使った発話区間検出。

入力: MicStream.queue から取り出した PCM bytes (int16, 16kHz, mono)
出力: 発話区間と判定されたチャンクを結合した np.ndarray (float32)

アルゴリズム:
  1. 30ms チャンクを順次 VAD にかける
  2. speech 確率が threshold 以上 → 発話中フラグ ON
  3. 発話中フラグ ON → チャンクを蓄積
  4. 無音が min_silence_ms 継続 → 発話終了 → 蓄積チャンクを返す
"""
from __future__ import annotations

import logging
import queue
import time
from typing import Iterator, Optional

import numpy as np
import torch  # type: ignore

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
CHUNK_MS = 30
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_MS / 1000)   # 480


class SileroVAD:
    """
    Silero VAD ラッパ。

    使い方:
        vad = SileroVAD(threshold=0.5, min_speech_ms=300, min_silence_ms=600)
        vad.load()

        for audio in vad.iter_utterances(mic_queue):
            # audio: float32 ndarray (16kHz)
            ...
    """

    def __init__(
        self,
        threshold: float = 0.5,
        min_speech_ms: int = 300,
        min_silence_ms: int = 600,
    ) -> None:
        self._threshold = threshold
        self._min_speech_samples = int(SAMPLE_RATE * min_speech_ms / 1000)
        self._min_silence_chunks = max(1, min_silence_ms // CHUNK_MS)
        self._model = None
        self._utils = None

    def load(self) -> None:
        """モデルをロードする。初回はダウンロードが走る（数MB、CPU動作）。"""
        logger.info("Silero VAD をロード中...")
        model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            trust_repo=True,
        )
        self._model = model
        self._utils = utils
        logger.info("Silero VAD ロード完了")

    def _prob(self, chunk_bytes: bytes) -> float:
        """30ms チャンクの発話確率を返す。"""
        arr = np.frombuffer(chunk_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        tensor = torch.from_numpy(arr)
        with torch.no_grad():
            prob = self._model(tensor, SAMPLE_RATE).item()
        return prob

    def iter_utterances(
        self, audio_queue: queue.Queue, stop_flag_fn=None
    ) -> Iterator[np.ndarray]:
        """
        音声キューから発話区間を検出して yield する（ブロッキングイテレータ）。

        stop_flag_fn: 呼び出すと True を返す場合にループを終了する関数（任意）
        """
        if self._model is None:
            raise RuntimeError("SileroVAD.load() を先に呼んでください")

        buffer: list[bytes] = []
        silence_count = 0
        in_speech = False

        while True:
            if stop_flag_fn and stop_flag_fn():
                break
            try:
                chunk = audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            prob = self._prob(chunk)

            if prob >= self._threshold:
                in_speech = True
                silence_count = 0
                buffer.append(chunk)
            elif in_speech:
                buffer.append(chunk)
                silence_count += 1
                if silence_count >= self._min_silence_chunks:
                    # 発話終了
                    raw = b"".join(buffer)
                    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                    if len(audio) >= self._min_speech_samples:
                        yield audio
                    buffer = []
                    silence_count = 0
                    in_speech = False
