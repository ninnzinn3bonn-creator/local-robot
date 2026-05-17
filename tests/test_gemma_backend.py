import unittest

from src.reasoning.gemma import GemmaMultimodalLLM, LANGUAGE_LABELS, _clean_response


class GemmaBackendTests(unittest.TestCase):
    def test_clean_response_strips_whitespace(self):
        self.assertEqual(_clean_response("  こんにちは\n"), "こんにちは")

    def test_language_label_maps_japanese_code(self):
        self.assertEqual(LANGUAGE_LABELS["ja"], "Japanese")

    def test_inject_image_into_last_user_message(self):
        image = object()
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "これは何？"},
        ]

        GemmaMultimodalLLM._inject_image_into_last_user_message(messages, image)

        content = messages[-1]["content"]
        self.assertEqual(content[0], {"type": "image", "image": image})
        self.assertEqual(content[1], {"type": "text", "text": "これは何？"})


if __name__ == "__main__":
    unittest.main()
