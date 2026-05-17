import unittest

from src.reasoning.ollama import OllamaMultimodalLLM


class OllamaBackendTests(unittest.TestCase):
    def test_selects_chat_and_vision_models(self):
        llm = OllamaMultimodalLLM(
            model_id="fallback",
            chat_model_id="chat-model",
            vision_model_id="vision-model",
        )

        self.assertEqual(llm._select_model(has_image=False), "chat-model")
        self.assertEqual(llm._select_model(has_image=True), "vision-model")

    def test_configured_models_are_deduped(self):
        llm = OllamaMultimodalLLM(
            model_id="fallback",
            chat_model_id="same-model",
            vision_model_id="same-model",
        )

        self.assertEqual(llm._configured_models(), ["same-model"])

    def test_last_observation_initially_empty(self):
        llm = OllamaMultimodalLLM()

        self.assertIsNone(llm.last_observation)

    def test_clean_response_strips_emoji(self):
        self.assertEqual(
            OllamaMultimodalLLM._clean_response("  どうしたの？ 😊\n"),
            "どうしたの？",
        )

    def test_vision_observation_prompt_blocks_unseen_details(self):
        prompt = OllamaMultimodalLLM._vision_observation_prompt("机が見える")

        self.assertIn("観察メモ", prompt)
        self.assertIn("想像しない", prompt)
        self.assertIn("否定", prompt)
        self.assertIn("Markdown", prompt)
        self.assertIn("机が見える", prompt)

    def test_replace_turn_context_updates_existing_system_slot(self):
        messages = [
            {"role": "system", "content": "base"},
            {"role": "system", "content": "old"},
            {"role": "user", "content": "hi"},
        ]

        OllamaMultimodalLLM._replace_turn_context(messages, "new")

        self.assertEqual(messages[1]["content"], "new")
        self.assertEqual(len(messages), 3)

    def test_replace_turn_context_updates_first_system_slot_without_base_prompt(self):
        messages = [
            {"role": "system", "content": "old"},
            {"role": "user", "content": "hi"},
        ]

        OllamaMultimodalLLM._replace_turn_context(messages, "new")

        self.assertEqual(messages[0]["content"], "new")
        self.assertEqual(len(messages), 2)


if __name__ == "__main__":
    unittest.main()
