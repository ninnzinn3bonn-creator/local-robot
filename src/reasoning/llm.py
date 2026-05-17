"""
reasoning/llm.py — Qwen2.5-VL-7B-Instruct (4bit NF4) 推論ラッパ。

入力: テキストプロンプト + BGR ndarray（オプション）
出力: 生成テキスト（str）

VRAM 管理:
  - bitsandbytes NF4 量子化でロード（約5.5GB）
  - 推論後は torch.cuda.empty_cache() を呼ぶ
  - 画像は長辺768pxにリサイズ済みのものを受け取る想定
"""
from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

ACCELERATE_DEVICE_MAP_PRESETS = {
    "auto",
    "balanced",
    "balanced_low_0",
    "sequential",
}


class QwenVLLM:
    """
    Qwen2.5-VL 推論ラッパ。

    使い方:
        llm = QwenVLLM(model_id="Qwen/Qwen2.5-VL-7B-Instruct", quantization="nf4")
        llm.load(device="cuda:0")
        response = llm.generate(
            messages=[{"role": "user", "content": "これは何ですか？"}],
            image=frame_bgr,   # np.ndarray or None
        )
    """

    def __init__(
        self,
        model_id: str = "Qwen/Qwen2.5-VL-7B-Instruct",
        quantization: str = "nf4",
        max_new_tokens: int = 256,
        system_prompt: str = "あなたはカメラ映像を見ながら会話する日本語アシスタントです。",
    ) -> None:
        self._model_id = model_id
        self._quantization = quantization
        self._max_new_tokens = max_new_tokens
        self._system_prompt = system_prompt
        self._model = None
        self._processor = None

    def load(self, device: str = "cuda:0") -> None:
        """モデルをロードする。初回はダウンロードが走る（約14GB → NF4で約5.5GB VRAM）。"""
        import torch  # type: ignore
        from transformers import (  # type: ignore
            AutoProcessor,
            BitsAndBytesConfig,
            Qwen2_5_VLForConditionalGeneration,
        )

        logger.info(f"Qwen2.5-VL '{self._model_id}' をロード中...")

        bnb_cfg = None
        if self._quantization in {"nf4", "bnb4", "4bit"}:
            bnb_cfg = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.float16,
            )

        device_map = (
            device
            if device in ACCELERATE_DEVICE_MAP_PRESETS
            else {"": device}
        )

        self._model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            self._model_id,
            quantization_config=bnb_cfg,
            device_map=device_map,
            trust_remote_code=True,
        )
        self._model.eval()

        self._processor = AutoProcessor.from_pretrained(
            self._model_id,
            trust_remote_code=True,
        )

        logger.info("Qwen2.5-VL ロード完了")

    def generate(
        self,
        messages: List[dict],
        image: Optional[np.ndarray] = None,
    ) -> str:
        """
        チャットメッセージ（+ 画像）を受け取って応答テキストを返す。

        Args:
            messages: [{"role": "user", "content": "..."}] 形式のリスト
            image: BGR ndarray (None の場合は画像なしで推論)
        """
        if self._model is None or self._processor is None:
            raise RuntimeError("QwenVLLM.load() を先に呼んでください")

        import torch  # type: ignore
        from PIL import Image  # type: ignore

        # システムプロンプトを先頭に挿入
        full_messages = [{"role": "system", "content": self._system_prompt}] + messages

        # 画像を PIL に変換して最後のユーザーターンに埋め込む
        pil_images = []
        if image is not None:
            import cv2  # type: ignore
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)
            pil_images.append(pil_img)

            # Qwen2.5-VL の画像トークンは messages の content に <image> プレースホルダで指定
            # 最後のユーザーメッセージに画像を挿入
            for i in range(len(full_messages) - 1, -1, -1):
                if full_messages[i]["role"] == "user":
                    content = full_messages[i]["content"]
                    if isinstance(content, str):
                        full_messages[i]["content"] = [
                            {"type": "image", "image": pil_img},
                            {"type": "text", "text": content},
                        ]
                    break

        # テンプレート適用
        text = self._processor.apply_chat_template(
            full_messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = self._processor(
            text=[text],
            images=pil_images if pil_images else None,
            return_tensors="pt",
            padding=True,
        ).to(self._model.device)

        with torch.no_grad():
            output_ids = self._model.generate(
                **inputs,
                max_new_tokens=self._max_new_tokens,
                do_sample=False,
            )

        # 入力トークン部分を除いて出力だけデコード
        input_len = inputs["input_ids"].shape[1]
        generated = output_ids[:, input_len:]
        response = self._processor.batch_decode(
            generated, skip_special_tokens=True
        )[0].strip()

        # VRAM 断片化対策
        torch.cuda.empty_cache()

        logger.debug(f"LLM 応答: {response[:80]!r}...")
        return response

    @property
    def is_loaded(self) -> bool:
        return self._model is not None
