import os
import tempfile
import unittest

from src.copyright_checker import (
    check_music_track_licensing,
    check_visual_assets_integrity,
)
from src.media_fetcher import RetrievedAsset
from src.music_manager import MusicTrack

class TestCopyrightChecker(unittest.TestCase):
    def test_check_none_music_track_compliant(self):
        # Speech-only video without music is always compliant
        res = check_music_track_licensing(None)
        self.assertTrue(res.is_compliant)
        self.assertFalse(res.requires_attribution)

    def test_check_verified_track_compliant(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            tf.write(b"RIFF" + (b"\x00" * 3000))
            audio_path = tf.name

        try:
            track = MusicTrack(
                filename="track.wav",
                title="Cosmic Wonder",
                artist="Free Music",
                resolved_path=audio_path,
                verified=True,
            )
            res = check_music_track_licensing(track)
            self.assertTrue(res.is_compliant)
        finally:
            if os.path.exists(audio_path):
                os.unlink(audio_path)

    def test_check_unverified_track_fails(self):
        track = MusicTrack(
            filename="unverified.wav",
            title="Sketchy Track",
            artist="Unknown",
            resolved_path="missing_file.wav",
            verified=False,
        )
        res = check_music_track_licensing(track)
        self.assertFalse(res.is_compliant)
        self.assertIn("not marked as verified", res.reasons[0])

    def test_check_visual_assets_integrity(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf.write(b"\x00" * 20000)
            asset_path = tf.name

        try:
            valid_asset = RetrievedAsset(
                path=asset_path,
                provider="pexels",
                asset_id="111",
                media_type="video",
                source_url="",
                query="space",
                width=1080,
                height=1920,
                duration=10.0,
            )
            all_ok, reasons = check_visual_assets_integrity([valid_asset])
            self.assertTrue(all_ok)
            self.assertEqual(len(reasons), 0)

            missing_asset = RetrievedAsset(
                path="missing_file.mp4",
                provider="pexels",
                asset_id="222",
                media_type="video",
                source_url="",
                query="galaxy",
                width=1080,
                height=1920,
                duration=10.0,
            )
            all_ok, reasons = check_visual_assets_integrity([missing_asset])
            self.assertFalse(all_ok)
            self.assertGreater(len(reasons), 0)
        finally:
            if os.path.exists(asset_path):
                os.unlink(asset_path)

if __name__ == "__main__":
    unittest.main()
