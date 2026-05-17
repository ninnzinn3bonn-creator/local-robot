"""Planning boundary between conversation and future robot actuation."""
from __future__ import annotations

import time
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
        intent = self._infer_intent(user_text)
        actions: list[RobotAction] = [
            RobotAction(
                type=ActionType.SAY,
                params={"text": assistant_text},
                reason="音声返答を行う",
            )
        ]
        requires_confirmation = False

        if intent == "stop_request":
            actions.insert(
                0,
                RobotAction(
                    type=ActionType.STOP,
                    reason="ユーザーが停止を要求した",
                ),
            )
        elif intent == "motion_request":
            actions.append(
                RobotAction(
                    type=ActionType.MOVE,
                    params={
                        "command": "forward_slow",
                        "speed": "low",
                        "duration_sec": 2,
                    },
                    reason="用水路内ではまず微速短時間の移動だけを提案する",
                )
            )
            requires_confirmation = True
        elif intent == "cleaning_request":
            actions.append(
                RobotAction(
                    type=ActionType.CLEAN,
                    params={"tool": "brush", "state": "on"},
                    reason="清掃機構は走行系と分けて提案する",
                )
            )
            requires_confirmation = True

        safety_notes = (
            "実機接続前のため、移動/清掃はSafety Gateと確認を通す",
        )
        if world_state and world_state.hazards:
            safety_notes = safety_notes + tuple(
                f"hazard: {hazard}" for hazard in world_state.hazards
            )
        return ActionPlan(
            intent=intent,
            actions=tuple(actions),
            safety_notes=safety_notes,
            requires_confirmation=requires_confirmation,
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
        if any(word in text for word in ["止ま", "停止", "ストップ", "緊急停止"]):
            return "stop_request"
        if any(word in text for word in ["掃除", "清掃", "ブラシ", "片付", "回収", "除去", "詰まりを取"]):
            return "cleaning_request"
        if any(word in text for word in ["動", "行って", "取って", "近づ", "進ん", "前進", "後退"]):
            return "motion_request"
        if any(word in text for word in ["見て", "読ん", "映", "カメラ", "見える", "あるか", "確認"]):
            return "vision_request"
        return "conversation"

    @staticmethod
    def world_state_from_observation(observation: str) -> WorldState:
        """Create a conservative waterway-oriented state from a VLM note."""
        text = observation.strip()
        if not text:
            return WorldState(source="vision_observation")

        affirmative_text = _affirmative_text(text)
        hazards = _pick_terms(
            affirmative_text,
            {
                "障害物": "前方障害物の可能性",
                "枝": "枝または細長い障害物",
                "石": "石または硬い障害物",
                "段差": "段差",
                "壁が近": "壁面が近い可能性",
                "壁面が近": "壁面が近い可能性",
                "接触": "接触リスク",
                "人": "人が近くにいる可能性",
                "人物": "人が近くにいる可能性",
                "濁": "水の濁り",
                "暗": "視界不良",
                "不明": "視界または対象が不明",
            },
        )
        debris = _pick_terms(
            affirmative_text,
            {
                "ゴミ": "ゴミ",
                "ごみ": "ゴミ",
                "落ち葉": "落ち葉",
                "泥": "泥",
                "藻": "藻",
                "枝": "枝",
                "詰まり": "詰まり候補",
            },
        )
        water_conditions = _pick_terms(
            affirmative_text,
            {
                "水": "水面",
                "濡": "濡れ",
                "泡": "泡",
                "流れ": "流れ",
                "濁": "濁り",
            },
        )
        channel_edges = _pick_terms(
            affirmative_text,
            {
                "左": "左側の境界",
                "右": "右側の境界",
                "壁": "壁面",
                "水路": "水路境界",
                "用水路": "用水路境界",
            },
        )
        visible_targets = tuple(dict.fromkeys((*debris, *channel_edges)))
        confidence = 0.35
        if visible_targets:
            confidence += 0.25
        if "不明" not in text and "見当たらない" not in text:
            confidence += 0.2

        return WorldState(
            summary=text[:240],
            hazards=hazards,
            visible_targets=visible_targets,
            debris=debris,
            water_conditions=water_conditions,
            channel_edges=channel_edges,
            confidence=min(confidence, 0.9),
            timestamp=time.time(),
            source="vision_observation",
        )


def _pick_terms(text: str, mapping: dict[str, str]) -> tuple[str, ...]:
    found: list[str] = []
    for needle, label in mapping.items():
        if needle in text and label not in found:
            found.append(label)
    return tuple(found)


def _affirmative_text(text: str) -> str:
    """Drop observation lines that explicitly say the target is not visible."""
    negative_markers = ("見えない", "見当たらない", "確認されていない", "不明")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    kept = [
        line for line in lines
        if not any(marker in line for marker in negative_markers)
    ]
    return "\n".join(kept)
