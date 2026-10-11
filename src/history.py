"""
Infotainment Run History and Duplicate Prevention Module.

Maintains persistent run history in data/history.json tracking:
  - Topics and normalized topic keys
  - Categories
  - Script summaries
  - Verified research source references
  - Used visual asset IDs (Pexels / Pixabay)
  - Selected music tracks
  - Output video filenames and durations
  - YouTube video IDs and upload statuses
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Set

from config import DATA_DIR
from src.topic_manager import calculate_similarity, normalize_topic

HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
MAX_RUNS = 500


def _load_raw_history() -> Dict[str, Any]:
    if not os.path.exists(HISTORY_FILE):
        return {"runs": [], "topics": [], "normalized_topics": [], "asset_ids": [], "music_tracks": []}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {"runs": [], "topics": [], "normalized_topics": [], "asset_ids": [], "music_tracks": []}
            return data
    except Exception:
        return {"runs": [], "topics": [], "normalized_topics": [], "asset_ids": [], "music_tracks": []}


def _save_raw_history(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(HISTORY_FILE)), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_used_topics() -> List[str]:
    """Return list of past raw topic titles."""
    history = _load_raw_history()
    return [r.get("topic") for r in history.get("runs", []) if r.get("topic")] or history.get("topics", [])


def get_used_normalized_topics() -> Set[str]:
    """Return set of normalized past topics for fast exact matching."""
    history = _load_raw_history()
    norms = set(history.get("normalized_topics", []))
    for r in history.get("runs", []):
        if r.get("normalized_topic"):
            norms.add(r["normalized_topic"])
        elif r.get("topic"):
            norms.add(normalize_topic(r["topic"]))
    return norms


def get_used_asset_ids() -> Set[str]:
    """Return set of Pexels and Pixabay asset IDs used in past runs."""
    history = _load_raw_history()
    asset_ids = set(str(a) for a in history.get("asset_ids", []))
    for r in history.get("runs", []):
        for aid in r.get("visual_asset_ids", []):
            asset_ids.add(str(aid))
    return asset_ids


def get_used_music_tracks() -> Set[str]:
    """Return set of music filenames/titles used in past runs."""
    history = _load_raw_history()
    music_tracks = set(history.get("music_tracks", []))
    for r in history.get("runs", []):
        if r.get("music_track"):
            music_tracks.add(r["music_track"])
    return music_tracks


def is_topic_already_used(topic: str, threshold: float = 0.65) -> bool:
    """Check if a proposed topic matches or is substantially similar to any past topic."""
    norm = normalize_topic(topic)
    used_norms = get_used_normalized_topics()
    if norm in used_norms:
        return True

    past_topics = get_used_topics()
    for past in past_topics:
        if calculate_similarity(topic, past) >= threshold:
            return True
    return False


def record_infotainment_run(
    topic: str,
    category: str,
    title: str,
    script_summary: str,
    sources: List[Dict[str, str]],
    visual_asset_ids: List[str],
    music_track_title: Optional[str],
    output_video_path: str,
    video_duration: float,
    youtube_video_id: Optional[str] = None,
    upload_status: str = "local_only",
) -> None:
    """Record a complete infotainment video creation run into persistent history."""
    history = _load_raw_history()
    runs = history.get("runs", [])

    run_entry = {
        "run_id": f"run_{int(time.time())}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "topic": topic,
        "normalized_topic": normalize_topic(topic),
        "category": category,
        "title": title,
        "script_summary": script_summary[:300],
        "sources": sources,
        "visual_asset_ids": [str(a) for a in visual_asset_ids if a],
        "music_track": music_track_title or "none",
        "output_video": os.path.basename(output_video_path),
        "video_duration": round(video_duration, 2),
        "youtube_video_id": youtube_video_id or None,
        "upload_status": upload_status,
    }

    runs.append(run_entry)
    # Maintain rolling window
    history["runs"] = runs[-MAX_RUNS:]

    # Update top-level rolling quick lookups
    history["topics"] = [r["topic"] for r in history["runs"]]
    history["normalized_topics"] = list(set(r["normalized_topic"] for r in history["runs"]))
    all_assets = set()
    for r in history["runs"]:
        all_assets.update(r.get("visual_asset_ids", []))
    history["asset_ids"] = list(all_assets)[-2000:]
    history["music_tracks"] = list(set(r.get("music_track") for r in history["runs"] if r.get("music_track")))[-200:]

    _save_raw_history(history)
    print(f"  [History] Saved run record — {len(history['runs'])} total runs tracked.")
