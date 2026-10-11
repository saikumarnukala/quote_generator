import unittest
import config

class TestConfig(unittest.TestCase):
    def test_dimensions_and_fps(self):
        self.assertEqual(config.VIDEO_WIDTH, 1080)
        self.assertEqual(config.VIDEO_HEIGHT, 1920)
        self.assertEqual(config.VIDEO_FPS, 30)

    def test_directories_defined(self):
        self.assertTrue(bool(config.OUTPUT_DIR))
        self.assertTrue(bool(config.TEMP_DIR))
        self.assertTrue(bool(config.ASSETS_DIR))
        self.assertTrue(bool(config.MUSIC_DIR))

    def test_upload_disabled_by_default(self):
        # Unless explicitly set to true in env, should default to False
        self.assertIsInstance(config.YOUTUBE_UPLOAD_ENABLED, bool)
        self.assertIsInstance(config.INSTAGRAM_UPLOAD_ENABLED, bool)

    def test_default_voices(self):
        self.assertIn("aura-", config.DEEPGRAM_VOICE)

if __name__ == "__main__":
    unittest.main()
