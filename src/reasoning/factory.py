"""
reasoning/factory.py - LLM backend selection.
"""
from __future__ import annotations

from src.config import LLMConfig
from src.reasoning.base import MultimodalLLM
from src.reasoning.gemma import GemmaMultimodalLLM
from src.reasoning.llm import QwenVLLM
from src.reasoning.ollama import OllamaMultimodalLLM


def create_llm(cfg: LLMConfig) -> MultimodalLLM:
    backend = cfg.backend.lower()
    if backend in {"ollama", "ollama-gemma", "ollama-vision"}:
        return OllamaMultimodalLLM(
            model_id=cfg.model_id,
            chat_model_id=cfg.chat_model_id,
            vision_model_id=cfg.vision_model_id,
            endpoint=cfg.endpoint,
            max_new_tokens=cfg.max_new_tokens,
            system_prompt=cfg.system_prompt,
            ground_vision=cfg.ground_vision,
            vision_grounding_prompt=cfg.vision_grounding_prompt,
            vision_grounding_tokens=cfg.vision_grounding_tokens,
        )
    if backend in {"gemma", "gemma4", "gemma-4"}:
        return GemmaMultimodalLLM(
            model_id=cfg.model_id,
            quantization=cfg.quantization,
            max_new_tokens=cfg.max_new_tokens,
            system_prompt=cfg.system_prompt,
            dtype=cfg.dtype,
        )
    if backend in {"qwen", "qwen2.5-vl", "qwen2_5_vl"}:
        return QwenVLLM(
            model_id=cfg.model_id,
            quantization=cfg.quantization,
            max_new_tokens=cfg.max_new_tokens,
            system_prompt=cfg.system_prompt,
        )
    raise ValueError(f"Unsupported LLM backend: {cfg.backend}")
