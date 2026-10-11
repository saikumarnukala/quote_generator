import json
import unittest
from unittest.mock import MagicMock, patch

from src.video_validator import ValidationReport, validate_mp4_video

class TestVideoValidator(unittest.TestCase):
    def test_validate_nonexistent_file(self):
        report = validate_mp4_video("non_existent_file.mp4")
        self.assertFalse(report.is_valid)
        self.assertIn("File does not exist", report.errors[0])

    @patch("src.video_validator.os.path.exists", return_value=True)
    @patch("src.video_validator.os.path.getsize", return_value=1_500_000)
    @patch("src.video_validator.subprocess.run")
    def test_validate_valid_video_mocked(self, mock_run, mock_getsize, mock_exists):
        probe_output = {
            "format": {"duration": "35.5"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1080,
                    "height": 1920,
                    "r_frame_rate": "30/1"
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "channels": 2,
                    "sample_rate": 44100
                }
            ]
        }
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = json.dumps(probe_output)
        mock_run.return_value = mock_res

        report = validate_mp4_video("sample_valid.mp4")
        self.assertTrue(report.is_valid)
        self.assertEqual(report.width, 1080)
        self.assertEqual(report.height, 1920)
        self.assertEqual(report.video_codec, "h264")
        self.assertEqual(report.audio_codec, "aac")
        self.assertEqual(len(report.errors), 0)

    @patch("src.video_validator.os.path.exists", return_value=True)
    @patch("src.video_validator.os.path.getsize", return_value=1_000_000)
    @patch("src.video_validator.subprocess.run")
    def test_validate_invalid_resolution(self, mock_run, mock_getsize, mock_exists):
        probe_output = {
            "format": {"duration": "30.0"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,  # Landscape instead of portrait
                    "r_frame_rate": "30/1"
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "channels": 2,
                    "sample_rate": 44100
                }
            ]
        }
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = json.dumps(probe_output)
        mock_run.return_value = mock_res

        report = validate_mp4_video("sample_landscape.mp4")
        self.assertFalse(report.is_valid)
        self.assertTrue(any("Unexpected resolution" in e for e in report.errors))

if __name__ == "__main__":
    unittest.main()
