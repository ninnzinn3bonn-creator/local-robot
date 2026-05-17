"""
Compare local Ollama models for the robot conversation workload.

Run:
  python scripts/compare_ollama_models.py --runs 1
  python scripts/compare_ollama_models.py --models qwen3.5:9b gemma3:12b --runs 2
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import cv2  # type: ignore
import httpx
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from src.io.camera import resize_for_llm
from src.utils.encoding import configure_utf8_stdio

configure_utf8_stdio()


TEXT_PROMPTS = [
    (
        "conversation",
        "今日はちょっと疲れたよ。画面説明ではなく、じろえもんとして短く自然に返して。",
    ),
    (
        "intent",
        "ロボットが机の近くにいるとして、「それ取れる？」と言われました。"
        "勝手に動かず、次に確認すべきことを短く答えて。",
    ),
]
VISION_PROMPT = (
    "この画像を、会話の返事ではなくロボットが動く前の状況把握として見てください。"
    "移動や手を伸ばす前に注意すべき点だけを日本語で3つ以内に挙げて。"
)


def make_dummy_image(width: int = 768, height: int = 432) -> np.ndarray:
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:, :, 0] = 48
    img[:, :, 1] = np.linspace(64, 190, height, dtype=np.uint8).reshape(height, 1)
    img[:, :, 2] = 210
    cv2.rectangle(img, (80, 260), (680, 380), (40, 40, 40), thickness=-1)
    cv2.circle(img, (190, 220), 45, (230, 230, 230), thickness=-1)
    cv2.putText(img, "LOCAL ROBOT", (250, 230), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (20, 20, 20), 2)
    return img


def capture_image(camera_index: int) -> np.ndarray:
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    try:
        ret, frame = cap.read()
    finally:
        cap.release()
    if not ret or frame is None:
        print("camera capture failed; using dummy image")
        return make_dummy_image()
    return resize_for_llm(frame)


def encode_image(image: np.ndarray) -> str:
    ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise RuntimeError("failed to encode image")
    return base64.b64encode(encoded.tobytes()).decode("ascii")


def supports_vision(model: str) -> bool:
    lowered = model.lower()
    return "vl" in lowered or "vision" in lowered or lowered.startswith("gemma3")


def chat(
    endpoint: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_new_tokens: int,
    image: Optional[np.ndarray] = None,
) -> dict[str, Any]:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    if image is not None:
        messages[-1]["images"] = [encode_image(image)]

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"num_predict": max_new_tokens},
    }
    t0 = time.perf_counter()
    with httpx.Client(timeout=300.0) as client:
        response = client.post(f"{endpoint.rstrip('/')}/api/chat", json=payload)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    response.raise_for_status()
    data = response.json()
    return {
        "model": model,
        "elapsed_ms": elapsed_ms,
        "response": data.get("message", {}).get("content", "").strip(),
        "raw": {
            "eval_count": data.get("eval_count"),
            "eval_duration": data.get("eval_duration"),
            "prompt_eval_count": data.get("prompt_eval_count"),
            "prompt_eval_duration": data.get("prompt_eval_duration"),
        },
    }


def default_models() -> list[str]:
    cfg = load_config()
    models = [
        cfg.llm.chat_model_id or cfg.llm.model_id,
        cfg.llm.vision_model_id or cfg.llm.model_id,
        "qwen3.5:9b",
        "gemma3:12b",
        "gemma3:4b",
    ]
    deduped: list[str] = []
    for model in models:
        if model and model not in deduped:
            deduped.append(model)
    return deduped


def main() -> int:
    cfg = load_config()
    parser = argparse.ArgumentParser(description="Compare local Ollama model responses and latency")
    parser.add_argument("--models", nargs="+", default=default_models(), help="Ollama model names")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--endpoint", default=cfg.llm.endpoint)
    parser.add_argument("--max-new-tokens", type=int, default=cfg.llm.max_new_tokens)
    parser.add_argument("--use-camera", action="store_true")
    parser.add_argument("--vision", action="store_true", help="also run the vision prompt on vision-capable models")
    parser.add_argument("--output-dir", default="logs/model_compare")
    args = parser.parse_args()

    image = capture_image(cfg.camera.index) if args.use_camera else make_dummy_image()
    results: list[dict[str, Any]] = []

    for model in args.models:
        print(f"\n== {model} ==")
        for run in range(args.runs):
            for prompt_id, prompt in TEXT_PROMPTS:
                try:
                    result = chat(args.endpoint, model, cfg.llm.system_prompt, prompt, args.max_new_tokens)
                    result.update({"run": run + 1, "prompt_id": prompt_id, "has_image": False})
                    results.append(result)
                    print(f"[text:{prompt_id} run={run + 1}] {result['elapsed_ms']}ms")
                    print(result["response"])
                except Exception as exc:
                    error = {"model": model, "run": run + 1, "prompt_id": prompt_id, "error": str(exc)}
                    results.append(error)
                    print(f"[text:{prompt_id} error] {exc}")
            if args.vision and supports_vision(model):
                try:
                    result = chat(args.endpoint, model, cfg.llm.system_prompt, VISION_PROMPT, args.max_new_tokens, image)
                    result.update({"run": run + 1, "prompt_id": "vision_safety", "has_image": True})
                    results.append(result)
                    print(f"[vision run={run + 1}] {result['elapsed_ms']}ms")
                    print(result["response"])
                except Exception as exc:
                    error = {"model": model, "run": run + 1, "prompt_id": "vision_safety", "has_image": True, "error": str(exc)}
                    results.append(error)
                    print(f"[vision error] {exc}")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"ollama_compare_{stamp}.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
