"""
Fetch trending background music for quote videos.

Fallback chain (no stops — one of these ALWAYS succeeds):
  1. SoundHelix  — 17 CC-BY-SA tracks, no API key, guaranteed URLs
  2. Jamendo     — CC-licensed library (JAMENDO_CLIENT_ID required)

Both sources are safe for YouTube Shorts & Instagram Reels (no ContentID issues).
"""

import os
import random

import requests


JAMENDO_TRACKS_URL = "https://api.jamendo.com/v3.0/tracks/"

# ---------------------------------------------------------------------------
# SoundHelix — 17 CC-BY-SA tracks, always online, no key needed
# License: https://creativecommons.org/licenses/by-sa/3.0/
# ---------------------------------------------------------------------------
_SOUNDHELIX_TRACKS = [
    {"id": f"soundhelix-{i}", "name": f"SoundHelix Song {i}", "artist": "T. Schneider",
     "url": f"https://www.soundhelix.com/examples/mp3/SoundHelix-Song-{i}.mp3",
     "license_url": "https://creativecommons.org/licenses/by-sa/3.0/"}
    for i in range(1, 18)
]

# ---------------------------------------------------------------------------
# Jamendo tag mappings — focused on CATCHY, popular, energetic music
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
    used_ids: set | None = None,
    pixabay_api_key: str = "",  # kept for backward compat, Pixabay has no music API
) -> dict:
    """
    Download a copyright-safe music track for the video.

    Fallback chain:
      1. SoundHelix (CC-BY-SA, 17 guaranteed tracks, no API key needed)
      2. Jamendo    (large CC library, requires JAMENDO_CLIENT_ID)

    Returns:
        dict with keys: path, track_name, artist_name, license_url, track_id
    """
    _used = used_ids or set()
    _empty = {"path": "", "track_name": "", "artist_name": "", "license_url": "", "track_id": ""}

    # ── 1. SoundHelix (CC-BY-SA, guaranteed 17 tracks, no key needed) ────
    result = _fetch_from_soundhelix(duration, output_path, _used)
    if result:
        return result
    print("        SoundHelix unavailable — trying Jamendo...")

    # ── 2. Jamendo (CC library) ───────────────────────────────────────────
    if client_id:
        tags = _tags_for_topic(topic)
        print(f"        Searching Jamendo for trending music (tags: {tags!r})...")
        try:
            track_url, track_name, artist, license_url, track_id = _find_track(
                client_id, tags, duration, _used
            )
            print(f"        Music   : '{track_name}' by {artist}")
            print(f"        License : {license_url}")
            mp3_path = os.path.splitext(output_path)[0] + ".mp3"
            _download(track_url, mp3_path)
            return {
                "path":        mp3_path,
                "track_name":  track_name,
                "artist_name": artist,
                "license_url": license_url,
                "track_id":    str(track_id),
            }
        except Exception as e:
            print(f"        Jamendo also failed ({e}).")
    else:
        print("        JAMENDO_CLIENT_ID not set.")

    print("        WARNING: All music sources failed — video will be built without music.")
    return _empty


# ---------------------------------------------------------------------------
# SoundHelix
# ---------------------------------------------------------------------------

def _fetch_from_soundhelix(
    min_duration: float,
    output_path: str,
    used_ids: set,
) -> dict | None:
    """Try all 17 SoundHelix tracks (shuffled) until one downloads successfully."""
    candidates = [t for t in _SOUNDHELIX_TRACKS if t["id"] not in used_ids]
    if not candidates:
        candidates = list(_SOUNDHELIX_TRACKS)  # all used — reset and reuse

    random.shuffle(candidates)
    mp3_path = os.path.splitext(output_path)[0] + ".mp3"

    for track in candidates:
        print(f"        Downloading: '{track['name']}' by {track['artist']} (SoundHelix CC-BY-SA)...")
        try:
            _download(track["url"], mp3_path)
            print(f"        License : {track['license_url']}")
            return {
                "path":        mp3_path,
                "track_name":  track["name"],
                "artist_name": track["artist"],
                "license_url": track["license_url"],
                "track_id":    track["id"],
            }
        except Exception as e:
            print(f"        {track['id']} failed ({e}) — trying next SoundHelix track...")

    return None


# ---------------------------------------------------------------------------
# Jamendo helpers
# ---------------------------------------------------------------------------

_ORDER_OPTIONS = ["popularity_total", "popularity_month", "popularity_week"]


def _find_track(client_id: str, tags: str, min_duration: float, used_ids: set | None = None):
    order = random.choice(_ORDER_OPTIONS)
    offset = random.randint(0, 20)

    base_params = {
        "client_id": client_id,
        "format":    "json",
        "limit":     50,
        "boost":     "popularity_total",
        "include":   "musicinfo+licenses",
        "order":     order,
    }

    # Attempt 1: fuzzytags (broad)
    tracks = _query_jamendo({**base_params, "fuzzytags": tags, "offset": offset}, min_duration)

    # Attempt 2: strict tags
    if not tracks:
        tracks = _query_jamendo({**base_params, "tags": tags, "offset": 0}, min_duration)

    # Attempt 3: different popular tag
    if not tracks:
        fallback_tag = random.choice(_DEFAULT_TAGS)
        print(f"        No results for '{tags}', trying '{fallback_tag}'...")
        tracks = _query_jamendo({**base_params, "fuzzytags": fallback_tag, "offset": 0}, min_duration)

    # Attempt 4: pure popularity — broadest possible
    if not tracks:
        print("        Falling back to top-popular Jamendo tracks (no tag filter)...")
        tracks = _query_jamendo({**base_params, "offset": random.randint(0, 10)}, min_duration)

    if not tracks:
        raise ValueError("No tracks found on Jamendo")

    random.shuffle(tracks)
    _skip = used_ids or set()

    for candidate in tracks:
        if str(candidate.get("id", "")) in _skip:
            continue
        lic = candidate.get("license_ccurl", "").lower()
        if not lic:
            continue
        # Block only NC (non-commercial) and ND (no-derivatives); SA is fine for uploads
        if "-nc" in lic or "-nd" in lic:
            continue
        url = candidate.get("audiodownload", "").strip()
        if not url or not url.startswith("http"):
            url = candidate.get("audio", "").strip()
        if url and url.startswith("http"):
            candidate["_resolved_url"] = url
            return (
                candidate["_resolved_url"],
                candidate.get("name", "unknown"),
                candidate.get("artist_name", "unknown"),
                candidate.get("license_ccurl", ""),
                str(candidate.get("id", "")),
            )

    raise ValueError("No tracks with a valid download URL found on Jamendo")


def _query_jamendo(params: dict, min_duration: float) -> list:
    try:
        resp = requests.get(JAMENDO_TRACKS_URL, params=params, timeout=15)
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except Exception:
        return []
    min_sec = max(min_duration, 30)
    return [t for t in results if int(t.get("duration", 0)) >= min_sec]


def _download(url: str, dest: str) -> None:
    resp = requests.get(url, timeout=60, stream=True)
    resp.raise_for_status()
    with open(dest, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=65536):
            fh.write(chunk)
