"""Typed data structures for future robot control."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class ActionType(str, Enum):
    """Actions the dialogue brain may request from a robot body."""

    NOOP = "noop"
    SAY = "say"
    LOOK = "look"
    MOVE = "move"
    STOP = "stop"
    CLEAN = "clean"
    LIGHT = "light"
    ASK_CLARIFICATION = "ask_clarification"


class MissionPhase(str, Enum):
    """High-level operating phase for the waterway cleaning robot."""

    IDLE = "idle"
    INSPECTION = "inspection"
    NAVIGATING = "navigating"
    CLEANING = "cleaning"
    PAUSED = "paused"
    ESTOP = "estop"
    FINISHED = "finished"


@dataclass(frozen=True)
class WorldState:
    """Small, serializable snapshot of what the robot believes is around it."""

    summary: str = ""
    hazards: tuple[str, ...] = ()
    visible_targets: tuple[str, ...] = ()
    debris: tuple[str, ...] = ()
    water_conditions: tuple[str, ...] = ()
    channel_edges: tuple[str, ...] = ()
    confidence: float = 0.0
    timestamp: Optional[float] = None
    source: str = "camera"

    def to_dict(self) -> dict[str, Any]:
        return _to_jsonable(asdict(self))


@dataclass(frozen=True)
class RobotAction:
    """One requested action before any hardware adapter executes it."""

    type: ActionType
    params: dict[str, Any] = field(default_factory=dict)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _to_jsonable(asdict(self))


@dataclass(frozen=True)
class ActionPlan:
    """A safety-checkable plan emitted by the robot planning layer."""

    intent: str
    actions: tuple[RobotAction, ...] = ()
    safety_notes: tuple[str, ...] = ()
    requires_confirmation: bool = False

    @property
    def is_motion_plan(self) -> bool:
        return any(action.type == ActionType.MOVE for action in self.actions)

    def to_dict(self) -> dict[str, Any]:
        return _to_jsonable(asdict(self))


@dataclass(frozen=True)
class SafetyStatus:
    """Result of checking whether a command may reach the actuator layer."""

    ok: bool = True
    estop_active: bool = False
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _to_jsonable(asdict(self))


@dataclass
class RobotTelemetry:
    """Operator-facing robot telemetry.

    Values are simulated until a microcontroller/ROS adapter is connected.
    """

    battery_percent: int = 100
    comms: str = "local-sim"
    control_mode: str = "manual"
    drive_state: str = "stopped"
    cleaning_state: str = "off"
    lights: bool = False
    motors_enabled: bool = False
    tilt_deg: float = 0.0
    water_detected: bool = False
    last_command: str = "none"
    last_stop_reason: str = "startup"
    updated_at: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return _to_jsonable(asdict(self))


@dataclass
class MissionState:
    """Waterway cleaning mission state for the operator console."""

    phase: MissionPhase = MissionPhase.IDLE
    target_distance_m: float = 0.0
    cleaned_distance_m: float = 0.0
    started_at: Optional[float] = None
    updated_at: Optional[float] = None
    note: str = "待機中"

    def to_dict(self) -> dict[str, Any]:
        return _to_jsonable(asdict(self))


@dataclass(frozen=True)
class ActuatorResult:
    """Result from the dummy or real actuator adapter."""

    accepted: bool
    command: str
    message: str
    safety: SafetyStatus = field(default_factory=SafetyStatus)

    def to_dict(self) -> dict[str, Any]:
        return _to_jsonable(asdict(self))


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    return value
