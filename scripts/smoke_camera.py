"""
Capture one camera frame and optionally ask the configured LLM about it.

Run:
  python scripts/smoke_camera.py
  python scripts/smoke_camera.py --ask
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from src.io.camera import CameraCapture, resize_for_llm
from src.reasoning.factory import create_llm
from src.utils.encoding import configure_utf8_stdio

configure_utf8_stdio()


def main() -> int:
    parser = argparse.ArgumentParser(description="Camera smoke test")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--ask", action="store_true", help="Send the frame to the configured LLM")
    args = parser.parse_args()

    cfg = load_config(args.config)
    camera = CameraCapture(
        index=cfg.camera.index,
        width=cfg.camera.width,
        height=cfg.camera.height,
        capture_fps=cfg.camera.capture_fps,
    )
    camera.start()
    try:
        frame = None
        for _ in range(30):
            frame = camera.get_latest()
            if frame is not None:
                break
            time.sleep(0.1)
        if frame is None:
            print("NG: camera frame was not captured")
            return 1

        h, w = frame.shape[:2]
        out = Path("logs") / "smoke_camera.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)

        import cv2  # type: ignore

        cv2.imwrite(str(out), frame)
        print(f"OK: camera frame {w}x{h} saved to {out}")

        if args.ask:
            llm = create_llm(cfg.llm)
            llm.load(device=cfg.device)
            prompt = "この画像に何が映っていますか？日本語で短く答えてください。"
            response = llm.generate([{"role": "user", "content": prompt}], resize_for_llm(frame))
            print(f"LLM: {response}")

        return 0
    finally:
        camera.stop()


if __name__ == "__main__":
    raise SystemExit(main())

