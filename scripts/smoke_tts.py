"""
VOICEVOX synthesis and playback smoke test.

Run:
  python scripts/smoke_tts.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from src.io.speaker import Speaker
from src.speech.tts import VoicevoxTTS
from src.utils.encoding import configure_utf8_stdio

configure_utf8_stdio()


def main() -> int:
    parser = argparse.ArgumentParser(description="VOICEVOX smoke test")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--text", default="ローカルモーダルの音声テストです。")
    args = parser.parse_args()

    cfg = load_config(args.config)
    tts = VoicevoxTTS(endpoint=cfg.tts.endpoint, speaker_id=cfg.tts.speaker_id)
    tts.start()
    try:
        if not tts.is_available():
            print("NG: VOICEVOX ENGINE is not available")
            return 1
        wav = tts.synthesize(args.text)
        print(f"OK: synthesized {len(wav)} bytes")
        Speaker(device=cfg.speaker.device).play(wav)
        print("OK: playback finished")
        return 0
    finally:
        tts.stop()


if __name__ == "__main__":
    raise SystemExit(main())

