"""
perception/simple_vad.py - Lightweight energy-based VAD.

This keeps the default Ollama route free of PyTorch. Silero remains available
for higher-quality segmentation when torch is installed.
"""
from __future__ import annotations

import logging
import queue
from typing import Iterator

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
CHUNK_MS = 30
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_MS / 1000)


class EnergyVAD:
    """Small VAD based on RMS energy and silence timeout."""

    def __init__(
        self,
        threshold: float = 0.012,
        min_speech_ms: int = 300,
        min_silence_ms: int = 600,
        max_speech_ms: int = 15_000,
    ) -> None:
        self._threshold = threshold
        self._min_speech_samples = int(SAMPLE_RATE * min_speech_ms / 1000)
        self._min_silence_chunks = max(1, min_silence_ms // CHUNK_MS)
        self._max_chunks = max(1, max_speech_ms // CHUNK_MS)

    def load(self) -> None:
        logger.info("Energy VAD を使用します")

    def iter_utterances(
        self,
        audio_queue: queue.Queue,
        stop_flag_fn=None,
    ) -> Iterator[np.ndarray]:
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

            audio = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
            rms = float(np.sqrt(np.mean(np.square(audio)))) if len(audio) else 0.0

            if rms >= self._threshold:
                in_speech = True
                silence_count = 0
                buffer.append(chunk)
            elif in_speech:
                buffer.append(chunk)
                silence_count += 1

            if in_speech and (
                silence_count >= self._min_silence_chunks
                or len(buffer) >= self._max_chunks
            ):
                raw = b"".join(buffer)
                utterance = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                if len(utterance) >= self._min_speech_samples:
                    yield utterance
                buffer = []
                silence_count = 0
                in_speech = False

