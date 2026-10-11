import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.media_fetcher import (
    create_infographic_card,
    retrieve_scene_media,
    validate_media_file,
)

class TestMediaFetcher(unittest.TestCase):
    def test_validate_nonexistent_media(self):
        self.assertFalse(validate_media_file("invalid_clip_123.mp4"))

    def test_create_infographic_card(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            card_path = tf.name

        try:
            created = create_infographic_card(
                title="BLACK HOLE GRAVITY",
                subtitle="Light cannot escape past the event horizon.",
                output_image_path=card_path,
                width=1080,
                height=1920,
            )
            self.assertTrue(os.path.exists(created))
            self.assertGreater(os.path.getsize(created), 5000)
        finally:
            if os.path.exists(card_path):
                os.unlink(card_path)

    @patch("src.media_fetcher._fetch_pexels_video")
    @patch("src.media_fetcher.transcode_to_portrait_video")
    def test_retrieve_scene_media_pexels_success(self, mock_transcode, mock_pexels_v):
        mock_asset = MagicMock(
            path="temp/raw.mp4",
            provider="pexels",
            asset_id="12345",
            width=1920,
            height=1080,
        )
        mock_pexels_v.return_value = mock_asset
        mock_transcode.return_value = True

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            out_path = tf.name

        try:
            res = retrieve_scene_media(
                scene_number=1,
                video_queries=["supernova explosion"],
                image_queries=["supernova"],
                main_subject="Supernova",
                target_duration=8.0,
                output_video_path=out_path,
                pexels_key="mock_pexels_key",
            )
            self.assertEqual(res.provider, "pexels")
            self.assertEqual(res.asset_id, "12345")
        finally:
            if os.path.exists(out_path):
                os.unlink(out_path)

    @patch("src.media_fetcher._fetch_pexels_video", return_value=None)
    @patch("src.media_fetcher._fetch_pixabay_video")
    @patch("src.media_fetcher.transcode_to_portrait_video")
    def test_retrieve_scene_media_pixabay_fallback(self, mock_transcode, mock_pixabay_v, mock_pexels_v):
        mock_asset = MagicMock(
            path="temp/pixabay.mp4",
            provider="pixabay",
            asset_id="99999",
            width=1280,
            height=720,
        )
        mock_pixabay_v.return_value = mock_asset
        mock_transcode.return_value = True

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            out_path = tf.name

        try:
            res = retrieve_scene_media(
                scene_number=1,
                video_queries=["quantum physics"],
                image_queries=["atom"],
                main_subject="Quantum Physics",
                target_duration=7.0,
                output_video_path=out_path,
                pexels_key="mock_key",
                pixabay_key="mock_key",
            )
            self.assertEqual(res.provider, "pixabay")
            self.assertEqual(res.asset_id, "99999")
        finally:
            if os.path.exists(out_path):
                os.unlink(out_path)

if __name__ == "__main__":
    unittest.main()
