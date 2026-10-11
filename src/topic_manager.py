"""
Topic Manager for Infotainment Video Automation.

Handles category definitions, rotating topic pools, topic normalization,
and similarity checking to prevent repetition across runs.
"""

from __future__ import annotations

import difflib
import random
import re
from typing import Dict, List, Optional, Tuple

CATEGORIES: Dict[str, List[str]] = {
    "science": [
        "Why Can't Light Escape a Black Hole?",
        "How Do Tardigrades Survive in Outer Space?",
        "The Quantum Phenomenon of Entanglement Explained",
        "Why Is the Speed of Light Constant?",
        "How Do Neurons Transmit Information in Milliseconds?",
        "The Science Behind Bioluminescent Creatures in Deep Oceans",
        "How CRISPR Gene Editing Actually Works",
    ],
    "technology": [
        "How Do Solid State Drives Store Data Without Moving Parts?",
        "The Secret Architecture Behind Modern Microprocessors",
        "How Does GPS Pinpoint Your Location Anywhere on Earth?",
        "Why Is Quantum Computing So Difficult to Build?",
        "How Do Fiber Optic Cables Carry Terabits Under the Sea?",
        "The Engineering Behind Touchscreens and Capacitive Sensing",
    ],
    "ai": [
        "How Do Large Language Models Actually Understand Text?",
        "The Difference Between Neural Networks and the Human Brain",
        "How Self-Driving Cars Sense the World in Real Time",
        "Why Machine Learning Hallucinations Occur",
        "How Transformers Revolutionized Modern Artificial Intelligence",
    ],
    "space": [
        "What Would Happen If You Fell into Jupiter?",
        "How the James Webb Space Telescope Sees the Early Universe",
        "The Mind-Bending Scale of the Boötes Void",
        "Why Neutron Stars Spin Hundreds of Times Per Second",
        "The Mysterious Oort Cloud at the Edge of the Solar System",
        "How Solar Storms Threaten Earth's Power Grid",
    ],
    "geography": [
        "The Deepest Ocean Trench: Challenger Deep Explained",
        "Why the Danakil Depression Is the Hottest Place on Earth",
        "How the Ring of Fire Generates 90 Percent of World Earthquakes",
        "The Hidden Subglacial Lakes Trapped Beneath Antarctica",
        "Why Point Nemo Is the Most Isolated Spot on Earth",
    ],
    "history": [
        "The Lost Library of Alexandria and What It Actually Contained",
        "How the Antikythera Mechanism Predicted Eclipses 2000 Years Ago",
        "The Construction Secrets of the Roman Aqueducts",
        "How the Voynich Manuscript Still Baffles Cryptographers",
        "The Engineering Marvel of the Ancient Great Wall of China",
    ],
    "engineering": [
        "How Burj Khalifa Withstands Extreme Desert Winds",
        "The Tuned Mass Damper That Protects Taipei 101 from Earthquakes",
        "How Modern Nuclear Reactors Prevent Meltdowns",
        "The Engineering Genius of the Panama Canal Lock System",
        "Why Maglev Trains Can Travel at 600 Kilometers Per Hour",
    ],
    "everyday_science": [
        "Why Does Ice Float on Water Instead of Sinking?",
        "What Actually Happens in Your Brain When You Sleep?",
        "Why Do Onions Make You Cry and How to Prevent It?",
        "How Does Soap Actually Destroy Viruses and Bacteria?",
        "Why Does Microwave Cooking Heat Food Unevenly?",
    ],
    "interesting_facts": [
        "The Fact That Honey Never Truly Spoils",
        "Why Bananas Are Slightly Radioactive",
        "How Octopus Blood Uses Copper Instead of Iron",
        "The Immortal Jellyfish That Can Reset Its Biological Clock",
        "Why Lightning Strikes Upwards More Often Than You Think",
    ],
    "natural_phenomena": [
        "The Science Behind the Northern Lights (Aurora Borealis)",
        "How Sailing Stones Move on Their Own in Death Valley",
        "The Catatumbo Lightning Storm That Strikes 300 Nights a Year",
        "How Underwater Waterfalls Form Beneath the Ocean Surface",
        "The Physics Behind Ball Lightning: Nature's Rarest Spark",
    ],
}


