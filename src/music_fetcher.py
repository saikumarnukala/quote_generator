"""
Fetch trending background music from Jamendo (CC-licensed, royalty-free).

Jamendo is a music platform that hosts Creative Commons licensed tracks.
A free `client_id` can be obtained at https://developer.jamendo.com/v3.0

Falls back to synthesized ambient music if Jamendo is unavailable or
the client_id is not configured.
"""

import os
import random

import requests


JAMENDO_TRACKS_URL = "https://api.jamendo.com/v3.0/tracks/"

# ---------------------------------------------------------------------------
# Tag mappings — focused on CATCHY, popular, energetic music (not ambient!)
# Each entry has multiple tag combos for variety across runs.
# ---------------------------------------------------------------------------
_TOPIC_TAG_MAP = [
    (["peace", "mindful", "calm", "still", "silent", "quiet"],
     ["chillout", "lounge", "chillhop", "downtempo"]),
    (["nature", "forest", "ocean", "mountain", "landscape"],
     ["acoustic", "folk", "indie", "worldmusic"]),
    (["love", "kindness", "compassion", "heart"],
     ["pop", "rnb", "soul", "romantic"]),
    (["courage", "strength", "growth", "power"],
     ["rock", "electronic", "hiphop", "energetic"]),
    (["wisdom", "patience", "philosophy"],
     ["jazz", "classical", "soul", "blues"]),
    (["gratitude", "joy", "light", "hope", "freedom"],
     ["pop", "dance", "funk", "happy"]),
    (["harmony", "balance", "zen"],
     ["lounge", "chillhop", "jazz", "bossanova"]),
    (["darkness", "struggle", "pain", "loss"],
     ["rock", "blues", "darkelectronic", "triphop"]),
    (["success", "motivation", "inspire", "dream"],
     ["pop", "electronic", "hiphop", "uplifting"]),
    (["fun", "party", "celebrate", "dance"],
     ["dance", "house", "disco", "funk"]),
]
# Catchy fallback tags when no topic keyword matches
_DEFAULT_TAGS = ["pop", "electronic", "hiphop", "dance", "rock", "indie"]


def _tags_for_topic(topic: str) -> str:
    """Pick a single catchy tag that matches the topic mood."""
    topic_lower = topic.lower()
    for keywords, tag_list in _TOPIC_TAG_MAP:
        if any(kw in topic_lower for kw in keywords):
            return random.choice(tag_list)
    return random.choice(_DEFAULT_TAGS)


