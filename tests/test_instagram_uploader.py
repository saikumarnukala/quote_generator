import unittest
from unittest.mock import MagicMock, patch

from src.instagram_uploader import upload_to_instagram


class TestInstagramUploader(unittest.TestCase):
    def test_upload_disabled_by_default(self):
        # Without force_upload or dry_run, must return None
        url = upload_to_instagram(
            video_path="test.mp4",
            caption="Sample Caption",
            dry_run=False,
            force_upload=False,
        )
        self.assertIsNone(url)

    def test_upload_dry_run_mode(self):
        url = upload_to_instagram(
            video_path="test.mp4",
            caption="Sample Caption",
            dry_run=True,
        )
        self.assertIsNotNone(url)
        self.assertIn("instagram.com/p/mock_ig_", url)

    def test_upload_missing_credentials(self):
        url = upload_to_instagram(
            video_path="test.mp4",
            caption="Sample Caption",
            user_id="",
            access_token="",
            force_upload=True,
            dry_run=False,
        )
        self.assertIsNone(url)

    @patch("src.instagram_uploader.validate_mp4_video")
    def test_upload_aborts_if_video_invalid(self, mock_validate):
        mock_report = MagicMock()
        mock_report.is_valid = False
        mock_report.errors = ["Invalid resolution"]
        mock_validate.return_value = mock_report

        url = upload_to_instagram(
            video_path="corrupted.mp4",
            caption="Sample Caption",
            user_id="12345",
            access_token="EAAB...",
            force_upload=True,
            dry_run=False,
        )
        self.assertIsNone(url)

    @patch("src.instagram_uploader.validate_mp4_video")
    @patch("src.instagram_uploader.requests.post")
    def test_upload_handles_expired_token_gracefully(self, mock_post, mock_validate):
        mock_report = MagicMock()
        mock_report.is_valid = True
        mock_validate.return_value = mock_report

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {
            "error": {
                "message": "Error validating access token: Session has expired",
                "type": "OAuthException",
                "code": 190,
                "error_subcode": 463,
            }
        }
        mock_post.return_value = mock_resp

        with patch("os.path.getsize", return_value=1024):
            url = upload_to_instagram(
                video_path="valid.mp4",
                caption="Sample Caption",
                user_id="12345",
                access_token="expired_token",
                force_upload=True,
                dry_run=False,
            )
        self.assertIsNone(url)


if __name__ == "__main__":
    unittest.main()
