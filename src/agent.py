"""
agent.py — VisionAudioAgent オーケストレータ（中核）。

状態機械:
  IDLE → WAKE_WAIT → LISTENING → THINKING → SPEAKING → IDLE

- WAKE_WAIT: STT 結果に「じろえもん」が含まれた場合のみ LISTENING へ遷移
- timeout_after_response_sec 以内は wake word をスキップして連続会話可
- SPEAKING 中はマイク入力を破棄（エコー防止）
- 全処理は asyncio イベントループ1本に集約
- 重い同期処理（STT・LLM・TTS）は run_in_executor でスレッドプールへ
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional

import numpy as np

from src.utils.encoding import configure_utf8_stdio

configure_utf8_stdio()

from rich.console import Console

from src.config import AppConfig, load_config
from src.io.camera import CameraCapture
from src.io.mic import MicStream
from src.io.speaker import Speaker
from src.perception.stt import WhisperSTT
from src.perception.wake_word import WakeWordDetector
from src.reasoning.factory import create_llm
from src.reasoning.memory import ConversationMemory
from src.speech.tts import VoicevoxTTS
from src.utils.logging import ConversationLogger, setup_logging
from src.utils.metrics import LatencyTimer

logger = logging.getLogger(__name__)
console = Console()

# ---------------------------------------------------------------------------
# データ型
# ---------------------------------------------------------------------------

class AgentState(Enum):
    IDLE = auto()
    WAKE_WAIT = auto()
    LISTENING = auto()
    THINKING = auto()
    SPEAKING = auto()


@dataclass
class Turn:
    """1ターンの記録。"""
    user_text: str
    image: Optional[np.ndarray]   # BGR ndarray
    assistant_text: str
    latency_ms: dict = field(default_factory=dict)  # {"stt": x, "llm": y, "tts": z}


# ---------------------------------------------------------------------------
# エージェント本体
# ---------------------------------------------------------------------------

class VisionAudioAgent:
    """
    ローカルマルチモーダル対話エージェント。

    使い方:
        agent = VisionAudioAgent("config.yaml")
        asyncio.run(agent.run_forever())
    """

    def __init__(self, config_path: str = "config.yaml") -> None:
        self.cfg: AppConfig = load_config(config_path)
        setup_logging(self.cfg.logging.level)

        # モジュール初期化（まだロードしない）
        self.camera = CameraCapture(
            index=self.cfg.camera.index,
            width=self.cfg.camera.width,
            height=self.cfg.camera.height,
            capture_fps=self.cfg.camera.capture_fps,
        )
        self.mic = MicStream(device=self.cfg.mic.device)
        self.speaker = Speaker(device=self.cfg.speaker.device)
        self.vad = self._create_vad()
        self.stt = None
        if self.cfg.stt.backend.lower() in {"faster-whisper", "whisper"}:
            self.stt = WhisperSTT(
                model=self.cfg.stt.model,
                compute_type=self.cfg.stt.compute_type,
                language=self.cfg.stt.language,
                local_files_only=self.cfg.stt.local_files_only,
                download_root=self.cfg.stt.download_root,
            )
        self.wake_word = WakeWordDetector(
            aliases=self.cfg.wake_word.aliases,
            enabled=self.cfg.wake_word.enabled,
        )
        self.llm = create_llm(self.cfg.llm)
        self.tts = VoicevoxTTS(
            endpoint=self.cfg.tts.endpoint,
            speaker_id=self.cfg.tts.speaker_id,
        )
        self.memory = ConversationMemory(max_turns=self.cfg.memory.max_turns)
        self.conv_logger = ConversationLogger(
            log_dir=self.cfg.logging.conversation_log_dir,
            save_frames=self.cfg.logging.save_frames,
        )

        self._state: AgentState = AgentState.IDLE
        self._last_response_time: float = 0.0
        self._stop_event = asyncio.Event()
        self.on_state_change: Optional[Callable[[AgentState, AgentState], None]] = None
        self.on_user_text: Optional[Callable[[str], None]] = None
        self.on_turn_complete: Optional[Callable[[Turn], None]] = None

    # ---- ライフサイクル ----

    async def start(self) -> None:
        """全モジュール起動。カメラ・マイクのストリーム開始。"""
        console.rule("[bold green]ローカルモーダルエージェント 起動中...[/bold green]")

        # VOICEVOX 疎通確認
        self.tts.start()
        if not self.tts.is_available():
            logger.warning("VOICEVOX ENGINE が応答しません。TTS は動作しない可能性があります。")

        # モデルロード（重い処理はスレッドプールで）
        loop = asyncio.get_event_loop()
        logger.info("VAD をロード中...")
        await loop.run_in_executor(None, self.vad.load)

        device = "cuda" if "cuda" in self.cfg.device else "cpu"
        if self.stt is not None:
            logger.info("STT をロード中...")
            await loop.run_in_executor(None, lambda: self.stt.load(device=device))
        else:
            logger.info("STT は Gemma backend を使用します")

        logger.info("LLM をロード中...")
        await loop.run_in_executor(None, lambda: self.llm.load(device=self.cfg.device))

        # I/O 起動
        self.camera.start()
        self.mic.start()
        self.mic.active = True

        self._set_state(AgentState.WAKE_WAIT)
        console.rule("[bold green]起動完了。「じろえもん」と話しかけてください[/bold green]")

    async def start_one_turn(self, use_camera: bool = True) -> None:
        """単発テキスト実行に必要な LLM/TTS と、可能ならカメラだけを起動する。"""
        console.rule("[bold green]単発テスト 起動中...[/bold green]")

        self.tts.start()
        if not self.tts.is_available():
            logger.warning("VOICEVOX ENGINE が応答しません。TTS は動作しない可能性があります。")

        loop = asyncio.get_event_loop()
        logger.info("LLM をロード中...")
        await loop.run_in_executor(None, lambda: self.llm.load(device=self.cfg.device))

        if use_camera:
            try:
                self.camera.start()
                for _ in range(20):
                    if self.camera.get_latest() is not None:
                        break
                    await asyncio.sleep(0.1)
                if self.camera.get_latest() is None:
                    logger.warning("カメラフレームを取得できませんでした。画像なしで続行します。")
            except Exception as e:
                logger.warning(f"カメラを起動できませんでした。画像なしで続行します: {e}")

        self._set_state(AgentState.WAKE_WAIT)
        console.rule("[bold green]単発テスト 起動完了[/bold green]")

    async def stop(self) -> None:
        """グレースフルシャットダウン。"""
        self._stop_event.set()
        self.camera.stop()
        self.mic.stop()
        self.tts.stop()
        self.speaker.stop()
        console.rule("[bold red]シャットダウン完了[/bold red]")

    async def run_forever(self) -> None:
        """発話検知→応答までを無限ループで実行。"""
        await self.start()
        loop = asyncio.get_event_loop()

        try:
            while not self._stop_event.is_set():
                # VAD で発話検知（ブロッキング → executor）
                audio = await loop.run_in_executor(
                    None, self._wait_for_utterance
                )
                if audio is None:
                    continue

                await self.process_audio(audio)

        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt 受信")
        finally:
            await self.stop()

    # ---- 単発テスト用 ----

    async def one_turn(self, user_text: str, notify: bool = True) -> Turn:
        """テキストを直接入力して1ターン実行する（マイク不要）。"""
        loop = asyncio.get_event_loop()

        frame = self._frame_for_user_text(user_text)
        timer = LatencyTimer()
        self.conv_logger.log_user(user_text)
        if notify and self.on_user_text:
            self.on_user_text(user_text)

        # STT スキップ（テキスト直接入力）
        timer._results["stt"] = 0

        # LLM
        self._set_state(AgentState.THINKING)
        timer.start("llm")
        messages = self.memory.to_messages(user_text)
        response = await loop.run_in_executor(
            None, lambda: self.llm.generate(messages, frame)
        )
        timer.stop("llm")

        # TTS
        self._set_state(AgentState.SPEAKING)
        timer.start("tts")
        try:
            wav = await loop.run_in_executor(
                None, lambda: self.tts.synthesize(response)
            )
            await loop.run_in_executor(None, lambda: self.speaker.play(wav))
        except Exception as e:
            logger.error(f"TTS エラー: {e}")
        timer.stop("tts")

        self.memory.add(user_text, response)
        self.conv_logger.log_bot(response)
        self._last_response_time = time.monotonic()
        lat = timer.summary()
        turn = Turn(
            user_text=user_text,
            image=frame,
            assistant_text=response,
            latency_ms=lat,
        )
        if notify and self.on_turn_complete:
            self.on_turn_complete(turn)
        self._set_state(AgentState.WAKE_WAIT)
        return turn

    async def process_audio(self, audio: np.ndarray, bypass_wake: bool = False) -> Optional[Turn]:
        """音声1発話を処理する。Web UIでは bypass_wake=True でボタン起動に使う。"""
        return await self._process_turn(audio, bypass_wake=bypass_wake)

    @property
    def state(self) -> AgentState:
        return self._state

    def continuous_remaining_sec(self) -> float:
        """応答後のWake Wordなし連続会話時間の残り秒数。"""
        remaining = self.cfg.wake_word.timeout_after_response_sec - (
            time.monotonic() - self._last_response_time
        )
        return max(0.0, remaining)

    def end_continuous_mode(self) -> None:
        """連続会話モードを終了し、次発話からWake Wordを必須にする。"""
        self._last_response_time = 0.0

    # ---- 内部メソッド ----

    def _set_state(self, state: AgentState) -> None:
        old = self._state
        self._state = state
        if self.on_state_change:
            self.on_state_change(old, state)
        state_colors = {
            AgentState.IDLE: "dim",
            AgentState.WAKE_WAIT: "cyan",
            AgentState.LISTENING: "yellow",
            AgentState.THINKING: "magenta",
            AgentState.SPEAKING: "green",
        }
        color = state_colors.get(state, "white")
        console.print(f"[{color}]◆ {old.name} → {state.name}[/{color}]")

    def _is_continuous_mode(self) -> bool:
        """応答後 timeout 秒以内なら wake word 不要の連続会話モード。"""
        elapsed = time.monotonic() - self._last_response_time
        return elapsed < self.cfg.wake_word.timeout_after_response_sec

    def _wait_for_utterance(self):
        """
        VAD で発話区間を1つ取り出す（同期・ブロッキング）。
        SPEAKING 中はマイクを無視する。
        stop_event がセットされたら None を返す。
        """
        for audio in self.vad.iter_utterances(
            self.mic.queue,
            stop_flag_fn=lambda: self._stop_event.is_set(),
        ):
            # SPEAKING 中は破棄
            if self._state == AgentState.SPEAKING:
                continue
            return audio
        return None

    async def _process_turn(self, audio: np.ndarray, bypass_wake: bool = False) -> Optional[Turn]:
        """1ターンの処理フロー: STT → wake word → LLM → TTS"""
        loop = asyncio.get_event_loop()
        timer = LatencyTimer()

        # ---- STT ----
        self._set_state(AgentState.LISTENING)
        self.mic.active = False  # 処理中はマイク停止

        timer.start("stt")
        stt_text = await loop.run_in_executor(None, lambda: self._transcribe(audio))
        stt_ms = timer.stop("stt")

        if not stt_text:
            logger.debug("STT 結果が空。スキップ。")
            self.mic.active = True
            self._set_state(AgentState.WAKE_WAIT)
            return None
        if self._is_noise_transcript(stt_text):
            logger.info(f"STT の定型幻覚を検知、無視: {stt_text!r}")
            self.mic.active = True
            self._set_state(AgentState.WAKE_WAIT)
            return None

        console.print(f"[yellow]USER (raw): {stt_text}[/yellow]")

        # ---- 言語フィルタ ----
        if self.cfg.language.reject_other:
            if not self._is_japanese(stt_text):
                logger.info(f"日本語以外を検知、無視: {stt_text!r}")
                self.mic.active = True
                self._set_state(AgentState.WAKE_WAIT)
                return None

        # ---- Wake Word ----
        if bypass_wake:
            user_text = stt_text
        elif not self._is_continuous_mode():
            detected, content = self.wake_word.detect(stt_text)
            if not detected:
                logger.debug(f"wake word なし: {stt_text!r}")
                self.mic.active = True
                self._set_state(AgentState.WAKE_WAIT)
                return None
            self.conv_logger.log_wake()
            user_text = content if content else stt_text
        else:
            # 連続会話モード: テキスト全体を使用
            user_text = stt_text

        self.conv_logger.log_user(user_text)
        if self.on_user_text:
            self.on_user_text(user_text)
        console.print(f"[bold yellow]USER: {user_text}[/bold yellow]")

        # フレーム取得・ログ
        frame = self._frame_for_user_text(user_text)
        if frame is not None:
            h, w = frame.shape[:2]
            self.conv_logger.log_image(frame, width=w, height=h)

        # ---- LLM ----
        self._set_state(AgentState.THINKING)
        messages = self.memory.to_messages(user_text)

        timer.start("llm")
        try:
            response = await loop.run_in_executor(
                None, lambda: self.llm.generate(messages, frame)
            )
        except Exception as e:
            logger.error(f"LLM エラー: {e}")
            self.conv_logger.log_error(str(e))
            self.mic.active = True
            self._set_state(AgentState.WAKE_WAIT)
            return None
        llm_ms = timer.stop("llm")

        console.print(f"[bold green]BOT: {response}[/bold green]")
        self.conv_logger.log_bot(response)

        # ---- TTS ----
        self._set_state(AgentState.SPEAKING)
        timer.start("tts")
        try:
            wav = await loop.run_in_executor(
                None, lambda: self.tts.synthesize(response)
            )
            # 再生は同期だが別スレッドで（マイクをブロックしない）
            await loop.run_in_executor(None, lambda: self.speaker.play(wav))
        except Exception as e:
            logger.error(f"TTS エラー: {e}")
        tts_ms = timer.stop("tts")

        # ---- 後処理 ----
        self.memory.add(user_text, response)
        self.conv_logger.log_latency(stt_ms, llm_ms, tts_ms)
        self._last_response_time = time.monotonic()

        total_ms = timer.total_ms()
        console.print(
            f"[dim]⏱ STT={stt_ms}ms LLM={llm_ms}ms TTS={tts_ms}ms total={total_ms}ms[/dim]"
        )

        # マイク再開・フラッシュ（エコー除去）
        await asyncio.sleep(0.4)
        self.mic.flush()
        self.mic.active = True
        self._set_state(AgentState.WAKE_WAIT)

        turn = Turn(
            user_text=user_text,
            image=frame,
            assistant_text=response,
            latency_ms=timer.summary(),
        )
        if self.on_turn_complete:
            self.on_turn_complete(turn)
        return turn

    @staticmethod
    def _is_japanese(text: str) -> bool:
        """テキストに日本語文字（ひらがな/カタカナ/CJK）が含まれるか判定。"""
        for ch in text:
            cp = ord(ch)
            if (
                0x3040 <= cp <= 0x309F  # ひらがな
                or 0x30A0 <= cp <= 0x30FF  # カタカナ
                or 0x4E00 <= cp <= 0x9FFF  # CJK 統合漢字
            ):
                return True
        return False

    def _transcribe(self, audio: np.ndarray) -> str:
        backend = self.cfg.stt.backend.lower()
        if backend in {"faster-whisper", "whisper"}:
            if self.stt is None:
                raise RuntimeError("WhisperSTT が初期化されていません")
            return self.stt.transcribe(audio)
        if backend in {"gemma", "gemma4", "gemma-4"}:
            transcriber = self.llm
            if not hasattr(transcriber, "transcribe"):
                raise RuntimeError("選択中のLLM backendはGemma ASRに対応していません")
            return transcriber.transcribe(  # type: ignore[attr-defined]
                audio,
                language=self.cfg.stt.language,
                sample_rate=16_000,
            )
        raise ValueError(f"Unsupported STT backend: {self.cfg.stt.backend}")

    def _frame_for_user_text(self, user_text: str) -> Optional[np.ndarray]:
        """会話では原則画像を渡さず、視覚参照があるときだけ最新フレームを添える。"""
        if not self.camera.is_running:
            return None
        if not self._should_use_vision(user_text):
            return None
        return self.camera.get_latest_for_llm()

    @staticmethod
    def _should_use_vision(user_text: str) -> bool:
        text = user_text.casefold()
        visual_keywords = [
            "見え",
            "映",
            "写",
            "カメラ",
            "画面",
            "画像",
            "写真",
            "視界",
            "周り",
            "まわり",
            "何がある",
            "なにがある",
            "読ん",
            "文字",
            "色",
            "右",
            "左",
            "前",
            "後ろ",
        ]
        visual_phrases = [
            "これ何",
            "これなに",
            "これは何",
            "これはなに",
            "これ読",
            "これ見",
            "あれ何",
            "あれなに",
            "あれ見",
            "そこ見",
            "ここ見",
            "どれ",
        ]
        return (
            any(keyword in text for keyword in visual_keywords)
            or any(phrase in text for phrase in visual_phrases)
        )

    @staticmethod
    def _is_noise_transcript(text: str) -> bool:
        import re

        normalized = re.sub(r"[\s、。，．,.!！?？]+", "", text.strip())
        noise_phrases = {
            "ご視聴ありがとうございました",
            "ご視聴ありがとうございます",
            "ご清聴ありがとうございました",
            "ご清聴ありがとうございます",
            "ご覧いただきありがとうございます",
            "ありがとうございました",
        }
        return normalized in noise_phrases

    def _create_vad(self):
        backend = self.cfg.vad.backend.lower()
        if backend in {"energy", "simple"}:
            from src.perception.simple_vad import EnergyVAD

            return EnergyVAD(
                threshold=self.cfg.vad.threshold,
                min_speech_ms=self.cfg.vad.min_speech_ms,
                min_silence_ms=self.cfg.vad.min_silence_ms,
                max_speech_ms=self.cfg.vad.max_speech_ms,
            )
        if backend == "silero":
            from src.perception.vad import SileroVAD

            return SileroVAD(
                threshold=self.cfg.vad.threshold,
                min_speech_ms=self.cfg.vad.min_speech_ms,
                min_silence_ms=self.cfg.vad.min_silence_ms,
            )
        raise ValueError(f"Unsupported VAD backend: {self.cfg.vad.backend}")


# ---------------------------------------------------------------------------
# エントリーポイント
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    agent = VisionAudioAgent(config_path)
    try:
        asyncio.run(agent.run_forever())
    except KeyboardInterrupt:
        pass
