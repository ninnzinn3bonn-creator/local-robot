"""
Compare faster-whisper models using either a WAV file or a local VOICEVOX sample.

Run:
  python scripts/compare_stt_models.py --models small medium
  python scripts/compare_stt_models.py --audio logs/sample.wav --models small medium large-v3
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf  # type: ignore

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from src.perception.stt import WhisperSTT
from src.speech.tts import VoicevoxTTS
from src.utils.encoding import configure_utf8_stdio

configure_utf8_stdio()

TARGET_SAMPLE_RATE = 16_000


def resample_to_16k(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    waveform = np.asarray(audio, dtype=np.float32)
    if waveform.ndim > 1:
        waveform = waveform.mean(axis=1)
    if sample_rate == TARGET_SAMPLE_RATE:
        return waveform
    duration = len(waveform) / float(sample_rate)
    old_x = np.linspace(0.0, duration, num=len(waveform), endpoint=False)
    new_len = max(1, int(duration * TARGET_SAMPLE_RATE))
    new_x = np.linspace(0.0, duration, num=new_len, endpoint=False)
    return np.interp(new_x, old_x, waveform).astype(np.float32)


def load_audio(path: Path) -> np.ndarray:
    data, sample_rate = sf.read(path, dtype="float32", always_2d=False)
    return resample_to_16k(np.asarray(data), int(sample_rate))


def synthesize_sample(text: str, endpoint: str, speaker_id: int) -> np.ndarray:
    tts = VoicevoxTTS(endpoint=endpoint, speaker_id=speaker_id)
    tts.start()
    try:
        wav = tts.synthesize(text)
    finally:
        tts.stop()
    data, sample_rate = sf.read(io.BytesIO(wav), dtype="float32", always_2d=False)
    return resample_to_16k(np.asarray(data), int(sample_rate))


def default_models() -> list[str]:
    cfg = load_config()
    models = ["small", cfg.stt.model]
    deduped: list[str] = []
    for model in models:
        if model and model not in deduped:
            deduped.append(model)
    return deduped


def main() -> int:
    cfg = load_config()
    parser = argparse.ArgumentParser(description="Compare local faster-whisper models")
    parser.add_argument("--models", nargs="+", default=default_models())
    parser.add_argument("--audio", default=None, help="Optional WAV/FLAC/OGG file to transcribe")
    parser.add_argument("--sample-text", default="ジロー、今日はロボットの動作確認をします。右を見て、机の上を確認して。")
    parser.add_argument("--device", default="cuda" if "cuda" in cfg.device else "cpu", choices=["cpu", "cuda"])
    parser.add_argument("--compute-type", default=cfg.stt.compute_type)
    parser.add_argument("--allow-download", action="store_true")
    parser.add_argument("--output-dir", default="logs/stt_compare")
    args = parser.parse_args()

    if args.audio:
        waveform = load_audio(Path(args.audio))
        source = args.audio
    else:
        waveform = synthesize_sample(args.sample_text, cfg.tts.endpoint, cfg.tts.speaker_id)
        source = "voicevox"

    results = []
    for model_name in args.models:
        print(f"\n== {model_name} ==")
        stt = WhisperSTT(
            model=model_name,
            compute_type=args.compute_type,
            language=cfg.stt.language,
            initial_prompt=cfg.stt.initial_prompt,
            hotwords=cfg.stt.hotwords,
            hallucination_silence_threshold=cfg.stt.hallucination_silence_threshold,
            local_files_only=not args.allow_download,
            download_root=cfg.stt.download_root,
        )
        t0 = time.perf_counter()
        try:
            stt.load(device=args.device)
            text = stt.transcribe(waveform)
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            print(f"{elapsed_ms}ms | {text!r}")
            results.append(
                {
                    "model": model_name,
                    "device": args.device,
                    "compute_type": args.compute_type,
                    "elapsed_ms": elapsed_ms,
                    "text": text,
                    "source": source,
                }
            )
        except Exception as exc:
            print(f"ERROR: {exc}")
            results.append({"model": model_name, "error": str(exc), "source": source})

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"stt_compare_{stamp}.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
