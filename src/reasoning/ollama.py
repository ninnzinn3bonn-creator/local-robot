"""
reasoning/ollama.py - Ollama multimodal backend.

This path is the fastest way to run local vision models on this PC because
Ollama is already installed and manages GPU execution and GGUF quantization.
"""
from __future__ import annotations

import base64
import logging
from typing import Optional

import httpx
import numpy as np

logger = logging.getLogger(__name__)


class OllamaMultimodalLLM:
    """Ollama `/api/chat` backend with optional image input."""

    def __init__(
        self,
        model_id: str = "gemma3:4b",
        chat_model_id: Optional[str] = None,
        vision_model_id: Optional[str] = None,
        endpoint: str = "http://127.0.0.1:11434",
        max_new_tokens: int = 256,
        system_prompt: str = "あなたはカメラ映像を見ながら会話する日本語アシスタントです。",
        timeout: float = 300.0,
    ) -> None:
        self._model_id = model_id
        self._chat_model_id = chat_model_id
        self._vision_model_id = vision_model_id
        self._endpoint = endpoint.rstrip("/")
        self._max_new_tokens = max_new_tokens
        self._system_prompt = system_prompt
        self._timeout = timeout
        self._client: Optional[httpx.Client] = None
        self._loaded = False

    def load(self, device: str = "cuda:0") -> None:
        """Check Ollama availability and warm up the selected model."""
        self._client = httpx.Client(timeout=self._timeout)
        try:
            response = self._client.get(f"{self._endpoint}/api/tags")
            response.raise_for_status()
        except Exception as exc:
            raise RuntimeError(
                f"Ollama server is not available at {self._endpoint}."
            ) from exc

        for model in self._configured_models():
            logger.info(f"Ollama model '{model}' をウォームアップ中...")
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "準備できていますか？"}],
                "stream": False,
                "options": {"num_predict": 8},
            }
            response = self._client.post(f"{self._endpoint}/api/chat", json=payload)
            response.raise_for_status()
        self._loaded = True
        logger.info("Ollama backend 起動完了")

    def generate(
        self,
        messages: list[dict],
        image: Optional[np.ndarray] = None,
    ) -> str:
        if self._client is None:
            raise RuntimeError("OllamaMultimodalLLM.load() を先に呼んでください")

        has_image = image is not None
        ollama_messages = self._to_ollama_messages(messages, has_image=has_image)
        if image is not None:
            self._attach_image_to_last_user(ollama_messages, image)

        model = self._select_model(has_image)
        payload = {
            "model": model,
            "messages": ollama_messages,
            "stream": False,
            "options": {"num_predict": self._max_new_tokens},
        }
        response = self._client.post(f"{self._endpoint}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        return self._clean_response(data.get("message", {}).get("content", ""))

    def _to_ollama_messages(self, messages: list[dict], has_image: bool) -> list[dict]:
        ollama_messages: list[dict] = []
        if self._system_prompt:
            ollama_messages.append({"role": "system", "content": self._system_prompt})
        ollama_messages.append(
            {
                "role": "system",
                "content": self._turn_context_prompt(has_image),
            }
        )

        for message in messages:
            content = message.get("content", "")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = "\n".join(
                    item.get("text", "")
                    for item in content
                    if item.get("type") == "text"
                )
            else:
                text = str(content)
            ollama_messages.append({"role": message["role"], "content": text})
        return ollama_messages

    @staticmethod
    def _turn_context_prompt(has_image: bool) -> str:
        if has_image:
            return (
                "このターンには画像が渡されています。画像はロボットの状況把握に使い、"
                "ユーザーの質問に必要な範囲だけ自然に触れてください。"
            )
        return (
            "このターンには画像が渡されていません。目の前、カメラ、視界、机、充電ステーションなど、"
            "見えていない周囲の状況を想像して話さないでください。純粋なテキスト会話として返答してください。"
        )

    @staticmethod
    def _attach_image_to_last_user(messages: list[dict], image: np.ndarray) -> None:
        import cv2  # type: ignore

        ok, encoded = cv2.imencode(".jpg", image)
        if not ok:
            raise RuntimeError("画像のJPEGエンコードに失敗しました")
        b64 = base64.b64encode(encoded.tobytes()).decode("ascii")

        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "user":
                messages[i]["images"] = [b64]
                return

    def _select_model(self, has_image: bool) -> str:
        if has_image:
            return self._vision_model_id or self._model_id
        return self._chat_model_id or self._model_id

    def _configured_models(self) -> list[str]:
        models = [
            self._chat_model_id or self._model_id,
            self._vision_model_id or self._model_id,
        ]
        deduped: list[str] = []
        for model in models:
            if model and model not in deduped:
                deduped.append(model)
        return deduped

    @staticmethod
    def _clean_response(text: str) -> str:
        return "".join(
            ch for ch in text.strip()
            if not (
                0x1F000 <= ord(ch) <= 0x1FAFF
                or 0x2600 <= ord(ch) <= 0x27BF
            )
        ).strip()

    @property
    def is_loaded(self) -> bool:
        return self._loaded