def fetch_trending_music(
    topic: str,
    client_id: str,
    duration: float,
    output_path: str,
) -> dict:
    """
    Download a trending CC-licensed music track from Jamendo that matches
    the video topic mood.

    Args:
        topic:       The quote/video topic (selects matching music mood/tags).
        client_id:   Jamendo API client ID (free — register at jamendo.com).
        duration:    Required minimum track duration in seconds.
        output_path: Destination path for the downloaded audio (.mp3).

    Returns:
        dict with keys:
          "path"        — path to the downloaded MP3 (or fallback WAV)
          "track_name"  — track title (empty string for fallback)
          "artist_name" — artist name (empty string for fallback)
          "license_url" — Creative Commons license URL (empty for fallback)
    """
    _empty_attr = {"path": "", "track_name": "", "artist_name": "", "license_url": ""}

    if not client_id:
        print("        JAMENDO_CLIENT_ID not set — using synthesized ambient music.")
        return {**_empty_attr, "path": _fallback_ambient(duration, output_path)}

    tags = _tags_for_topic(topic)
    print(f"        Searching Jamendo for trending music (tags: {tags!r})...")

    try:
        track_url, track_name, artist, license_url = _find_track(client_id, tags, duration)
    except Exception as e:
        print(f"        Jamendo search failed ({e}) — using synthesized ambient music.")
        return {**_empty_attr, "path": _fallback_ambient(duration, output_path)}

    print(f"        Music   : '{track_name}' by {artist}")
    print(f"        License : {license_url}")

    # Ensure output path uses .mp3 extension since Jamendo serves MP3
    mp3_path = os.path.splitext(output_path)[0] + ".mp3"

    try:
        _download(track_url, mp3_path)
    except Exception as e:
        print(f"        Jamendo download failed ({e}) — using synthesized ambient music.")
        return {**_empty_attr, "path": _fallback_ambient(duration, output_path)}

    return {
        "path": mp3_path,
        "track_name": track_name,
        "artist_name": artist,
        "license_url": license_url,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Always sort by popularity — we want the hits, not random filler
_ORDER_OPTIONS = [
    "popularity_total",
    "popularity_month",
    "popularity_week",
]


def _find_track(client_id: str, tags: str, min_duration: float):
    """Query Jamendo and return (download_url, track_name, artist_name).

    Strategy:
      1. Search with the chosen tag, sorted by popularity, using fuzzytags
         for broader matching.  Pick from the top results (small random
         offset so we still get variety across runs).
      2. If no results, retry with a popular fallback tag.
      3. If still nothing, do a tag-free popularity search — guaranteed to
         return the most-listened tracks on Jamendo.
    """
    order = random.choice(_ORDER_OPTIONS)
    # Small offset (0-20) keeps us near the most popular tracks while
    # still giving variety across runs
    offset = random.randint(0, 20)

    base_params = {
        "client_id":       client_id,
        "format":          "json",
        "limit":           30,
        "audiodlformat":   "mp32",
        "boost":           "popularity_total",
        "include":         "musicinfo+licenses",
        "order":           order,
        "content_id_free": True,
    }

    # --- Attempt 1: fuzzytags search (broader than strict tags) -----------
    params = {
        **base_params,
        "fuzzytags":     tags,
        "offset":        offset,
    }
    tracks = _query_jamendo(params, min_duration)

    # --- Attempt 2: strict tags search ------------------------------------
    if not tracks:
        params = {
            **base_params,
            "tags":   tags,
            "offset": 0,
        }
        tracks = _query_jamendo(params, min_duration)

    # --- Attempt 3: different popular tag ---------------------------------
    if not tracks:
        fallback_tag = random.choice(_DEFAULT_TAGS)
        print(f"        No results for '{tags}', trying '{fallback_tag}'...")
        params = {
            **base_params,
            "fuzzytags": fallback_tag,
            "offset":    0,
        }
        tracks = _query_jamendo(params, min_duration)

    # --- Attempt 4: pure popularity (no tags) — guaranteed results --------
    if not tracks:
        print("        Falling back to top-popular tracks (no tag filter)...")
        params = {
            **base_params,
            "offset": random.randint(0, 10),
        }
        tracks = _query_jamendo(params, min_duration)

    if not tracks:
        raise ValueError("No tracks found on Jamendo")

    # Pick from TOP 10 most popular results (not a random shuffle of all 30)
    top_tracks = tracks[:10]
    random.shuffle(top_tracks)

    track = None
    for candidate in top_tracks:
        # Skip tracks that disallow downloads
        if not candidate.get("audiodownload_allowed", True):
            continue
        url = candidate.get("audiodownload", "").strip()
        if not url or not url.startswith("http"):
            url = candidate.get("audio", "").strip()
        if url and url.startswith("http"):
            candidate["_resolved_url"] = url
            track = candidate
            break

    if track is None:
        raise ValueError("No tracks with a valid download URL found on Jamendo")

    return (
        track["_resolved_url"],
        track.get("name", "unknown"),
        track.get("artist_name", "unknown"),
        track.get("license_ccurl", ""),
    )


def _query_jamendo(params: dict, min_duration: float) -> list:
    """Run a single Jamendo API query and return filtered results."""
    try:
        resp = requests.get(JAMENDO_TRACKS_URL, params=params, timeout=15)
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except Exception:
        return []

    # Filter by minimum duration client-side (more reliable than API param
    # which sometimes ignores short minimums)
    min_sec = max(min_duration, 30)
    return [t for t in results if int(t.get("duration", 0)) >= min_sec]


def _download(url: str, dest: str) -> None:
    """Stream-download a URL to dest."""
    resp = requests.get(url, timeout=60, stream=True)
    resp.raise_for_status()
    with open(dest, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=65536):
            fh.write(chunk)


def _fallback_ambient(duration: float, output_path: str) -> str:
    from src.ambient_generator import generate_ambient  # local import to avoid circular dep
    wav_path = os.path.splitext(output_path)[0] + ".wav"
    return generate_ambient(duration, wav_path)
