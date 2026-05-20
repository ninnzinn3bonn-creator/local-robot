import unittest

from src.robot import (
    ActionType,
    DummyActuator,
    MissionController,
    MissionPhase,
    RobotPlanner,
    SafetyGate,
    WorldState,
)
from src.robot.voice_commands import parse_operator_command


class RobotPlannerTests(unittest.TestCase):
    def test_reply_plan_speaks_without_motion(self):
        planner = RobotPlanner()

        plan = planner.plan_reply("机の上を見て", "うん、確認するね。")

        self.assertFalse(plan.is_motion_plan)
        self.assertEqual(plan.intent, "vision_request")
        self.assertEqual(plan.actions[0].type, ActionType.SAY)

    def test_world_hazards_are_carried_to_safety_notes(self):
        planner = RobotPlanner()
        state = WorldState(hazards=("机の脚が近い",))

        plan = planner.plan_reply("右に動いて", "今は少し危ないかも。", state)

        self.assertEqual(plan.intent, "motion_request")
        self.assertIn("hazard: 机の脚が近い", plan.safety_notes)
        self.assertTrue(plan.requires_confirmation)
        self.assertTrue(plan.is_motion_plan)

    def test_cleaning_request_adds_clean_action(self):
        planner = RobotPlanner()

        plan = planner.plan_reply("用水路のゴミを掃除して", "安全確認してからね。")

        self.assertEqual(plan.intent, "cleaning_request")
        self.assertTrue(plan.requires_confirmation)
        self.assertIn(ActionType.CLEAN, [action.type for action in plan.actions])

    def test_debris_question_is_vision_not_cleaning_request(self):
        planner = RobotPlanner()

        plan = planner.plan_reply("用水路のゴミや障害物が見えるか確認して", "見てみるね。")

        self.assertEqual(plan.intent, "vision_request")
        self.assertNotIn(ActionType.CLEAN, [action.type for action in plan.actions])

    def test_stop_request_adds_stop_without_confirmation(self):
        planner = RobotPlanner()

        plan = planner.plan_reply("すぐ停止して", "止まるね。")

        self.assertEqual(plan.intent, "stop_request")
        self.assertFalse(plan.requires_confirmation)
        self.assertEqual(plan.actions[0].type, ActionType.STOP)

    def test_world_state_from_observation_extracts_waterway_terms(self):
        planner = RobotPlanner()

        state = planner.world_state_from_observation("右の壁が近く、前方に枝とゴミがあります。水は濁っています。")

        self.assertIn("壁面が近い可能性", state.hazards)
        self.assertIn("枝", state.debris)
        self.assertIn("ゴミ", state.visible_targets)
        self.assertIn("濁り", state.water_conditions)

    def test_world_state_ignores_negated_observation_terms(self):
        planner = RobotPlanner()

        state = planner.world_state_from_observation(
            "- 枝：見えない\n- ゴミ：見えない\n- 段差：見えない\n- 壁面：灰色の壁"
        )

        self.assertEqual(state.debris, ())
        self.assertNotIn("枝または細長い障害物", state.hazards)
        self.assertNotIn("段差", state.hazards)
        self.assertIn("壁面", state.channel_edges)

    def test_safety_gate_blocks_motion_during_estop(self):
        safety = SafetyGate()
        actuator = DummyActuator(safety)

        safety.trigger_estop()
        result = actuator.execute("forward")

        self.assertFalse(result.accepted)
        self.assertTrue(result.safety.estop_active)
        self.assertEqual(actuator.telemetry.drive_state, "stopped")

    def test_dummy_actuator_updates_cleaning_state(self):
        actuator = DummyActuator(SafetyGate())

        result = actuator.execute("clean_on")

        self.assertTrue(result.accepted)
        self.assertEqual(actuator.telemetry.cleaning_state, "on")

    def test_mission_controller_lifecycle(self):
        mission = MissionController()

        mission.start(target_distance_m=5)
        mission.pause()
        mission.resume()
        mission.finish()

        self.assertEqual(mission.state.phase, MissionPhase.FINISHED)
        self.assertEqual(mission.state.target_distance_m, 5)

    def test_operator_voice_commands_map_to_actuator_commands(self):
        cases = {
            "前に進めて": "forward",
            "少しバックして": "reverse",
            "左に曲がって": "turn_left",
            "右へ向いて": "turn_right",
            "止まって": "stop",
            "掃除して": "clean_on",
            "清掃を止めて": "clean_off",
            "ライトを切り替えて": "lights_toggle",
        }

        for text, command in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_operator_command(text), command)

    def test_operator_voice_commands_ignore_conversation_phrases(self):
        self.assertIsNone(parse_operator_command("話を進めて"))
        self.assertIsNone(parse_operator_command("前に何が見えるか教えて"))


if __name__ == "__main__":
    unittest.main()
