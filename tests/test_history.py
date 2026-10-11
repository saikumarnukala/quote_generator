import json
import os
import tempfile
import unittest
from unittest.mock import patch

from src.history import (
    get_used_asset_ids,
    get_used_music_tracks,
    get_used_normalized_topics,
    get_used_topics,
    is_topic_already_used,
    record_infotainment_run,
)

class TestHistory(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.history_file = os.path.join(self.temp_dir, "history.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_and_read_run(self):
        with patch("src.history.HISTORY_FILE", self.history_file):
            record_infotainment_run(
                topic="Why Do Stars Twinkle?",
                category="space",
                title="The Secret of Twinkling Stars",
                script_summary="Atmospheric refraction causes stellar scintillation.",
                sources=[{"title": "Stellar Scintillation", "url": "https://example.com/stars"}],
                visual_asset_ids=["px_1001", "pb_2002"],
                music_track_title="Stellar Drift",
                output_video_path="output/stars.mp4",
                video_duration=42.5,
                youtube_video_id="abc123xyz",
                upload_status="uploaded",
            )

            topics = get_used_topics()
            self.assertIn("Why Do Stars Twinkle?", topics)

            norms = get_used_normalized_topics()
            self.assertIn("why do stars twinkle", norms)

            assets = get_used_asset_ids()
            self.assertIn("px_1001", assets)
            self.assertIn("pb_2002", assets)

            tracks = get_used_music_tracks()
            self.assertIn("Stellar Drift", tracks)

            self.assertTrue(is_topic_already_used("Why Do Stars Twinkle?"))
            self.assertTrue(is_topic_already_used("why do stars twinkle"))
            self.assertFalse(is_topic_already_used("How Do Volcanoes Erupt?"))

if __name__ == "__main__":
    unittest.main()
