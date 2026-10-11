"""
Curated Background Music Manager.

Manages the local curated music collection (sourced from YouTube Audio Library),
parses track manifests, enforces licensing and verification statuses,
and automatically extracts attribution requirements.

If no verified, license-checked track exists, returns None so the video
is rendered safely with narration and no background music.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set

from config import MUSIC_DIR


@dataclass
class MusicTrack:
    filename: str
    title: str
    artist: str
    source: str = "YouTube Audio Library"
    license: str = "YouTube Audio Library License"
    attribution_required: bool = False
    attribution_text: str = ""
    permitted_usage_notes: str = "Free to use in YouTube videos and monetize"
    categories: List[str] = field(default_factory=list)
    moods: List[str] = field(default_factory=list)
    verified: bool = True
    resolved_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def get_manifest_path(music_dir: Optional[str] = None) -> str:
    """Return path to music manifest.json file."""
    base = music_dir or MUSIC_DIR
    return os.path.join(base, "manifest.json")


def load_manifest(music_dir: Optional[str] = None) -> List[MusicTrack]:
    """Load and parse the local music manifest file."""
    base = music_dir or MUSIC_DIR
    manifest_file = get_manifest_path(base)
    if not os.path.exists(manifest_file):
        return []

    try:
        with open(manifest_file, "r", encoding="utf-8") as f:
            raw_entries = json.load(f)
    except Exception as e:
        print(f"  [Music] Error reading music manifest: {e}")
        return []

    tracks: List[MusicTrack] = []
    for item in raw_entries:
        if not isinstance(item, dict):
            continue
        rel_path = item.get("filename", "")
        abs_path = os.path.normpath(os.path.join(base, rel_path))

        track = MusicTrack(
            filename=rel_path,
            title=item.get("title", "Untitled Track"),
            artist=item.get("artist", "Unknown Artist"),
            source=item.get("source", "YouTube Audio Library"),
            license=item.get("license", "YouTube Audio Library License"),
            attribution_required=bool(item.get("attribution_required", False)),
            attribution_text=item.get("attribution_text", "").strip(),
            permitted_usage_notes=item.get("permitted_usage_notes", ""),
            categories=[c.lower().strip() for c in item.get("categories", [])],
            moods=[m.lower().strip() for m in item.get("moods", [])],
            verified=bool(item.get("verified", False)),
            resolved_path=abs_path,
        )
        tracks.append(track)
    return tracks


def select_background_track(
    category: str,
    mood: Optional[str] = None,
    music_dir: Optional[str] = None,
    used_track_names: Optional[Set[str]] = None,
) -> Optional[MusicTrack]:
    """
    Select an appropriate verified background track from local library.

    Returns None if:
      - Library is empty or manifest does not exist
      - No tracks match with verified status
      - Files do not exist on disk
    """
    tracks = load_manifest(music_dir=music_dir)
    if not tracks:
        print("  [Music] Curated music library is empty — rendering video without music.")
        return None

    used = used_track_names or set()
    category_lower = category.lower().strip()

    # 1. Filter only verified tracks whose files physically exist on disk and have content
    usable_tracks: List[MusicTrack] = []
    for t in tracks:
        if not t.verified:
            continue
        if not os.path.exists(t.resolved_path):
            continue
        if os.path.getsize(t.resolved_path) < 2000:
            continue
        usable_tracks.append(t)

    if not usable_tracks:
        print("  [Music] No verified physical tracks found in library — rendering without music.")
        return None

    # 2. Match by category and mood
    cat_matches = [
        t for t in usable_tracks
        if category_lower in t.categories or "general" in t.categories
    ]
    if mood:
        mood_matches = [t for t in cat_matches if mood.lower() in t.moods]
        if mood_matches:
            cat_matches = mood_matches

    candidates = cat_matches or usable_tracks

    # 3. Prefer tracks not used recently
    fresh_candidates = [t for t in candidates if t.title not in used and t.filename not in used]
    chosen = random.choice(fresh_candidates) if fresh_candidates else random.choice(candidates)

    print(f"  [Music] Selected curated track: '{chosen.title}' by {chosen.artist} ({chosen.source})")
    if chosen.attribution_required:
        print(f"  [Music] Track requires attribution: {chosen.attribution_text}")

    return chosen
