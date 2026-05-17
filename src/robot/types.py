"""Typed data structures for future robot control."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ActionType(str, Enum):
    """Actions the dialogue brain may request from a robot body."""

    NOOP = "noop"
    SAY = "say"
    LOOK = "look"
    MOVE = "move"
    STOP = "stop"
    ASK_CLARIFICATION = "ask_clarification"


@dataclass(frozen=True)
class WorldState:
    """Small, serializable snapshot of what the robot believes is around it."""

    summary: str = ""
    hazards: tuple[str, ...] = ()
    visible_targets: tuple[str, ...] = ()
    confidence: float = 0.0
    timestamp: Optional[float] = None
    source: str = "camera"


@dataclass(frozen=True)
class RobotAction:
    """One requested action before any hardware adapter executes it."""

    type: ActionType
    params: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


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
