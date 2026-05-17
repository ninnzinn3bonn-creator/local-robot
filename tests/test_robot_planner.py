import unittest

from src.robot import ActionType, RobotPlanner, WorldState


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
        self.assertEqual(plan.safety_notes, ("hazard: 机の脚が近い",))


if __name__ == "__main__":
    unittest.main()
