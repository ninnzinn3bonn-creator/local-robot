"""
Download/cache a faster-whisper model for offline use.

Run:
  python scripts/pull_stt_model.py medium
  python scripts/pull_stt_model.py large-v3 --device cuda --compute-type int8_float16
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.encoding import configure_utf8_stdio

configure_utf8_stdio()


def main() -> int:
    parser = argparse.ArgumentParser(description="Cache a faster-whisper model locally")
    parser.add_argument("model", help="faster-whisper model name, e.g. small, medium, large-v3")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--download-root", default=None)
    args = parser.parse_args()

    from faster_whisper import WhisperModel  # type: ignore

    print(
        f"Loading {args.model} with local_files_only=False "
        f"({args.device}, {args.compute_type})..."
    )
    WhisperModel(
        args.model,
        device=args.device,
        compute_type=args.compute_type,
        download_root=args.download_root,
        local_files_only=False,
    )
    print("OK: model is cached for later offline runs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
