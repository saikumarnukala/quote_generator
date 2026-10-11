import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.audio_generator import (
    _cache_path_for_text,
    generate_audio,
    get_audio_duration,
    validate_audio_file,
)

class TestAudioGenerator(unittest.TestCase):
    def test_cache_path_generation(self):
        p1 = _cache_path_for_text("Hello world", "aura-asteria-en")
        p2 = _cache_path_for_text("Hello world", "aura-asteria-en")
        p3 = _cache_path_for_text("Different text", "aura-asteria-en")

        self.assertEqual(p1, p2)
        self.assertNotEqual(p1, p3)
        self.assertTrue(p1.endswith(".mp3"))

    def test_validate_audio_nonexistent(self):
        self.assertFalse(validate_audio_file("non_existent_audio_file_12345.mp3"))

    @patch("src.audio_generator.requests.post")
    def test_generate_audio_deepgram_mocked(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # Return 2KB dummy audio payload
        mock_resp.content = b"ID3" + (b"\x00" * 2048)
        mock_post.return_value = mock_resp

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
            temp_path = tf.name

        try:
            with patch("src.audio_generator.validate_audio_file", side_effect=lambda p: os.path.exists(p)):
                res_path = generate_audio(
                    text="Testing audio generation with mocked Deepgram Aura.",
                    output_path=temp_path,
                    voice="aura-asteria-en",
                    api_key="mock_deepgram_token",
                )
                self.assertEqual(res_path, temp_path)
                self.assertTrue(os.path.exists(temp_path))
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

if __name__ == "__main__":
    unittest.main()
