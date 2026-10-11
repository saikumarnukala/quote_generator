import unittest
from src.topic_manager import (
    CATEGORIES,
    calculate_similarity,
    get_categories,
    infer_category,
    is_topic_recent_or_similar,
    normalize_topic,
    select_topic,
)

class TestTopicManager(unittest.TestCase):
    def test_get_categories(self):
        cats = get_categories()
        self.assertIn("science", cats)
        self.assertIn("technology", cats)
        self.assertIn("space", cats)
        self.assertIn("history", cats)

    def test_normalize_topic(self):
        self.assertEqual(normalize_topic("Why Do We Dream?"), "why do we dream")
        self.assertEqual(normalize_topic("  Quantum... Computing!  "), "quantum computing")

    def test_similarity_calculation(self):
        sim_exact = calculate_similarity("Why Do We Dream?", "why do we dream")
        self.assertEqual(sim_exact, 1.0)

        sim_high = calculate_similarity("Why Do We Dream at Night?", "Why Do We Dream?")
        self.assertGreater(sim_high, 0.6)

        sim_low = calculate_similarity("Black Holes in Outer Space", "How Roman Aqueducts Work")
        self.assertLess(sim_low, 0.3)

    def test_duplicate_prevention(self):
        past = ["Why Can't Light Escape a Black Hole?", "How Do Neurons Transmit Information?"]
        self.assertTrue(is_topic_recent_or_similar("Why Can't Light Escape a Black Hole?", past))
        self.assertTrue(is_topic_recent_or_similar("light escape a black hole", past))
        self.assertFalse(is_topic_recent_or_similar("The Discovery of Penicillin", past))

    def test_select_topic_manual(self):
        topic, cat = select_topic(manual_topic="The James Webb Telescope")
        self.assertEqual(topic, "The James Webb Telescope")
        self.assertEqual(cat, "space")

    def test_select_topic_category(self):
        topic, cat = select_topic(category="history")
        self.assertEqual(cat, "history")
        self.assertIn(topic, CATEGORIES["history"])

    def test_infer_category(self):
        self.assertEqual(infer_category("The mystery of ancient Roman concrete"), "history")
        self.assertEqual(infer_category("Black holes and distant galaxies"), "space")
        self.assertEqual(infer_category("Neural networks in computer vision"), "ai")

if __name__ == "__main__":
    unittest.main()
