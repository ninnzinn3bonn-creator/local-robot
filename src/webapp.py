"""
webapp.py - Local browser UI for the multimodal agent.

The server uses only Python's standard library. Browser requests stay on
127.0.0.1 and the existing agent keeps using local Ollama, VOICEVOX, camera,
and microphone devices.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import mimetypes
import threading
import time
import traceback
from concurrent.futures import TimeoutError
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import cv2  # type: ignore

from src.agent import AgentState, Turn, VisionAudioAgent
from src.robot import DummyActuator, MissionController, SafetyGate
from src.utils.encoding import configure_utf8_stdio

configure_utf8_stdio()

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"


STATE_LABELS = {
    "IDLE": "停止中",
    "WAKE_WAIT": "ウェイクワード待機中",
    "LISTENING": "聞き取り中",
    "THINKING": "考え中",
    "SPEAKING": "返答を読み上げ中",
}


@dataclass
class ChatMessage:
    id: int
    role: str
    text: str
    timestamp: float = field(default_factory=time.time)
    latency_ms: Optional[dict[str, int]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "text": self.text,
            "timestamp": self.timestamp,
            "latencyMs": self.latency_ms,
        }


class WebRuntime:
    """Owns the agent and exposes a thread-safe snapshot for HTTP handlers."""

    def __init__(self, config_path: str) -> None:
        self.agent = VisionAudioAgent(config_path)
        self.agent.on_state_change = self._on_state_change
        self.agent.on_user_text = self._on_user_text
        self.agent.on_turn_complete = self._on_turn_complete

        self._lock = threading.RLock()
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="web-agent")
        self._message_id = 0
        self._messages: list[ChatMessage] = []
        self._ready = False
        self._error: Optional[str] = None
        self._status_text = "起動中"
        self._manual_armed = False
        self._manual_expires_at = 0.0
        self._last_state = self.agent.state.name
        self._turn_lock = asyncio.Lock()
        self._safety_gate = SafetyGate()
        self._actuator = DummyActuator(self._safety_gate)
        self._mission = MissionController()
        self._events: list[dict[str, Any]] = []

    def start(self) -> None:
        self._add_message("system", "起動中です。モデルとデバイスを準備しています。")
        self._thread.start()

    def arm_manual_listen(self, timeout_sec: float = 20.0) -> dict[str, Any]:
        with self._lock:
            self._manual_armed = True
            self._manual_expires_at = time.monotonic() + timeout_sec
            self._status_text = "ボタン起動: マイクに話しかけてください"
            self.agent.mic.flush()
            self.agent.mic.active = True
        return self.snapshot()

    def end_conversation(self) -> dict[str, Any]:
        with self._lock:
            self._manual_armed = False
            self._manual_expires_at = 0.0
            self.agent.end_continuous_mode()
            self.agent.mic.flush()
            self._status_text = "会話を終了しました。次はウェイクワードまたはボタンで開始します"
        return self.snapshot()

    def clear_messages(self) -> dict[str, Any]:
        with self._lock:
            self._messages.clear()
            self._add_message("system", "チャット表示を消去しました。")
        return self.snapshot()

    def emergency_stop(self, reason: str = "operator estop") -> dict[str, Any]:
        with self._lock:
            result = self._actuator.emergency_stop(reason)
            self._mission.estop(reason)
            self.agent.end_continuous_mode()
            self._manual_armed = False
            self._manual_expires_at = 0.0
            self._status_text = "緊急停止中。周囲確認後に解除してください"
            self._add_event("estop", result.message)
        return self.snapshot()

    def reset_estop(self) -> dict[str, Any]:
        with self._lock:
            result = self._actuator.reset_estop()
            self._mission.pause("緊急停止を解除。再開待ち")
            self._status_text = "緊急停止を解除しました"
            self._add_event("estop_reset", result.message)
        return self.snapshot()

    def manual_control(self, command: str) -> dict[str, Any]:
        with self._lock:
            result = self._actuator.execute(command, self.agent.last_world_state)
            if command == "stop":
                self._mission.pause("手動停止")
            elif result.accepted and command == "clean_on":
                self._mission.cleaning("清掃機構ON")
            elif result.accepted and command == "clean_off":
                self._mission.resume("清掃機構OFF、走行待ち")
            elif result.accepted and command in {"forward", "reverse", "turn_left", "turn_right"}:
                self._mission.resume("手動微速操作")
            self._status_text = result.message
            self._add_event("manual_control", result.message, {"command": command})
        return self.snapshot()

    def mission_command(self, command: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        payload = payload or {}
        with self._lock:
            if command == "start":
                self._mission.start(
                    target_distance_m=float(payload.get("targetDistanceM") or 0.0),
                    note="用水路清掃ミッション開始",
                )
                self._add_event("mission", "ミッションを開始しました")
            elif command == "pause":
                self._mission.pause("オペレーターが一時停止")
                self._actuator.execute("stop", self.agent.last_world_state)
                self._add_event("mission", "ミッションを一時停止しました")
            elif command == "resume":
                self._mission.resume("オペレーターが再開")
                self._add_event("mission", "ミッションを再開しました")
            elif command == "finish":
                self._mission.finish("オペレーターが完了")
                self._actuator.execute("stop", self.agent.last_world_state)
                self._add_event("mission", "ミッションを完了しました")
            else:
                self._add_event("mission_error", f"未知のミッション操作: {command}")
            self._status_text = self._mission.state.note
        return self.snapshot()

    def submit_text(self, text: str) -> dict[str, Any]:
        text = text.strip()
        if not text:
            return self.snapshot()
        with self._lock:
            self.agent.mic.active = False
            self.agent.mic.flush()
            self._manual_armed = False
            self._manual_expires_at = 0.0
            self._status_text = "テキスト入力を処理しています"
            self._add_message("user", text)
        future = asyncio.run_coroutine_threadsafe(self._submit_text_async(text), self._loop)
        try:
            future.result(timeout=0.05)
        except TimeoutError:
            pass
        return self.snapshot()

    def frame_jpeg(self) -> Optional[bytes]:
        frame = self.agent.camera.get_latest()
        if frame is None:
            return None
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if not ok:
            return None
        return encoded.tobytes()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            self._expire_manual_locked()
            state = self.agent.state.name
            continuous_remaining = self.agent.continuous_remaining_sec()
            manual_remaining = max(0.0, self._manual_expires_at - time.monotonic())
            label = STATE_LABELS.get(state, state)
            if self._manual_armed and state == AgentState.WAKE_WAIT.name:
                label = "ボタン起動: 発話待ち"

            return {
                "ready": self._ready,
                "error": self._error,
                "state": state,
                "stateLabel": label,
                "statusText": self._status_text,
                "manualArmed": self._manual_armed,
                "manualRemainingSec": round(manual_remaining, 1),
                "continuousRemainingSec": round(continuous_remaining, 1),
                "continuousLimitSec": self.agent.cfg.wake_word.timeout_after_response_sec,
                "wakeWord": self.agent.cfg.wake_word.phrase,
                "cameraRunning": self.agent.camera.is_running,
                "messages": [message.to_dict() for message in self._messages[-80:]],
                "robot": self._robot_snapshot_locked(),
            }

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._agent_loop())

    async def _agent_loop(self) -> None:
        try:
            await self.agent.start()
            with self._lock:
                self._ready = True
                self._status_text = "起動完了。ウェイクワードまたはボタンで開始できます"
            self._add_message("system", "起動完了。左の映像を見ながら会話できます。")

            loop = asyncio.get_event_loop()
            while not self.agent._stop_event.is_set():
                self._expire_manual()
                audio = await loop.run_in_executor(None, self.agent._wait_for_utterance)
                if audio is None:
                    continue
                bypass_wake = self._consume_manual()
                async with self._turn_lock:
                    await self.agent.process_audio(audio, bypass_wake=bypass_wake)
        except Exception as exc:
            logger.exception("Web agent loop failed")
            with self._lock:
                self._error = f"{exc}"
                self._status_text = "エラーが発生しました"
            self._add_message("system", "エラーが発生しました。コンソールログを確認してください。")
            traceback.print_exc()
        finally:
            try:
                await self.agent.stop()
            except Exception:
                logger.exception("Agent shutdown failed")

    def _consume_manual(self) -> bool:
        with self._lock:
            self._expire_manual_locked()
            if not self._manual_armed:
                return False
            self._manual_armed = False
            self._manual_expires_at = 0.0
            self._status_text = "ボタン起動の発話を処理しています"
            return True

    async def _submit_text_async(self, text: str) -> None:
        async with self._turn_lock:
            self.agent.mic.active = False
            self._manual_armed = False
            self._manual_expires_at = 0.0
            try:
                turn = await self.agent.one_turn(text, notify=False)
                self._add_message("assistant", turn.assistant_text, latency_ms=turn.latency_ms)
            finally:
                await asyncio.sleep(0.4)
                self.agent.mic.flush()
                self.agent.mic.active = True

    def _expire_manual(self) -> None:
        with self._lock:
            self._expire_manual_locked()

    def _expire_manual_locked(self) -> None:
        if self._manual_armed and time.monotonic() >= self._manual_expires_at:
            self._manual_armed = False
            self._manual_expires_at = 0.0
            self._status_text = "ボタン起動の待機時間が終了しました"

    def _on_state_change(self, _old: AgentState, new: AgentState) -> None:
        with self._lock:
            self._last_state = new.name
            if new == AgentState.WAKE_WAIT and not self._manual_armed:
                remaining = self.agent.continuous_remaining_sec()
                if remaining > 0:
                    self._status_text = "応答後の連続会話を受け付けています"
                else:
                    self._status_text = "ウェイクワード待機中"
            else:
                self._status_text = STATE_LABELS.get(new.name, new.name)

    def _on_user_text(self, text: str) -> None:
        self._add_message("user", text)

    def _on_turn_complete(self, turn: Turn) -> None:
        self._add_message("assistant", turn.assistant_text, latency_ms=turn.latency_ms)

    def _add_message(
        self,
        role: str,
        text: str,
        latency_ms: Optional[dict[str, int]] = None,
    ) -> None:
        with self._lock:
            self._message_id += 1
            self._messages.append(
                ChatMessage(
                    id=self._message_id,
                    role=role,
                    text=text,
                    latency_ms=latency_ms,
                )
            )

    def _robot_snapshot_locked(self) -> dict[str, Any]:
        telemetry = self._actuator.telemetry
        safety = self._safety_gate.evaluate(
            "status",
            telemetry,
            self.agent.last_world_state,
        )
        return {
            "telemetry": telemetry.to_dict(),
            "safety": safety.to_dict(),
            "mission": self._mission.state.to_dict(),
            "lastObservation": self.agent.last_observation,
            "worldState": self.agent.last_world_state.to_dict(),
            "actionPlan": self.agent.last_action_plan.to_dict(),
            "events": self._events[-20:],
        }

    def _add_event(
        self,
        kind: str,
        message: str,
        data: Optional[dict[str, Any]] = None,
    ) -> None:
        self._events.append(
            {
                "timestamp": time.time(),
                "kind": kind,
                "message": message,
                "data": data or {},
            }
        )


class LocalRobotHandler(BaseHTTPRequestHandler):
    runtime: WebRuntime

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            self._serve_static(WEB_DIR / "index.html")
            return
        if path == "/api/state":
            self._send_json(self.runtime.snapshot())
            return
        if path == "/api/frame.jpg":
            frame = self.runtime.frame_jpeg()
            if frame is None:
                self._send_text("No frame yet", HTTPStatus.SERVICE_UNAVAILABLE)
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(frame)))
            self.end_headers()
            self.wfile.write(frame)
            return
        if path.startswith("/static/"):
            self._serve_static(WEB_DIR / path.removeprefix("/static/"))
            return
        self._send_text("Not found", HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/listen":
            self._send_json(self.runtime.arm_manual_listen())
            return
        if path == "/api/end-session":
            self._send_json(self.runtime.end_conversation())
            return
        if path == "/api/clear":
            self._send_json(self.runtime.clear_messages())
            return
        if path == "/api/estop":
            self._send_json(self.runtime.emergency_stop())
            return
        if path == "/api/estop/reset":
            self._send_json(self.runtime.reset_estop())
            return
        if path == "/api/manual-control":
            try:
                payload = self._read_json()
                command = str(payload.get("command", ""))
            except Exception as exc:
                self._send_text(f"Bad request: {exc}", HTTPStatus.BAD_REQUEST)
                return
            self._send_json(self.runtime.manual_control(command))
            return
        if path.startswith("/api/mission/"):
            command = path.removeprefix("/api/mission/")
            payload = {}
            if command == "start":
                try:
                    payload = self._read_json()
                except Exception as exc:
                    self._send_text(f"Bad request: {exc}", HTTPStatus.BAD_REQUEST)
                    return
            self._send_json(self.runtime.mission_command(command, payload))
            return
        if path == "/api/text":
            try:
                payload = self._read_json()
                text = str(payload.get("text", ""))
            except Exception as exc:
                self._send_text(f"Bad request: {exc}", HTTPStatus.BAD_REQUEST)
                return
            self._send_json(self.runtime.submit_text(text))
            return
        self._send_text("Not found", HTTPStatus.NOT_FOUND)

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.debug("web: " + fmt, *args)

    def _serve_static(self, path: Path) -> None:
        try:
            resolved = path.resolve()
            web_root = WEB_DIR.resolve()
            if web_root not in resolved.parents and resolved != web_root:
                self._send_text("Forbidden", HTTPStatus.FORBIDDEN)
                return
            if not resolved.exists() or not resolved.is_file():
                self._send_text("Not found", HTTPStatus.NOT_FOUND)
                return
            content = resolved.read_bytes()
            mime = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
            if resolved.suffix == ".js":
                mime = "text/javascript; charset=utf-8"
            elif resolved.suffix in {".html", ".css"}:
                mime = f"text/{resolved.suffix[1:]}; charset=utf-8"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except OSError as exc:
            self._send_text(f"Static file error: {exc}", HTTPStatus.INTERNAL_SERVER_ERROR)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON object expected")
        return data

    def _send_text(self, text: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Local robot web UI")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    runtime = WebRuntime(args.config)
    runtime.start()

    LocalRobotHandler.runtime = runtime
    server = ThreadingHTTPServer((args.host, args.port), LocalRobotHandler)
    print(f"Web UI: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
