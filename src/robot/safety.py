"""Conservative safety gate for waterway robot commands."""
from __future__ import annotations

from src.robot.types import RobotTelemetry, SafetyStatus, WorldState


MOTION_COMMANDS = {
    "forward",
    "reverse",
    "turn_left",
    "turn_right",
    "forward_slow",
    "reverse_short",
}


class SafetyGate:
    """Blocks actuator commands when the operator console is unsafe."""

    def __init__(self) -> None:
        self._estop_active = False
        self._last_reason = "startup"

    def trigger_estop(self, reason: str = "operator estop") -> SafetyStatus:
        self._estop_active = True
        self._last_reason = reason
        return self.status(reasons=(reason,))

    def reset_estop(self) -> SafetyStatus:
        self._estop_active = False
        self._last_reason = "estop reset"
        return self.status(warnings=("実機接続時は周囲確認後に再開してください",))

    def status(
        self,
        reasons: tuple[str, ...] = (),
        warnings: tuple[str, ...] = (),
    ) -> SafetyStatus:
        return SafetyStatus(
            ok=not self._estop_active and not reasons,
            estop_active=self._estop_active,
            reasons=reasons,
            warnings=warnings,
        )

    def evaluate(
        self,
        command: str,
        telemetry: RobotTelemetry,
        world_state: WorldState | None = None,
    ) -> SafetyStatus:
        """Return whether a command is safe enough for the actuator layer."""
        command = command.strip().casefold()
        reasons: list[str] = []
        warnings: list[str] = []

        if self._estop_active and command not in {"stop", "reset_estop"}:
            reasons.append("緊急停止中")
        if telemetry.comms not in {"local-sim", "ok"}:
            reasons.append("通信状態が正常ではありません")
        if telemetry.battery_percent <= 15 and command in MOTION_COMMANDS:
            reasons.append("バッテリー低下のため移動不可")
        if abs(telemetry.tilt_deg) >= 30 and command in MOTION_COMMANDS:
            reasons.append("姿勢異常のため移動不可")
        if world_state and world_state.hazards and command in MOTION_COMMANDS:
            warnings.extend(f"視覚警告: {hazard}" for hazard in world_state.hazards)

        ok = not reasons
        return SafetyStatus(
            ok=ok,
            estop_active=self._estop_active,
            reasons=tuple(reasons),
            warnings=tuple(warnings),
        )

    @property
    def estop_active(self) -> bool:
        return self._estop_active

    @property
    def last_reason(self) -> str:
        return self._last_reason
