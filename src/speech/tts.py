"""
speech/tts.py — VOICEVOX ENGINE への HTTP クライアント。

フロー:
  1. POST /audio_query?text=...&speaker=3  → AudioQuery JSON
  2. POST /synthesis?speaker=3  body=AudioQuery JSON → WAV bytes
  3. WAV bytes を Speaker に渡して再生

VOICEVOX ENGINE はローカルポート 50021 で起動済みであることを前提とする。
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 12.0  # 秒


class VoicevoxTTS:
    """
    VOICEVOX TTS クライアント。

    使い方:
        tts = VoicevoxTTS(endpoint="http://127.0.0.1:50021", speaker_id=3)
        wav = tts.synthesize("こんにちは、ずんだもんなのだ！")
        # wav: bytes (WAV)
    """

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:50021",
        speaker_id: int = 3,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._speaker_id = speaker_id
        self._timeout = timeout
        self._client: Optional[httpx.Client] = None

    # ---- lifecycle ----

    def start(self) -> None:
        """HTTP クライアントを初期化する。"""
        self._client = httpx.Client(timeout=self._timeout)
        logger.info(f"VOICEVOX クライアント起動: {self._endpoint}, speaker={self._speaker_id}")

    def stop(self) -> None:
        """HTTP クライアントを閉じる。"""
        if self._client:
            self._client.close()
            self._client = None

    @property
    def endpoint(self) -> str:
        return self._endpoint

    @property
    def speaker_id(self) -> int:
        return self._speaker_id

    # ---- public API ----

    def synthesize(self, text: str) -> bytes:
        """
        テキストを音声合成して WAV バイト列を返す。

        Raises:
            RuntimeError: VOICEVOX ENGINE との通信に失敗した場合
        """
        if not self._client:
            raise RuntimeError("VoicevoxTTS.start() を先に呼んでください")

        text = text.strip()
        if not text:
            raise ValueError("合成するテキストが空です")

        # Step 1: audio_query
        try:
            r = self._client.post(
                f"{self._endpoint}/audio_query",
                params={"text": text, "speaker": self._speaker_id},
            )
            r.raise_for_status()
            audio_query = r.json()
        except httpx.HTTPError as e:
            raise RuntimeError(f"audio_query 失敗: {e}") from e

        # Step 2: synthesis
        try:
            r = self._client.post(
                f"{self._endpoint}/synthesis",
                params={"speaker": self._speaker_id},
                json=audio_query,
                headers={"Content-Type": "application/json"},
            )
            r.raise_for_status()
            wav_bytes = r.content
        except httpx.HTTPError as e:
            raise RuntimeError(f"synthesis 失敗: {e}") from e

        logger.debug(f"TTS 合成完了: {len(text)} 文字 → {len(wav_bytes)} bytes")
        return wav_bytes

    def is_available(self) -> bool:
        """VOICEVOX ENGINE が起動しているか確認する。"""
        if not self._client:
            return False
        try:
            r = self._client.get(f"{self._endpoint}/version", timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False
