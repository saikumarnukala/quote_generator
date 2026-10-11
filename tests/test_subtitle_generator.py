import os
import tempfile
import unittest

from src.subtitle_generator import (
    build_subtitle_cues,
    chunk_narration_phrases,
    generate_ass,
    generate_srt,
)

class TestSubtitleGenerator(unittest.TestCase):
    def test_chunk_narration_phrases(self):
        text = "Neutron stars are so dense that a single teaspoon weighs billions of tons."
        chunks = chunk_narration_phrases(text, max_words=4)
        self.assertGreaterEqual(len(chunks), 2)
        # Verify all words preserved
        reconstructed = " ".join(chunks)
        self.assertEqual(reconstructed.split(), text.split())

    def test_build_subtitle_cues(self):
        narrations = ["First scene explanation.", "Second scene conclusion."]
        durations = [5.0, 5.0]
        cues = build_subtitle_cues(narrations, durations)
        self.assertGreater(len(cues), 0)
        # End of last cue should match total duration
        last_end = cues[-1][1]
        self.assertAlmostEqual(last_end, 10.0, places=1)

    def test_generate_srt(self):
        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as tf:
            srt_path = tf.name

        try:
            generate_srt(["Hello world sentence one.", "Sentence two."], [4.0, 4.0], srt_path)
            self.assertTrue(os.path.exists(srt_path))
            with open(srt_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("-->", content)
            self.assertIn("Hello world", content)
        finally:
            if os.path.exists(srt_path):
                os.unlink(srt_path)

    def test_generate_ass(self):
        with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as tf:
            ass_path = tf.name

        try:
            generate_ass(["Fact one.", "Fact two."], [3.5, 4.0], ass_path)
            self.assertTrue(os.path.exists(ass_path))
            with open(ass_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("[Script Info]", content)
            self.assertIn("[V4+ Styles]", content)
            self.assertIn("Dialogue:", content)
        finally:
            if os.path.exists(ass_path):
                os.unlink(ass_path)

if __name__ == "__main__":
    unittest.main()
