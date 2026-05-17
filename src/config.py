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
    model_id: str = "gemma3:4b"
    endpoint: str = "http://127.0.0.1:11434"
    quantization: str = "q4"
    dtype: str = "auto"
    max_new_tokens: int = 256
    context_window: int = 128_000
    system_prompt: str = (
        "あなたは「じろえもん」という日本語のローカルロボット相棒です。"
        "カメラ映像は状況把握の補助として使い、ユーザーが明示的に聞いていない限り、"
        "画面説明だけを返さず普通に会話してください。"
    )


class STTConfig(BaseModel):
    backend: str = "gemma"
    model: str = "large-v3"
    compute_type: str = "int8_float16"
    language: str = "ja"
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
    device: str = "cuda:0"
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
