"""
reasoning/gemma.py - Gemma 4 multimodal backend.

This backend follows the Hugging Face Transformers path from Google's Gemma
docs. It supports image+text generation and an experimental ASR path for the
E2B/E4B models that accept audio input.
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np

from src.reasoning.llm import ACCELERATE_DEVICE_MAP_PRESETS

logger = logging.getLogger(__name__)


LANGUAGE_LABELS = {
    "ja": "Japanese",
    "jp": "Japanese",
    "japanese": "Japanese",
    "en": "English",
    "english": "English",
}


def _device_map_for(device: str):
    return device if device in ACCELERATE_DEVICE_MAP_PRESETS else {"": device}


def _clean_response(text: str) -> str:
    return text.strip()


class GemmaMultimodalLLM:
    """
    Gemma 4 multimodal inference wrapper.

    Recommended model IDs:
      - google/gemma-4-E4B-it
      - google/gemma-4-E2B-it

    `quantization="bnb4"` uses bitsandbytes 4-bit NF4 for the Transformers
    runtime. Google's Q4_0 memory figures refer to GGUF runtimes such as
    llama.cpp/Ollama and are intentionally not accepted here.
    """

    def __init__(
        self,
        model_id: str = "google/gemma-4-E4B-it",
        quantization: str = "bnb4",
        max_new_tokens: int = 256,
        system_prompt: str = "あなたはカメラ映像を見ながら会話する日本語アシスタントです。",
        dtype: str = "auto",
    ) -> None:
        self._model_id = model_id
        self._quantization = quantization.lower()
        self._max_new_tokens = max_new_tokens
        self._system_prompt = system_prompt
        self._dtype = dtype
        self._model = None
        self._processor = None

    def load(self, device: str = "cuda:0") -> None:
        """Load Gemma 4 model and processor."""
        import torch  # type: ignore
        from transformers import AutoProcessor, BitsAndBytesConfig  # type: ignore

        try:
            from transformers import AutoModelForMultimodalLM  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Gemma 4 requires a recent transformers release with "
                "AutoModelForMultimodalLM support."
            ) from exc

        logger.info(f"Gemma 4 '{self._model_id}' をロード中...")

        kwargs = {
            "device_map": _device_map_for(device),
            "dtype": self._dtype,
        }

        if self._quantization in {"bnb4", "4bit", "nf4"}:
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.float16,
            )
        elif self._quantization in {"bnb8", "8bit"}:
            kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
        elif self._quantization in {"none", "auto", ""}:
            pass
        elif self._quantization == "q4_0":
            raise ValueError(
                "quantization='q4_0' is for GGUF runtimes. Use 'bnb4' for "
                "Transformers, or run Gemma through llama.cpp/Ollama instead."
            )
        else:
            raise ValueError(f"Unsupported Gemma quantization: {self._quantization}")

        self._model = AutoModelForMultimodalLM.from_pretrained(
            self._model_id,
            **kwargs,
        )
        self._model.eval()
        self._processor = AutoProcessor.from_pretrained(self._model_id)

        logger.info("Gemma 4 ロード完了")

    def generate(
        self,
        messages: list[dict],
        image: Optional[np.ndarray] = None,
    ) -> str:
        """Generate assistant text from chat messages and an optional BGR image."""
        if image is None:
            return self._run_messages(self._with_system(messages))

        import cv2  # type: ignore
        from PIL import Image  # type: ignore

        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        full_messages = self._with_system(messages)
        self._inject_image_into_last_user_message(full_messages, pil_img)
        return self._run_messages(full_messages)

    def transcribe(
        self,
        audio: np.ndarray,
        language: str = "ja",
        sample_rate: int = 16_000,
    ) -> str:
        """
        Experimental Gemma ASR path.

        Gemma 4 audio input accepts short clips. The current agent still uses
        VAD to cut speech first, then sends the clipped waveform here.
        """
        language_label = LANGUAGE_LABELS.get(language.lower(), language)
        prompt = (
            f"Transcribe the following speech segment in {language_label} into "
            f"{language_label} text. Only output the transcription, with no newlines."
        )

        audio_path = self._write_temp_wav(audio, sample_rate)
        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "audio", "audio": str(audio_path)},
                    ],
                }
            ]
            return self._run_messages(messages, max_new_tokens=96)
        finally:
            try:
                audio_path.unlink(missing_ok=True)
            except Exception:
                logger.debug("一時音声ファイルの削除に失敗しました", exc_info=True)

    def _run_messages(
        self,
        messages: list[dict],
        max_new_tokens: Optional[int] = None,
    ) -> str:
        if self._model is None or self._processor is None:
            raise RuntimeError("GemmaMultimodalLLM.load() を先に呼んでください")

        import torch  # type: ignore

        inputs = self._processor.apply_chat_template(
            messages,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
            add_generation_prompt=True,
        )
        inputs = inputs.to(self._model_device())

        with torch.no_grad():
            output_ids = self._model.generate(
                **inputs,
                max_new_tokens=max_new_tokens or self._max_new_tokens,
                do_sample=False,
            )

        input_len = inputs["input_ids"].shape[-1]
        generated = output_ids[:, input_len:]
        response = self._processor.batch_decode(
            generated,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0]

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        cleaned = _clean_response(response)
        logger.debug(f"Gemma 応答: {cleaned[:80]!r}...")
        return cleaned

    def _with_system(self, messages: list[dict]) -> list[dict]:
        full_messages: list[dict] = []
        if self._system_prompt:
            full_messages.append({"role": "system", "content": self._system_prompt})
        full_messages.extend({"role": m["role"], "content": m["content"]} for m in messages)
        return full_messages

    @staticmethod
    def _inject_image_into_last_user_message(messages: list[dict], image) -> None:
        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] != "user":
                continue
            content = messages[i]["content"]
            if isinstance(content, str):
                messages[i]["content"] = [
                    {"type": "image", "image": image},
                    {"type": "text", "text": content},
                ]
            elif isinstance(content, list):
                messages[i]["content"] = [{"type": "image", "image": image}, *content]
            return

    @staticmethod
    def _write_temp_wav(audio: np.ndarray, sample_rate: int) -> Path:
        import soundfile as sf  # type: ignore

        audio = np.asarray(audio, dtype=np.float32)
        handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        path = Path(handle.name)
        handle.close()
        sf.write(path, audio, sample_rate)
        return path

    def _model_device(self):
        device = getattr(self._model, "device", None)
        if device is not None:
            return device
        return next(self._model.parameters()).device

    @property
    def is_loaded(self) -> bool:
        return self._model is not None
