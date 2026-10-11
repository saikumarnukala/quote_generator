import unittest
from unittest.mock import MagicMock, patch

from src.researcher import (
    ResearchDossier,
    extract_key_facts,
    research_topic,
)

class TestResearcher(unittest.TestCase):
    def test_extract_key_facts(self):
        sample_text = (
            "A black hole is a region of spacetime where gravity is so strong that nothing can escape. "
            "The boundary of no escape is called the event horizon. "
            "Quantum field theory predicts that event horizons emit Hawking radiation."
        )
        facts = extract_key_facts(sample_text, max_facts=2)
        self.assertEqual(len(facts), 2)
        self.assertTrue(facts[0].startswith("A black hole"))

    @patch("src.researcher.requests.get")
    def test_research_topic_mocked(self, mock_get):
        # Mock search opensearch response
        search_resp = MagicMock()
        search_resp.status_code = 200
        search_resp.json.return_value = ["black hole", ["Black hole"], ["description"], ["https://en.wikipedia.org/wiki/Black_hole"]]

        # Mock REST API summary response
        summary_resp = MagicMock()
        summary_resp.status_code = 200
        summary_resp.json.return_value = {
            "title": "Black hole",
            "extract": "A black hole is a region of spacetime exhibiting gravitational acceleration so strong that nothing can escape.",
            "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Black_hole"}}
        }

        mock_get.side_effect = [search_resp, summary_resp]

        dossier = research_topic("Why Can't Light Escape a Black Hole?", category="space")
        self.assertIsInstance(dossier, ResearchDossier)
        self.assertEqual(dossier.primary_source_title, "Black hole")
        self.assertIn("gravitational acceleration", dossier.summary)
        self.assertGreater(len(dossier.sources), 0)

    @patch("src.researcher.requests.get")
    def test_research_topic_fallback_on_network_error(self, mock_get):
        mock_get.side_effect = Exception("Network offline")
        dossier = research_topic("Tardigrades in Space", category="science")
        self.assertIsInstance(dossier, ResearchDossier)
        self.assertEqual(dossier.topic, "Tardigrades in Space")
        self.assertGreater(len(dossier.sources), 0)

if __name__ == "__main__":
    unittest.main()
