"""
scripts/bench_llm.py — LLM 推論レイテンシ計測スクリプト（Phase 1 用）。

テスト内容:
  1. テキストのみ推論（画像なし）
  2. テキスト + サンプル画像推論（Webカメラ or ダミー画像）
  3. 複数回計測して p50 / p95 を表示

実行方法:
  python scripts/bench_llm.py [--config config.yaml] [--runs 3]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import List, Optional

import numpy as np

# プロジェクトルートを sys.path に追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from src.reasoning.base import MultimodalLLM
from src.reasoning.factory import create_llm
from src.utils.encoding import configure_utf8_stdio
from src.utils.logging import setup_logging

configure_utf8_stdio()


def make_dummy_image(width: int = 768, height: int = 432) -> np.ndarray:
    """ダミーの BGR 画像を生成する（カメラ不使用時）。"""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    # グレーグラデーション
    for y in range(height):
        img[y, :] = int(255 * y / height)
    return img


def percentile(values: List[float], p: float) -> float:
    sorted_v = sorted(values)
    idx = int(len(sorted_v) * p / 100)
    return sorted_v[min(idx, len(sorted_v) - 1)]


def bench(llm: MultimodalLLM, prompt: str, image: Optional[np.ndarray], runs: int) -> None:
    label = "テキスト+画像" if image is not None else "テキストのみ"
    print(f"\n--- ベンチマーク: {label} ({runs}回) ---")
    messages = [{"role": "user", "content": prompt}]

    times: List[float] = []
    for i in range(runs):
        t0 = time.perf_counter()
        response = llm.generate(messages, image)
        elapsed = (time.perf_counter() - t0) * 1000
        times.append(elapsed)
        print(f"  [{i+1}/{runs}] {elapsed:.0f}ms | {response[:60]!r}")

    print(f"  p50: {percentile(times, 50):.0f}ms")
    print(f"  p95: {percentile(times, 95):.0f}ms")
    print(f"  min: {min(times):.0f}ms / max: {max(times):.0f}ms")


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM レイテンシ計測")
    parser.add_argument("--config", default="config.yaml", help="設定ファイルパス")
    parser.add_argument("--runs", type=int, default=3, help="計測回数")
    parser.add_argument("--use-camera", action="store_true", help="Webカメラを使用")
    args = parser.parse_args()

    cfg = load_config(args.config)
    setup_logging("INFO")

    chat_model = cfg.llm.chat_model_id or cfg.llm.model_id
    vision_model = cfg.llm.vision_model_id or cfg.llm.model_id
    print(
        f"LLM backend={cfg.llm.backend} "
        f"chat={chat_model} vision={vision_model} をロード中..."
    )
    llm = create_llm(cfg.llm)
    llm.load(device=cfg.device)

    # 画像準備
    image = None
    if args.use_camera:
        import cv2
        cap = cv2.VideoCapture(cfg.camera.index, cv2.CAP_DSHOW)
        ret, frame = cap.read()
        cap.release()
        if ret:
            from src.io.camera import resize_for_llm
            image = resize_for_llm(frame)
            print(f"カメラフレーム取得: {image.shape[1]}x{image.shape[0]}")
        else:
            print("カメラ取得失敗。ダミー画像を使用します。")
            image = make_dummy_image()
    else:
        print("ダミー画像を使用します。--use-camera でWebカメラを使用できます。")
        image = make_dummy_image()

    # ベンチマーク実行
    bench(llm, "今日は少し疲れたよ。じろえもんとして短く自然に返して。", None, args.runs)
    bench(llm, "この画像を見て、ロボットが動く前に注意すべき点を日本語で短く答えてください。", image, args.runs)

    print("\n✓ ベンチマーク完了")


if __name__ == "__main__":
    main()
