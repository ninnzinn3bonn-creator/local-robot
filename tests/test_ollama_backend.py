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

    def test_clean_response_strips_emoji(self):
        self.assertEqual(
            OllamaMultimodalLLM._clean_response("  どうしたの？ 😊\n"),
            "どうしたの？",
        )


if __name__ == "__main__":
    unittest.main()
