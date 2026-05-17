"""Mission state machine for waterway cleaning operations."""
from __future__ import annotations

import time

from src.robot.types import MissionPhase, MissionState


class MissionController:
    """Tracks a cleaning mission independently from the chat session."""

    def __init__(self) -> None:
        self.state = MissionState(updated_at=time.time())

    def start(self, target_distance_m: float = 0.0, note: str = "用水路清掃を開始") -> MissionState:
        now = time.time()
        self.state = MissionState(
            phase=MissionPhase.INSPECTION,
            target_distance_m=max(0.0, float(target_distance_m)),
            cleaned_distance_m=0.0,
            started_at=now,
            updated_at=now,
            note=note,
        )
        return self.state

    def pause(self, note: str = "一時停止") -> MissionState:
        self.state.phase = MissionPhase.PAUSED
        self.state.note = note
        self.state.updated_at = time.time()
        return self.state

    def resume(self, note: str = "点検後に再開") -> MissionState:
        if self.state.phase in {MissionPhase.IDLE, MissionPhase.FINISHED}:
            return self.start(note=note)
        self.state.phase = MissionPhase.NAVIGATING
        self.state.note = note
        self.state.updated_at = time.time()
        return self.state

    def cleaning(self, note: str = "清掃中") -> MissionState:
        if self.state.phase in {MissionPhase.IDLE, MissionPhase.FINISHED}:
            self.start(note=note)
        self.state.phase = MissionPhase.CLEANING
        self.state.note = note
        self.state.updated_at = time.time()
        return self.state

    def finish(self, note: str = "作業完了") -> MissionState:
        self.state.phase = MissionPhase.FINISHED
        self.state.note = note
        self.state.updated_at = time.time()
        return self.state

    def estop(self, note: str = "緊急停止") -> MissionState:
        self.state.phase = MissionPhase.ESTOP
        self.state.note = note
        self.state.updated_at = time.time()
        return self.state

    def add_distance(self, meters: float) -> MissionState:
        self.state.cleaned_distance_m = max(
            0.0,
            self.state.cleaned_distance_m + float(meters),
        )
        self.state.updated_at = time.time()
        return self.state
