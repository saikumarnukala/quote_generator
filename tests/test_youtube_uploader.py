import unittest
from unittest.mock import MagicMock, patch

from src.youtube_uploader import upload_to_youtube

class TestYouTubeUploader(unittest.TestCase):
    def test_upload_disabled_by_default(self):
        # Without force_upload or dry_run, must return (None, None)
        url, vid_id = upload_to_youtube(
            video_path="test.mp4",
            title="Sample Title",
            dry_run=False,
            force_upload=False,
        )
        self.assertIsNone(url)
        self.assertIsNone(vid_id)

    def test_upload_dry_run_mode(self):
        url, vid_id = upload_to_youtube(
            video_path="test.mp4",
            title="Sample Title",
            dry_run=True,
        )
        self.assertIsNotNone(url)
        self.assertIsNotNone(vid_id)
        self.assertIn("mock_", vid_id)

    @patch("src.youtube_uploader.validate_mp4_video")
    def test_upload_aborts_if_video_invalid(self, mock_validate):
        mock_report = MagicMock()
        mock_report.is_valid = False
        mock_report.errors = ["Missing audio stream"]
        mock_validate.return_value = mock_report

        url, vid_id = upload_to_youtube(
            video_path="corrupted.mp4",
            title="Title",
            force_upload=True,
            dry_run=False,
        )
        self.assertIsNone(url)
        self.assertIsNone(vid_id)

if __name__ == "__main__":
    unittest.main()
