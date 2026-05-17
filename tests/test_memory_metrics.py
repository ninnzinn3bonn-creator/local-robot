import unittest

from src.reasoning.memory import ConversationMemory
from src.utils.metrics import LatencyTimer


class MemoryAndMetricsTests(unittest.TestCase):
    def test_memory_keeps_only_recent_turns(self):
        memory = ConversationMemory(max_turns=2)
        memory.add("u1", "a1")
        memory.add("u2", "a2")
        memory.add("u3", "a3")

        messages = memory.to_messages("u4")

        self.assertEqual(
            messages,
            [
                {"role": "user", "content": "u2"},
                {"role": "assistant", "content": "a2"},
                {"role": "user", "content": "u3"},
                {"role": "assistant", "content": "a3"},
                {"role": "user", "content": "u4"},
            ],
        )

    def test_latency_timer_raises_when_key_was_not_started(self):
        timer = LatencyTimer()

        with self.assertRaisesRegex(KeyError, "llm"):
            timer.stop("llm")


if __name__ == "__main__":
    unittest.main()
