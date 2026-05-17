import unittest

from src.perception.wake_word import WakeWordDetector


class WakeWordDetectorTests(unittest.TestCase):
    def test_detects_alias_and_returns_content_after_wake_word(self):
        detector = WakeWordDetector(["じろえもん", "ジロエモン"])

        detected, content = detector.detect("じろえもん、これは何？")

        self.assertTrue(detected)
        self.assertEqual(content, "これは何？")

    def test_detects_katakana_alias_as_hiragana(self):
        detector = WakeWordDetector(["じろえもん"])

        detected, content = detector.detect("ジロエモン 右を見て")

        self.assertTrue(detected)
        self.assertEqual(content, "右を見て")

    def test_content_slice_handles_spaces_inside_wake_word(self):
        detector = WakeWordDetector(["じろえもん"])

        detected, content = detector.detect("じ ろ え もん、これ何？")

        self.assertTrue(detected)
        self.assertEqual(content, "これ何？")

    def test_detects_case_insensitive_english_alias(self):
        detector = WakeWordDetector(["hey jiro"])

        detected, content = detector.detect("Hey Jiro これ見て")

        self.assertTrue(detected)
        self.assertEqual(content, "これ見て")

    def test_disabled_detector_passes_text_through(self):
        detector = WakeWordDetector(["じろえもん"], enabled=False)

        detected, content = detector.detect("これは何？")

        self.assertTrue(detected)
        self.assertEqual(content, "これは何？")


if __name__ == "__main__":
    unittest.main()
