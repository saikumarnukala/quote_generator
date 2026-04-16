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

# Map topic keywords to Jamendo music tags (space-separated for the API)
# Each entry now has MULTIPLE tag combos so we can rotate for variety
_TOPIC_TAG_MAP = [
    (["peace", "mindful", "calm", "still", "silent", "quiet"],
     ["ambient meditation", "ambient piano", "cinematic calm", "chillout ambient"]),
    (["nature", "forest", "ocean", "mountain", "landscape"],
     ["ambient acoustic", "nature cinematic", "acoustic relaxing", "ambient electronic"]),
    (["love", "kindness", "compassion", "heart"],
     ["romantic emotional", "piano emotional", "acoustic love", "cinematic emotional"]),
    (["courage", "strength", "growth", "power"],
     ["motivational uplifting", "cinematic epic", "inspiring orchestral", "uplifting electronic"]),
    (["wisdom", "patience", "philosophy"],
     ["ambient cinematic", "neoclassical", "piano solo", "ambient downtempo"]),
    (["gratitude", "joy", "light", "hope", "freedom"],
     ["uplifting positive", "happy acoustic", "cinematic inspiring", "ambient uplifting"]),
    (["harmony", "balance", "zen"],
     ["ambient meditation", "zen relaxing", "chillout lounge", "ambient drone"]),
    (["darkness", "struggle", "pain", "loss"],
     ["cinematic dark", "ambient atmospheric", "piano melancholic", "cinematic emotional"]),
]
_DEFAULT_TAGS = ["ambient chill", "cinematic ambient", "lofi chill", "downtempo ambient"]


def _tags_for_topic(topic: str) -> str:
    """Pick a random tag combo that matches the topic mood."""
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
) -> str:
    """
    Download a trending CC-licensed music track from Jamendo that matches
    the video topic mood.

    Args:
        topic:       The quote/video topic (selects matching music mood/tags).
        client_id:   Jamendo API client ID (free — register at jamendo.com).
        duration:    Required minimum track duration in seconds.
        output_path: Destination path for the downloaded audio (.mp3).

    Returns:
        Path to the downloaded MP3 file on success, or falls back to
        synthesized ambient WAV if Jamendo is unavailable.
    """
    if not client_id:
        print("        JAMENDO_CLIENT_ID not set — using synthesized ambient music.")
        return _fallback_ambient(duration, output_path)

    tags = _tags_for_topic(topic)
    print(f"        Searching Jamendo for trending music (tags: {tags!r})...")

    try:
        track_url, track_name, artist = _find_track(client_id, tags, duration)
    except Exception as e:
        print(f"        Jamendo search failed ({e}) — using synthesized ambient music.")
        return _fallback_ambient(duration, output_path)

    print(f"        Music   : '{track_name}' by {artist} (CC-licensed, Jamendo)")

    # Ensure output path uses .mp3 extension since Jamendo serves MP3
    mp3_path = os.path.splitext(output_path)[0] + ".mp3"

    try:
        _download(track_url, mp3_path)
    except Exception as e:
        print(f"        Jamendo download failed ({e}) — using synthesized ambient music.")
        return _fallback_ambient(duration, output_path)

    return mp3_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Ordering strategies to rotate through for variety
_ORDER_OPTIONS = [
    "popularity_total",
    "popularity_month",
    "popularity_week",
    "releasedate",
]


def _find_track(client_id: str, tags: str, min_duration: float):
    """Query Jamendo and return (download_url, track_name, artist_name)."""
    # Use a random order strategy and a random offset so every run gets a
    # different pool of tracks instead of always the same top-10.
    order  = random.choice(_ORDER_OPTIONS)
    offset = random.randint(0, 150)

    params = {
        "client_id":     client_id,
        "format":        "json",
        "limit":         50,
        "offset":        offset,
        "order":         order,
        "tags":          tags,
        "audiodlformat": "mp31",            # mp31 = 320 kbps (highest quality)
        "minlength":     int(max(min_duration, 30)),   # Jamendo minimum: 30 s
        "boost":         "popularity_total", # prefer well-rated tracks
        "include":       "musicinfo",        # get genre/mood metadata
    }
    resp = requests.get(JAMENDO_TRACKS_URL, params=params, timeout=15)
    resp.raise_for_status()
    tracks = resp.json().get("results", [])

    if not tracks:
        # Retry with offset=0 in case the paged offset was beyond the result set
        params["offset"] = 0
        resp = requests.get(JAMENDO_TRACKS_URL, params=params, timeout=15)
        resp.raise_for_status()
        tracks = resp.json().get("results", [])

    if not tracks:
        # Broader fallback — try a random default tag combo
        params["tags"]   = random.choice(_DEFAULT_TAGS)
        params["offset"] = random.randint(0, 100)
        resp = requests.get(JAMENDO_TRACKS_URL, params=params, timeout=15)
        resp.raise_for_status()
        tracks = resp.json().get("results", [])

    if not tracks:
        raise ValueError("No tracks found on Jamendo")

    # Shuffle and pick a track that has a valid download URL
    random.shuffle(tracks)
    track = None
    for candidate in tracks:
        url = candidate.get("audiodownload", "").strip()
        # Some tracks don't have mp32 download enabled; fall back to the
        # streaming audio field which is always present
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
    )


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
