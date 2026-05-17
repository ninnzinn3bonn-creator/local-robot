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
        ground_vision: bool = True,
        vision_grounding_prompt: str = (
            "この画像をロボットの観察メモとして解析してください。"
            "見えている事実だけを書き、推測や想像は書かないでください。"
        ),
        vision_grounding_tokens: int = 180,
        timeout: float = 300.0,
    ) -> None:
        self._model_id = model_id
        self._chat_model_id = chat_model_id
        self._vision_model_id = vision_model_id
        self._endpoint = endpoint.rstrip("/")
        self._max_new_tokens = max_new_tokens
        self._system_prompt = system_prompt
        self._ground_vision = ground_vision
        self._vision_grounding_prompt = vision_grounding_prompt
        self._vision_grounding_tokens = vision_grounding_tokens
        self._timeout = timeout
        self._client: Optional[httpx.Client] = None
        self._last_observation: Optional[str] = None
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
        if has_image and self._ground_vision:
            return self._generate_with_grounded_vision(messages, image)

        self._last_observation = None
        ollama_messages = self._to_ollama_messages(messages, has_image=has_image)
        if image is not None:
            self._attach_image_to_last_user(ollama_messages, image)

        model = self._select_model(has_image)
        return self._post_chat(model, ollama_messages, self._max_new_tokens)

    def _generate_with_grounded_vision(self, messages: list[dict], image: np.ndarray) -> str:
        vision_messages = [
            {
                "role": "system",
                "content": (
                    "あなたはロボットの視覚観察係です。会話はせず、"
                    "画像に写っている根拠だけを日本語で短く記録します。"
                ),
            },
            {"role": "user", "content": self._vision_grounding_prompt},
        ]
        self._attach_image_to_last_user(vision_messages, image)
        vision_model = self._select_model(has_image=True)
        observation = self._post_chat(
            vision_model,
            vision_messages,
            self._vision_grounding_tokens,
        )
        if not observation:
            observation = "観察結果は不明です。"
        self._last_observation = observation
        logger.info("Vision observation:\n%s", observation)

        chat_messages = self._to_ollama_messages(messages, has_image=False)
        self._replace_turn_context(chat_messages, self._grounded_turn_context_prompt())
        chat_messages.insert(
            2 if self._system_prompt else 1,
            {
                "role": "system",
                "content": self._vision_observation_prompt(observation),
            },
        )
        return self._post_chat(
            self._select_model(has_image=False),
            chat_messages,
            self._max_new_tokens,
        )

    def _post_chat(self, model: str, messages: list[dict], max_tokens: int) -> str:
        if self._client is None:
            raise RuntimeError("OllamaMultimodalLLM.load() を先に呼んでください")
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": max_tokens},
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
    def _grounded_turn_context_prompt() -> str:
        return (
            "このターンでは、画像そのものではなく直前フレームの観察メモが渡されています。"
            "観察メモを現在の視界として扱い、メモにない周囲状況は想像しないでください。"
        )

    @staticmethod
    def _replace_turn_context(messages: list[dict], content: str) -> None:
        if len(messages) >= 2 and messages[1].get("role") == "system":
            messages[1]["content"] = content
            return
        if messages and messages[0].get("role") == "system":
            messages[0]["content"] = content
            return
        messages.insert(0, {"role": "system", "content": content})

    @staticmethod
    def _vision_observation_prompt(observation: str) -> str:
        return (
            "このターンでは、別の視覚モデルが直前フレームを観察した結果だけを使えます。\n"
            "観察メモにない物体、人物、文字、距離、状況を追加で想像しないでください。\n"
            "観察メモで「見えない」「不明」「見当たらない」と書かれた項目は、存在確認ではなく否定として扱ってください。\n"
            "観察が曖昧なら曖昧だと伝え、必要ならユーザーに確認してください。\n"
            "Markdown記法、箇条書き記号、強調記号は使わず、音声で自然に読める文にしてください。\n"
            "画面説明だけで終わらせず、ユーザーの発話意図への返事として自然に話してください。\n\n"
            f"観察メモ:\n{observation}"
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

    @property
    def last_observation(self) -> Optional[str]:
        return self._last_observation
