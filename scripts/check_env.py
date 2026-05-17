"""
scripts/check_env.py — 環境確認スクリプト（Phase 0 Done条件チェック）。

確認項目:
  - Python バージョン
  - CUDA 利用可否・バージョン
  - GPU 名・VRAM 容量
  - 主要ライブラリのインポート確認
  - VOICEVOX ENGINE 疎通確認
  - カメラデバイス列挙
  - マイクデバイス列挙

実行方法:
  python scripts/check_env.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# プロジェクトルートを sys.path に追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.encoding import configure_utf8_stdio

configure_utf8_stdio()


def check_python() -> None:
    print(f"\n{'='*50}")
    print("Python バージョン")
    print(f"{'='*50}")
    v = sys.version_info
    print(f"Python {v.major}.{v.minor}.{v.micro}")
    if v.major != 3 or v.minor != 11:
        print("  ⚠ Python 3.11.x 推奨 (bitsandbytes の Windows 対応)")
    else:
        print("  ✓ OK")


def check_cuda() -> None:
    print(f"\n{'='*50}")
    print("CUDA / GPU")
    print(f"{'='*50}")
    try:
        from src.config import load_config
        cfg = load_config("config.yaml")
    except Exception:
        cfg = None
    torch_required = cfg is None or cfg.llm.backend.lower() in {
        "gemma", "gemma4", "gemma-4", "qwen", "qwen2.5-vl", "qwen2_5_vl"
    } or cfg.vad.backend.lower() == "silero"

    try:
        import torch
        print(f"PyTorch: {torch.__version__}")
        if torch.cuda.is_available():
            print(f"  ✓ CUDA 利用可能")
            print(f"  CUDA バージョン: {torch.version.cuda}")
            for i in range(torch.cuda.device_count()):
                name = torch.cuda.get_device_name(i)
                total = torch.cuda.get_device_properties(i).total_memory / 1024**3
                free, total2 = torch.cuda.mem_get_info(i)
                free_gb = free / 1024**3
                print(f"  GPU {i}: {name}")
                print(f"    総VRAM: {total:.1f} GB")
                print(f"    空きVRAM: {free_gb:.1f} GB")
        else:
            print("  ✗ CUDA 利用不可")
    except ImportError:
        if torch_required:
            print("  ✗ PyTorch がインストールされていません")
        else:
            print("  - PyTorch 未インストール（現在のOllama/Energy VAD構成では任意）")
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            print(f"  GPU: {result.stdout.strip()}")
    except Exception:
        pass


def check_libraries() -> None:
    print(f"\n{'='*50}")
    print("ライブラリ確認")
    print(f"{'='*50}")
    try:
        from src.config import load_config
        cfg = load_config("config.yaml")
    except Exception:
        cfg = None

    required_libs = [
        ("cv2", "opencv-python"),
        ("sounddevice", "sounddevice"),
        ("soundfile", "soundfile"),
        ("numpy", "numpy"),
        ("PIL", "pillow"),
        ("pydantic", "pydantic"),
        ("yaml", "pyyaml"),
        ("httpx", "httpx"),
        ("rich", "rich"),
    ]
    optional_libs = [
        ("faster_whisper", "faster-whisper"),
        ("transformers", "transformers"),
        ("accelerate", "accelerate"),
        ("bitsandbytes", "bitsandbytes"),
        ("silero_vad", "silero-vad"),
    ]

    if cfg is not None:
        if cfg.stt.backend.lower() in {"faster-whisper", "whisper"}:
            required_libs.append(("faster_whisper", "faster-whisper"))
        if cfg.llm.backend.lower() in {"gemma", "gemma4", "gemma-4", "qwen"}:
            required_libs.extend([
                ("transformers", "transformers"),
                ("accelerate", "accelerate"),
                ("bitsandbytes", "bitsandbytes"),
            ])
        if cfg.vad.backend.lower() == "silero":
            required_libs.append(("silero_vad", "silero-vad"))

    for module, package in required_libs:
        try:
            mod = __import__(module)
            ver = getattr(mod, "__version__", "?")
            print(f"  ✓ {package} ({ver})")
        except ImportError:
            print(f"  ✗ {package} — 未インストール")

    required_modules = {module for module, _ in required_libs}
    print("\n任意ライブラリ")
    for module, package in optional_libs:
        if module in required_modules:
            continue
        try:
            mod = __import__(module)
            ver = getattr(mod, "__version__", "?")
            print(f"  ✓ {package} ({ver})")
        except ImportError:
            print(f"  - {package} — 未インストール")


def check_voicevox() -> None:
    print(f"\n{'='*50}")
    print("VOICEVOX ENGINE 疎通確認")
    print(f"{'='*50}")
    try:
        import httpx
    except ImportError:
        print("  ✗ httpx が未インストールのため疎通確認をスキップ")
        return
    try:
        r = httpx.get("http://127.0.0.1:50021/version", timeout=2.0)
        if r.status_code == 200:
            print(f"  ✓ VOICEVOX ENGINE 稼働中 (バージョン: {r.text.strip()})")
        else:
            print(f"  ✗ 応答あり、ステータス: {r.status_code}")
    except Exception as e:
        print(f"  ✗ 接続失敗: {e}")
        print("    → VOICEVOX ENGINE を先に起動してください")


def check_ollama() -> None:
    print(f"\n{'='*50}")
    print("Ollama / LLM")
    print(f"{'='*50}")
    try:
        from src.config import load_config
        cfg = load_config("config.yaml")
    except Exception as e:
        print(f"  ✗ config 読み込み失敗: {e}")
        return
    if cfg.llm.backend.lower() != "ollama":
        print(f"  - llm.backend={cfg.llm.backend} のため Ollama 確認をスキップ")
        return
    try:
        import httpx
    except ImportError:
        print("  ✗ httpx が未インストールのため確認をスキップ")
        return
    try:
        r = httpx.get(f"{cfg.llm.endpoint}/api/tags", timeout=5.0)
        r.raise_for_status()
        models = [m.get("name") for m in r.json().get("models", [])]
        wanted = [
            cfg.llm.chat_model_id or cfg.llm.model_id,
            cfg.llm.vision_model_id or cfg.llm.model_id,
        ]
        missing = []
        for model in dict.fromkeys(wanted):
            if model in models:
                print(f"  ✓ model={model}")
            else:
                print(f"  ✗ model={model} が未取得")
                missing.append(model)
        if missing:
            for model in missing:
                print("    → ollama pull " + model)
        else:
            print("  ✓ Ollama 稼働中")
    except Exception as e:
        print(f"  ✗ Ollama 接続失敗: {e}")


def check_camera() -> None:
    print(f"\n{'='*50}")
    print("カメラデバイス")
    print(f"{'='*50}")
    try:
        import cv2
        found = []
        for i in range(5):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                found.append((i, w, h))
                cap.release()
        if found:
            for idx, w, h in found:
                print(f"  ✓ index={idx}: {w}x{h}")
        else:
            print("  ✗ カメラが見つかりません")
    except Exception as e:
        print(f"  ✗ OpenCV エラー: {e}")


def check_mic() -> None:
    print(f"\n{'='*50}")
    print("マイクデバイス")
    print(f"{'='*50}")
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_devices = [d for d in devices if d["max_input_channels"] > 0]
        if input_devices:
            for d in input_devices[:5]:  # 最大5件表示
                print(f"  ✓ [{d['index']}] {d['name']} (ch={d['max_input_channels']})")
        else:
            print("  ✗ マイクが見つかりません")
    except Exception as e:
        print(f"  ✗ sounddevice エラー: {e}")


if __name__ == "__main__":
    print("ローカルモーダルエージェント — 環境確認")
    check_python()
    check_cuda()
    check_libraries()
    check_ollama()
    check_voicevox()
    check_camera()
    check_mic()
    print(f"\n{'='*50}")
    print("確認完了")
    print(f"{'='*50}\n")
