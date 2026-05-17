"""
reasoning/base.py - Shared interfaces for multimodal reasoning backends.
"""
from __future__ import annotations

from typing import Optional, Protocol

import numpy as np


class MultimodalLLM(Protocol):
    """Common surface used by the agent and benchmark scripts."""

    def load(self, device: str = "cuda:0") -> None:
        """Load model weights and processors."""

    def generate(
        self,
        messages: list[dict],
        image: Optional[np.ndarray] = None,
    ) -> str:
        """Generate assistant text from chat messages and an optional BGR image."""

    @property
    def is_loaded(self) -> bool:
        """Whether the backend has already loaded its model."""


class AudioTranscriber(Protocol):
    """Optional protocol implemented by LLMs that can do ASR."""

    def transcribe(
        self,
        audio: np.ndarray,
        language: str = "ja",
        sample_rate: int = 16_000,
    ) -> str:
        """Transcribe a mono float32 waveform."""

