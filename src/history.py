"""
Persistent run history — tracks used quotes, Pexels video IDs, and Jamendo track IDs
so every run produces completely fresh content with no repeats.

Stored in data/history.json — committed back to the repo by the GitHub Actions workflow
after each run so the state survives across ephemeral CI runners.
"""

import json
import os

_HISTORY_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "history.json")

# Rolling window limits — prevent the file growing unboundedly
_MAX_QUOTES    = 700
_MAX_VIDEO_IDS = 2000
_MAX_MUSIC_IDS = 500


def _path() -> str:
    return os.path.abspath(_HISTORY_FILE)


def _load() -> dict:
    p = _path()
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"quotes": [], "video_ids": [], "music_ids": []}


def _save(history: dict) -> None:
    p = _path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


# ── Public read helpers ────────────────────────────────────────────────────

def get_used_quotes() -> list[str]:
    """Return list of quote strings used in previous runs."""
    return _load().get("quotes", [])


def get_used_video_ids() -> set[int]:
    """Return set of Pexels video IDs already used."""
    return set(_load().get("video_ids", []))


def get_used_music_ids() -> set[str]:
    """Return set of Jamendo/Archive track IDs already used."""
    return set(_load().get("music_ids", []))


# ── Public write helper ────────────────────────────────────────────────────

def record_run(
    quotes: list[str],
    video_ids: list[int],
    music_id: str | None,
) -> None:
    """
    Append this run's content to the persistent history and save to disk.
    Called at the end of a successful pipeline run in main.py.
    """
    history = _load()

    # Quotes — rolling window, newest last
    existing_quotes = history.get("quotes", [])
    existing_quotes.extend(q.strip() for q in quotes if q and q.strip())
    history["quotes"] = existing_quotes[-_MAX_QUOTES:]

    # Pexels video IDs — deduped set, capped
    existing_vids = list(set(history.get("video_ids", [])) | set(video_ids))
    history["video_ids"] = existing_vids[-_MAX_VIDEO_IDS:]

    # Music track IDs
    if music_id:
        existing_music = list(set(history.get("music_ids", [])) | {str(music_id)})
        history["music_ids"] = existing_music[-_MAX_MUSIC_IDS:]

    _save(history)
    print(f"  [History] Saved — {len(history['quotes'])} quotes, "
          f"{len(history['video_ids'])} videos, {len(history['music_ids'])} tracks recorded.")
