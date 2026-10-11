import json
import unittest
from unittest.mock import MagicMock, patch

from src.researcher import ResearchDossier, SourceCitation
from src.script_generator import (
    InfotainmentScript,
    build_fallback_script,
    estimate_narration_duration,
    generate_infotainment_script,
    validate_script_dict,
)

class TestScriptGenerator(unittest.TestCase):
    def setUp(self):
        self.dossier = ResearchDossier(
            topic="How Tardigrades Survive",
            category="science",
            primary_source_title="Tardigrade",
            primary_source_url="https://en.wikipedia.org/wiki/Tardigrade",
            summary="Tardigrades are near-microscopic animals capable of surviving extreme conditions including the vacuum of outer space.",
            key_facts=[
                "Tardigrades can survive temperatures down to minus 328 degrees Fahrenheit.",
                "They enter cryptobiosis when dehydrated, suspending metabolic activity."
            ],
            sources=[
                SourceCitation(
                    title="Wikipedia: Tardigrade",
                    url="https://en.wikipedia.org/wiki/Tardigrade",
                    snippet="Tardigrades are resilient microscopic organisms.",
                    verified=True,
                )
            ],
        )

    def test_estimate_narration_duration(self):
        text = "This is a short test sentence of eight words."
        dur = estimate_narration_duration(text)
        self.assertGreaterEqual(dur, 3.5)

    def test_validate_script_dict_valid(self):
        valid_dict = {
            "title": "Unbreakable Creatures",
            "scenes": [
                {"narration": "Scene 1 narration.", "video_search_queries": ["tardigrade microscope"]},
                {"narration": "Scene 2 narration.", "video_search_queries": ["outer space stars"]},
                {"narration": "Scene 3 narration.", "video_search_queries": ["science lab"]},
            ]
        }
        self.assertTrue(validate_script_dict(valid_dict))

    def test_validate_script_dict_invalid(self):
        invalid_missing_scenes = {"title": "Test Title", "scenes": []}
        self.assertFalse(validate_script_dict(invalid_missing_scenes))

        invalid_empty_narration = {
            "title": "Test",
            "scenes": [
                {"narration": "", "video_search_queries": ["query"]},
                {"narration": "valid", "video_search_queries": ["query"]},
                {"narration": "valid", "video_search_queries": ["query"]},
            ]
        }
        self.assertFalse(validate_script_dict(invalid_empty_narration))

    def test_build_fallback_script(self):
        script = build_fallback_script("How Tardigrades Survive", "science", self.dossier, num_scenes=4)
        self.assertIsInstance(script, InfotainmentScript)
        self.assertEqual(len(script.scenes), 4)
        self.assertTrue(script.hook)
        self.assertGreater(script.target_duration, 15.0)

    @patch("src.script_generator.Groq")
    def test_generate_script_mocked_groq(self, mock_groq_class):
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client

        mock_response = MagicMock()
        mock_payload = {
            "title": "Why Tardigrades Can Survive Space",
            "hook": "Meet the immortal animal of our planet.",
            "scenes": [
                {
                    "scene_number": 1,
                    "narration": "Meet the tardigrade, an eight-legged microscopic survivor.",
                    "duration_est": 8.0,
                    "main_subject": "Tardigrade under microscope",
                    "visual_type": "video",
                    "video_search_queries": ["microscope tardigrade", "water bear"],
                    "image_search_queries": ["tardigrade close up"],
                    "onscreen_text": "THE IMMORTAL ANIMAL",
                    "source_refs": ["Tardigrade"]
                },
                {
                    "scene_number": 2,
                    "narration": "In 2007, thousands were launched into outer space without protection.",
                    "duration_est": 10.0,
                    "main_subject": "Outer space orbit",
                    "visual_type": "video",
                    "video_search_queries": ["satellite earth orbit", "space vacuum"],
                    "image_search_queries": ["spacecraft"],
                    "onscreen_text": "SPACE SURVIVOR",
                    "source_refs": ["Tardigrade"]
                },
                {
                    "scene_number": 3,
                    "narration": "They enter cryptobiosis, shutting down their metabolism completely.",
                    "duration_est": 9.0,
                    "main_subject": "Cellular biology",
                    "visual_type": "video",
                    "video_search_queries": ["cell biology animation", "dna science"],
                    "image_search_queries": ["cellular structure"],
                    "onscreen_text": "CRYPTOBIOSIS SHUTDOWN",
                    "source_refs": ["Tardigrade"]
                },
                {
                    "scene_number": 4,
                    "narration": "Once water returns, they reawaken like nothing ever happened.",
                    "duration_est": 8.0,
                    "main_subject": "Water drop on glass",
                    "visual_type": "video",
                    "video_search_queries": ["water droplet slow motion", "nature revival"],
                    "image_search_queries": ["water droplet"],
                    "onscreen_text": "BACK TO LIFE",
                    "source_refs": ["Tardigrade"]
                }
            ]
        }
        mock_response.choices = [
            MagicMock(message=MagicMock(content=json.dumps(mock_payload)))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        script = generate_infotainment_script(
            topic="How Tardigrades Survive",
            category="science",
            dossier=self.dossier,
            groq_api_key="gsk_mock_valid_key_12345678901234567890",
            num_scenes=4,
        )

        self.assertEqual(script.title, "Why Tardigrades Can Survive Space")
        self.assertEqual(len(script.scenes), 4)
        self.assertEqual(script.scenes[0].onscreen_text, "THE IMMORTAL ANIMAL")

if __name__ == "__main__":
    unittest.main()
