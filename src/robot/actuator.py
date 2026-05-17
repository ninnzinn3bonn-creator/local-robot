"""Dummy actuator adapter for the waterway robot console."""
from __future__ import annotations

import time

from src.robot.safety import SafetyGate
from src.robot.types import ActuatorResult, RobotTelemetry, WorldState


class DummyActuator:
    """Simulates the actuator boundary until real motor hardware exists."""

    def __init__(self, safety_gate: SafetyGate) -> None:
        self._safety_gate = safety_gate
        self.telemetry = RobotTelemetry(updated_at=time.time())

    def execute(self, command: str, world_state: WorldState | None = None) -> ActuatorResult:
        command = command.strip().casefold()
        safety = self._safety_gate.evaluate(command, self.telemetry, world_state)
        if not safety.ok:
            self._apply_stop("; ".join(safety.reasons) or "safety blocked")
            return ActuatorResult(
                accepted=False,
                command=command,
                message="Safety Gateがコマンドを拒否しました",
                safety=safety,
            )

        if command == "stop":
            self._apply_stop("operator stop")
            message = "停止しました"
        elif command == "forward":
            self._apply_drive("forward_slow")
            message = "微速前進をシミュレーションしました"
        elif command == "reverse":
            self._apply_drive("reverse_short")
            message = "短い後退をシミュレーションしました"
        elif command == "turn_left":
            self._apply_drive("turn_left_small")
            message = "左へ小さく旋回する想定です"
        elif command == "turn_right":
            self._apply_drive("turn_right_small")
            message = "右へ小さく旋回する想定です"
        elif command == "clean_on":
            self.telemetry.cleaning_state = "on"
            self.telemetry.last_command = command
            self.telemetry.updated_at = time.time()
            message = "清掃機構ONをシミュレーションしました"
        elif command == "clean_off":
            self.telemetry.cleaning_state = "off"
            self.telemetry.last_command = command
            self.telemetry.updated_at = time.time()
            message = "清掃機構OFFをシミュレーションしました"
        elif command == "lights_toggle":
            self.telemetry.lights = not self.telemetry.lights
            self.telemetry.last_command = command
            self.telemetry.updated_at = time.time()
            message = "ライト状態を切り替えました"
        else:
            return ActuatorResult(
                accepted=False,
                command=command,
                message=f"未知のコマンドです: {command}",
                safety=safety,
            )

        return ActuatorResult(
            accepted=True,
            command=command,
            message=message,
            safety=safety,
        )

    def emergency_stop(self, reason: str = "operator estop") -> ActuatorResult:
        safety = self._safety_gate.trigger_estop(reason)
        self._apply_stop(reason)
        return ActuatorResult(
            accepted=True,
            command="estop",
            message="緊急停止を有効化しました",
            safety=safety,
        )

    def reset_estop(self) -> ActuatorResult:
        safety = self._safety_gate.reset_estop()
        self.telemetry.last_stop_reason = "estop reset"
        self.telemetry.updated_at = time.time()
        return ActuatorResult(
            accepted=True,
            command="reset_estop",
            message="緊急停止を解除しました",
            safety=safety,
        )

    def _apply_drive(self, state: str) -> None:
        self.telemetry.drive_state = state
        self.telemetry.motors_enabled = True
        self.telemetry.last_command = state
        self.telemetry.last_stop_reason = ""
        self.telemetry.updated_at = time.time()

    def _apply_stop(self, reason: str) -> None:
        self.telemetry.drive_state = "stopped"
        self.telemetry.motors_enabled = False
        self.telemetry.last_command = "stop"
        self.telemetry.last_stop_reason = reason
        self.telemetry.updated_at = time.time()
