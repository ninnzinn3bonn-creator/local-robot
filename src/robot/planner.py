"""Planning boundary between conversation and future robot actuation."""
from __future__ import annotations

from typing import Optional

from src.robot.types import ActionPlan, ActionType, RobotAction, WorldState


class RobotPlanner:
    """
    Converts dialogue results into a conservative robot action plan.

    The current PC-only app never executes motion. This class exists so that
    future motor control, pan/tilt, or arm adapters can be added behind a
    safety gate without mixing hardware commands into the chat loop.
    """

    def plan_reply(
        self,
        user_text: str,
        assistant_text: str,
        world_state: Optional[WorldState] = None,
    ) -> ActionPlan:
        safety_notes: tuple[str, ...] = ()
        if world_state and world_state.hazards:
            safety_notes = tuple(f"hazard: {hazard}" for hazard in world_state.hazards)
        return ActionPlan(
            intent=self._infer_intent(user_text),
            actions=(
                RobotAction(
                    type=ActionType.SAY,
                    params={"text": assistant_text},
                    reason="current app supports speech output only",
                ),
            ),
            safety_notes=safety_notes,
            requires_confirmation=False,
        )

    def idle(self, reason: str = "no robot action requested") -> ActionPlan:
        return ActionPlan(
            intent="idle",
            actions=(RobotAction(type=ActionType.NOOP, reason=reason),),
            requires_confirmation=False,
        )

    @staticmethod
    def _infer_intent(user_text: str) -> str:
        text = user_text.casefold()
        if any(word in text for word in ["動", "行って", "取って", "近づ", "進ん"]):
            return "motion_request"
        if any(word in text for word in ["見て", "読ん", "映", "カメラ"]):
            return "vision_request"
        return "conversation"
