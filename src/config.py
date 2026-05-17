"""
config.py — config.yaml を読み込んで pydantic モデルとして公開する。
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# サブ設定モデル
# ---------------------------------------------------------------------------

class LLMConfig(BaseModel):
    backend: str = "ollama"
    model_id: str = "qwen2.5vl:7b"
    chat_model_id: Optional[str] = "gemma3:12b"
    vision_model_id: Optional[str] = "qwen2.5vl:7b"
    endpoint: str = "http://127.0.0.1:11434"
    quantization: str = "q4"
    dtype: str = "auto"
    max_new_tokens: int = 256
    context_window: int = 128_000
    ground_vision: bool = True
    vision_grounding_tokens: int = 180
    vision_grounding_prompt: str = (
        "この画像をロボットの観察メモとして解析してください。"
        "見えている事実だけを書き、推測や想像は書かないでください。"
        "人、物、文字、位置関係、移動や接触で注意すべき点を短い箇条書きにしてください。"
        "用水路清掃ロボットの視点として、壁面、水、泥、落ち葉、枝、ゴミ、詰まり、"
        "段差、進行方向の障害物が見える場合は分けて書いてください。"
        "見えないものは「見えない」または「不明」と書いてください。"
        "毎回同じ定型文にせず、このフレーム固有の情報を優先してください。"
    )
    system_prompt: str = (
        "あなたは「じろえもん」という日本語のローカルロボット相棒です。"
        "最終的には40cm級のタイヤ/キャタピラ式用水路清掃ロボットの頭脳として、"
        "周囲の状況把握と安全な作業判断を補助します。"
        "カメラ映像は状況把握の補助として使い、ユーザーが明示的に聞いていない限り、"
        "画面説明だけを返さず普通に会話してください。"
        "用水路、ゴミ、泥、落ち葉、枝、詰まり、壁面、段差、進行方向の障害物について"
        "聞かれた時は、見えている根拠と不明点を分けて短く答えてください。"
        "会話の主題が画像でなければ、画像内の物体や背景に触れないでください。"
        "画像が渡されていないターンでは、見えていない周囲の状況を想像しないでください。"
        "Markdown記法、箇条書き記号、強調記号は使わず、音声で自然に読める文にしてください。"
        "音声で読み上げるため、絵文字や顔文字は使わないでください。"
    )


class STTConfig(BaseModel):
    backend: str = "faster-whisper"
    model: str = "small"
    compute_type: str = "int8"
    language: str = "ja"
    initial_prompt: str = "ジロー、じろえもん、ヘイジロー。日本語の短い会話です。"
    hotwords: str = "ジロー じろえもん ヘイジロー これ 読んで 見て"
    hallucination_silence_threshold: float = 0.7
    local_files_only: bool = True
    download_root: Optional[str] = None


class VADConfig(BaseModel):
    backend: str = "energy"
    threshold: float = 0.012
    min_speech_ms: int = 300
    min_silence_ms: int = 600
    max_speech_ms: int = 15000


class TTSConfig(BaseModel):
    endpoint: str = "http://127.0.0.1:50021"
    speaker_id: int = 3


class CameraConfig(BaseModel):
    index: int = 0
    width: int = 1280
    height: int = 720
    capture_fps: int = 12


class MicConfig(BaseModel):
    device: Optional[int] = None


class SpeakerConfig(BaseModel):
    device: Optional[int] = None


class MemoryConfig(BaseModel):
    max_turns: int = 10


class WakeWordConfig(BaseModel):
    enabled: bool = True
    phrase: str = "ジロー"
    aliases: List[str] = Field(default_factory=lambda: [
        "ジロー",
        "じろー",
        "じろう",
        "ジロウ",
        "二郎",
        "じろえもん",
        "ジロエモン",
        "ジローエモン",
        "じろーえもん",
        "次郎衛門",
        "じろうえもん",
        "ねえジロー",
        "ヘイジロー",
        "ページロー",
        "ペジロー",
        "hey jiro",
        "heyjiro",
        "hello jiro",
    ])
    timeout_after_response_sec: int = 8


class LoggingConfig(BaseModel):
    level: str = "INFO"
    conversation_log_dir: str = "./logs"
    save_frames: bool = False
    rotate: str = "daily"


class LanguageConfig(BaseModel):
    primary: str = "ja"
    reject_other: bool = True


class UIConfig(BaseModel):
    mode: str = "cli"


# ---------------------------------------------------------------------------
# ルート設定モデル
# ---------------------------------------------------------------------------

class AppConfig(BaseModel):
    device: str = "cpu"
    llm: LLMConfig = Field(default_factory=LLMConfig)
    stt: STTConfig = Field(default_factory=STTConfig)
    vad: VADConfig = Field(default_factory=VADConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    camera: CameraConfig = Field(default_factory=CameraConfig)
    mic: MicConfig = Field(default_factory=MicConfig)
    speaker: SpeakerConfig = Field(default_factory=SpeakerConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    wake_word: WakeWordConfig = Field(default_factory=WakeWordConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    language: LanguageConfig = Field(default_factory=LanguageConfig)
    ui: UIConfig = Field(default_factory=UIConfig)


# ---------------------------------------------------------------------------
# ローダ
# ---------------------------------------------------------------------------

def load_config(path: str | Path = "config.yaml") -> AppConfig:
    """YAML ファイルを読み込んで AppConfig を返す。ファイルが無い場合はデフォルト値を使用。"""
    p = Path(path)
    if not p.exists():
        return AppConfig()
    with p.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return AppConfig.model_validate(raw)
