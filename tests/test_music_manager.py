import json
import os
import tempfile
import unittest

from src.music_manager import (
    MusicTrack,
    load_manifest,
    select_background_track,
)

class TestMusicManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.dummy_audio_file = os.path.join(self.temp_dir, "sample_track.wav")
        with open(self.dummy_audio_file, "wb") as f:
            f.write(b"RIFF" + (b"\x00" * 4000))

        self.manifest_data = [
            {
                "filename": "sample_track.wav",
                "title": "Inspiring Science",
                "artist": "Laboratory Sound",
                "source": "YouTube Audio Library",
                "license": "YouTube Audio Library License",
                "attribution_required": False,
                "attribution_text": "",
                "categories": ["science", "technology"],
                "moods": ["inspirational"],
                "verified": True,
            },
            {
                "filename": "unverified_track.wav",
                "title": "Unverified Track",
                "artist": "Unknown",
                "source": "YouTube Audio Library",
                "license": "Uncertain",
                "attribution_required": True,
                "attribution_text": "Must attribute creator.",
                "categories": ["space"],
                "moods": ["ambient"],
                "verified": False,
            }
        ]

        with open(os.path.join(self.temp_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(self.manifest_data, f)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_manifest(self):
        tracks = load_manifest(music_dir=self.temp_dir)
        self.assertEqual(len(tracks), 2)
        self.assertIsInstance(tracks[0], MusicTrack)
        self.assertEqual(tracks[0].title, "Inspiring Science")
        self.assertTrue(tracks[0].verified)

    def test_select_background_track_verified(self):
        track = select_background_track(
            category="science",
            music_dir=self.temp_dir,
        )
        self.assertIsNotNone(track)
        self.assertEqual(track.title, "Inspiring Science")
        self.assertTrue(track.verified)

    def test_select_background_track_skips_unverified(self):
        # Category space only has unverified track in our test manifest
        track = select_background_track(
            category="space",
            music_dir=self.temp_dir,
        )
        # Should pick the only verified track (science) as candidate rather than the unverified one
        self.assertIsNotNone(track)
        self.assertEqual(track.title, "Inspiring Science")

    def test_empty_library_returns_none(self):
        empty_dir = tempfile.mkdtemp()
        try:
            track = select_background_track(category="science", music_dir=empty_dir)
            self.assertIsNone(track)
        finally:
            import shutil
            shutil.rmtree(empty_dir, ignore_errors=True)

if __name__ == "__main__":
    unittest.main()
