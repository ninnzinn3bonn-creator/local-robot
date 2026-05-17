"""
Record a short microphone clip and transcribe it with faster-whisper.

Run:
  python scripts/smoke_mic_stt.py --seconds 5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import sounddevice as sd  # type: ignore

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from src.io.mic import SAMPLE_RATE
from src.perception.stt import WhisperSTT
from src.utils.encoding import configure_utf8_stdio

configure_utf8_stdio()


def main() -> int:
    parser = argparse.ArgumentParser(description="Mic + STT smoke test")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--seconds", type=float, default=5.0)
    args = parser.parse_args()

    cfg = load_config(args.config)
    if cfg.stt.backend.lower() not in {"faster-whisper", "whisper"}:
        print("NG: this smoke test currently expects stt.backend=faster-whisper")
        return 1

    print(f"Recording {args.seconds:.1f}s from mic device={cfg.mic.device}...")
    audio = sd.rec(
        int(SAMPLE_RATE * args.seconds),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        device=cfg.mic.device,
    )
    sd.wait()
    waveform = np.asarray(audio).reshape(-1)
    rms = float(np.sqrt(np.mean(np.square(waveform)))) if len(waveform) else 0.0
    print(f"RMS: {rms:.4f}")
    if rms < cfg.vad.threshold:
        print(
            "OK: mic opened, but the recording was below the VAD threshold. "
            "Speak during the test to verify transcription."
        )
        return 0

    stt = WhisperSTT(
        model=cfg.stt.model,
        compute_type=cfg.stt.compute_type,
        language=cfg.stt.language,
        local_files_only=cfg.stt.local_files_only,
        download_root=cfg.stt.download_root,
    )
    device = "cuda" if "cuda" in cfg.device else "cpu"
    stt.load(device=device)
    text = stt.transcribe(waveform)
    print(f"TRANSCRIPT: {text!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