def get_categories() -> List[str]:
    """Return all supported category names."""
    return list(CATEGORIES.keys())


def normalize_topic(topic: str) -> str:
    """
    Normalize topic string for comparison and history tracking.
    Lowercases, strips punctuation, and collapses whitespace.
    """
    if not topic:
        return ""
    cleaned = re.sub(r"[^\w\s]", " ", topic.lower())
    return " ".join(cleaned.split())


def calculate_similarity(topic_a: str, topic_b: str) -> float:
    """
    Compute similarity ratio between two topic strings (0.0 to 1.0).
    Uses difflib sequence matching and token set overlap.
    """
    norm_a = normalize_topic(topic_a)
    norm_b = normalize_topic(topic_b)
    if not norm_a or not norm_b:
        return 0.0
    if norm_a == norm_b:
        return 1.0

    seq_sim = difflib.SequenceMatcher(None, norm_a, norm_b).ratio()

    tokens_a = set(norm_a.split())
    tokens_b = set(norm_b.split())
    token_sim = (
        len(tokens_a & tokens_b) / max(len(tokens_a | tokens_b), 1)
        if (tokens_a and tokens_b)
        else 0.0
    )

    return max(seq_sim, token_sim)


def is_topic_recent_or_similar(
    topic: str, past_topics: List[str], threshold: float = 0.65
) -> bool:
    """Check if topic is identical or substantially similar to any past topic."""
    norm = normalize_topic(topic)
    for past in past_topics:
        if normalize_topic(past) == norm:
            return True
        if calculate_similarity(topic, past) >= threshold:
            return True
    return False


def infer_category(topic: str) -> str:
    """Infer the most plausible category for a user-provided topic."""
    topic_lower = topic.lower()
    keywords = {
        "space": ["planet", "star", "galaxy", "nasa", "space", "telescope", "moon", "mars", "black hole", "cosmic"],
        "ai": ["ai", "artificial intelligence", "neural", "machine learning", "robot", "gpt", "model"],
        "technology": ["computer", "code", "internet", "chip", "semiconductor", "battery", "processor", "tech", "gps"],
        "history": ["ancient", "century", "empire", "king", "war", "pyramid", "medieval", "rome", "greece"],
        "geography": ["ocean", "mountain", "river", "continent", "desert", "trench", "volcano", "earthquake"],
        "engineering": ["bridge", "tower", "dam", "engine", "reactor", "structure", "train", "tunnel"],
        "natural_phenomena": ["aurora", "lightning", "storm", "hurricane", "tornado", "phenomenon", "ice"],
        "everyday_science": ["brain", "sleep", "food", "cook", "soap", "water", "ice", "body", "eye"],
        "interesting_facts": ["fact", "why", "strange", "bizarre", "secret", "never"],
    }
    for cat, words in keywords.items():
        if any(w in topic_lower for w in words):
            return cat
    return "science"


def select_topic(
    category: Optional[str] = None,
    manual_topic: Optional[str] = None,
    past_topics: Optional[List[str]] = None,
) -> Tuple[str, str]:
    """
    Select an infotainment topic.
    Returns (topic_title, category_name).
    """
    past = past_topics or []

    if manual_topic and manual_topic.strip():
        topic = manual_topic.strip()
        cat = category if (category and category in CATEGORIES) else infer_category(topic)
        return topic, cat

    target_category = category if (category and category in CATEGORIES) else None

    if target_category:
        candidates = CATEGORIES[target_category]
        cat = target_category
    else:
        cat = random.choice(get_categories())
        candidates = CATEGORIES[cat]

    # Filter out recently used topics
    fresh_candidates = [c for c in candidates if not is_topic_recent_or_similar(c, past)]

    if fresh_candidates:
        return random.choice(fresh_candidates), cat

    # If all in category were used, try any category
    all_fresh = [
        (c, c_name)
        for c_name, pool in CATEGORIES.items()
        for c in pool
        if not is_topic_recent_or_similar(c, past)
    ]
    if all_fresh:
        chosen_topic, chosen_cat = random.choice(all_fresh)
        return chosen_topic, chosen_cat

    # Fallback to random pick from target category or pool
    return random.choice(candidates), cat
