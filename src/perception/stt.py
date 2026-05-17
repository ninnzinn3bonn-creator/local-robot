"""
perception/stt.py — faster-whisper を使った音声文字起こし（STT）。

入力: float32 ndarray (16kHz, mono)
出力: str（日本語テキスト）
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class WhisperSTT:
    """
    faster-whisper ラッパ。

    使い方:
        stt = WhisperSTT(model="large-v3", compute_type="int8_float16", language="ja")
        stt.load(device="cuda")
        text = stt.transcribe(audio_array)
    """

    def __init__(
        self,
        model: str = "large-v3",
        compute_type: str = "int8_float16",
        language: str = "ja",
        local_files_only: bool = True,
        download_root: Optional[str] = None,
    ) -> None:
        self._model_size = model
        self._compute_type = compute_type
        self._language = language
        self._local_files_only = local_files_only
        self._download_root = download_root
        self._model = None

    def load(self, device: str = "cuda") -> None:
        """モデルをロードする。標準ではローカルキャッシュのみを使う。"""
        from faster_whisper import WhisperModel  # type: ignore

        logger.info(f"faster-whisper '{self._model_size}' をロード中 ({device}, {self._compute_type})...")
        self._model = WhisperModel(
            self._model_size,
            device=device,
            compute_type=self._compute_type,
            download_root=self._download_root,
            local_files_only=self._local_files_only,
        )
        logger.info("faster-whisper ロード完了")

    def transcribe(self, audio: np.ndarray) -> str:
        """
        float32 音声配列を文字起こしして結合テキストを返す。
        空音声や低品質音声の場合は空文字列を返す。
        """
        if self._model is None:
            raise RuntimeError("WhisperSTT.load() を先に呼んでください")
        if len(audio) < 16_000 * 0.4:
            return ""

        segments, info = self._model.transcribe(
            audio,
            language=self._language,
            beam_size=5,
            vad_filter=False,   # VAD は外部で実施済み
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            log_prob_threshold=-1.0,
        )

        texts = [seg.text.strip() for seg in segments]
        result = "".join(texts).strip()
        logger.debug(f"STT: {result!r} (lang={info.language}, prob={info.language_probability:.2f})")
        return result

    @property
    def is_loaded(self) -> bool:
        return self._model is not None
