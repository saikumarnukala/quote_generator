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
PIXABAY_MUSIC_URL  = "https://pixabay.com/api/music/"

# ---------------------------------------------------------------------------
# Pixabay category map — CC0, no attribution required
# ---------------------------------------------------------------------------
_PIXABAY_CATEGORY_MAP = [
    (["peace", "mindful", "calm", "still", "quiet", "zen", "harmony", "balance"], "ambient"),
    (["nature", "forest", "ocean", "mountain", "landscape"],                       "cinematic"),
    (["love", "kindness", "compassion", "heart", "gratitude", "joy", "light"],     "pop"),
    (["courage", "strength", "success", "motivation", "inspire", "dream"],         "electronic"),
    (["wisdom", "patience", "philosophy"],                                          "jazz"),
    (["fun", "party", "celebrate", "dance"],                                        "beats"),
    (["darkness", "struggle", "pain", "loss"],                                      "drama"),
]
_PIXABAY_DEFAULT_CATEGORY = "cinematic"


def _pixabay_category_for_topic(topic: str) -> str:
    topic_lower = topic.lower()
    for keywords, category in _PIXABAY_CATEGORY_MAP:
        if any(kw in topic_lower for kw in keywords):
            return category
    return _PIXABAY_DEFAULT_CATEGORY


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
    used_ids: set | None = None,
    pixabay_api_key: str = "",
) -> dict:
    """
    Download a trending CC-licensed music track for the video.

    Fallback chain:
      1. Jamendo  (CC-BY / CC0, requires JAMENDO_CLIENT_ID)
      2. Pixabay  (CC0, requires PIXABAY_API_KEY)
      3. Internet Archive (CC-licensed, no key needed)
      4. Synthesized ambient (always works)

    Args:
        topic:           The quote/video topic (selects matching music mood).
        client_id:       Jamendo API client ID (free — register at jamendo.com).
        duration:        Required minimum track duration in seconds.
        output_path:     Destination path for the downloaded audio.
        used_ids:        Track IDs to skip — avoids repeating music across runs.
        pixabay_api_key: Pixabay API key (free — register at pixabay.com/api/docs).

    Returns:
        dict with keys: path, track_name, artist_name, license_url, track_id
    """
    _used = used_ids or set()
    _empty_attr = {"path": "", "track_name": "", "artist_name": "", "license_url": "", "track_id": ""}

    def _try_pixabay():
        result = _fetch_from_pixabay(topic, pixabay_api_key, duration, output_path, _used)
        if result:
            return result
        return None

    def _try_internet_archive():
        ia_path = _fetch_from_internet_archive(topic, duration, output_path)
        if ia_path:
            return {**_empty_attr, "path": ia_path}
        return None

    def _try_ambient():
        return {**_empty_attr, "path": _fallback_ambient(duration, output_path)}

    # ── 1. Jamendo ────────────────────────────────────────────────────────
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
                "path": mp3_path,
                "track_name": track_name,
                "artist_name": artist,
                "license_url": license_url,
                "track_id": str(track_id),
            }
        except Exception as e:
            print(f"        Jamendo failed ({e}) — trying Pixabay Music...")
    else:
        print("        JAMENDO_CLIENT_ID not set — trying Pixabay Music...")

    # ── 2. Pixabay Music (CC0) ────────────────────────────────────────────
    result = _try_pixabay()
    if result:
        return result
    if pixabay_api_key:
        print("        Pixabay Music failed — trying Internet Archive CC music...")
    else:
        print("        PIXABAY_API_KEY not set — trying Internet Archive CC music...")

    # ── 3. Internet Archive ───────────────────────────────────────────────
    result = _try_internet_archive()
    if result:
        return result
    print("        Internet Archive also unavailable — using synthesized ambient.")

    # ── 4. Synthesized ambient (guaranteed) ───────────────────────────────
    return _try_ambient()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Always sort by popularity — we want the hits, not random filler
_ORDER_OPTIONS = [
    "popularity_total",
    "popularity_month",
    "popularity_week",
]


def _find_track(client_id: str, tags: str, min_duration: float, used_ids: set | None = None):
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
        "client_id":     client_id,
        "format":        "json",
        "limit":         50,           # fetch more candidates so filters have enough to work with
        "boost":         "popularity_total",
        "include":       "musicinfo+licenses",
        "order":         order,
        # NOTE: audiodlformat removed — specifying "mp32" causes tracks without that
        # exact format to return with empty audiodownload, drastically shrinking the pool.
        # We accept any audio URL Jamendo provides (audiodownload OR audio stream).
        # NOTE: content_id_free removed — it cuts the pool too aggressively and most
        # CC-BY tracks are fine for YouTube. We still filter by license below.
    }

    # --- Attempt 1: fuzzytags search (broader than strict tags) -----------
    params = {
        **base_params,
        "fuzzytags": tags,
        "offset":    offset,
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

    # Shuffle all results for variety (was: only top 10)
    random.shuffle(tracks)

    _skip = used_ids or set()
    track = None
    for candidate in tracks:
        # Skip tracks used in previous runs
        if str(candidate.get("id", "")) in _skip:
            continue
        # Only allow CC BY and CC0 licenses — block NC/ND/SA
        lic = candidate.get("license_ccurl", "").lower()
        if not lic:
            continue  # unknown license — skip
        if "-nc" in lic or "-nd" in lic or "-sa" in lic:
            continue
        # Prefer direct download URL; fall back to streaming URL
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
        str(track.get("id", "")),
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


def _fetch_from_internet_archive(topic: str, min_duration: float, output_path: str) -> str | None:
    """
    Download a CC-licensed instrumental track from Internet Archive — no API key needed.

    Searches for CC-licensed audio matching the topic mood, picks from the most-downloaded
    results, then streams the first MP3 long enough to cover the video.
    Returns the local mp3 path on success, None on any failure.
    """
    mood_tag = _tags_for_topic(topic)
    print(f"        Searching Internet Archive for CC music (tag: {mood_tag!r})...")

    try:
        resp = requests.get(
            "https://archive.org/advancedsearch.php",
            params={
                "q": (
                    f"mediatype:audio subject:instrumental {mood_tag} "
                    "licenseurl:creativecommons.org"
                ),
                "fl": "identifier,title,creator",
                "sort[]": "downloads desc",
                "rows": 20,
                "page": 1,
                "output": "json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        docs = resp.json().get("response", {}).get("docs", [])
    except Exception as e:
        print(f"        Internet Archive search failed ({e})")
        return None

    if not docs:
        # Broaden search — no mood tag, just CC instrumental audio
        try:
            resp = requests.get(
                "https://archive.org/advancedsearch.php",
                params={
                    "q": "mediatype:audio subject:instrumental licenseurl:creativecommons.org",
                    "fl": "identifier,title,creator",
                    "sort[]": "downloads desc",
                    "rows": 20,
                    "page": 1,
                    "output": "json",
                },
                timeout=15,
            )
            resp.raise_for_status()
            docs = resp.json().get("response", {}).get("docs", [])
        except Exception:
            return None

    top = docs[:10]
    random.shuffle(top)

    for doc in top:
        identifier = doc.get("identifier", "")
        if not identifier:
            continue
        try:
            meta = requests.get(
                f"https://archive.org/metadata/{identifier}",
                timeout=15,
            )
            meta.raise_for_status()
            files = meta.json().get("files", [])
            # `length` in Archive.org file metadata is duration in seconds (as string)
            mp3s = [
                f for f in files
                if f.get("name", "").lower().endswith(".mp3")
                and float(f.get("length") or 0) >= min(min_duration, 30)
            ]
            if not mp3s:
                continue
            selected = mp3s[0]
            url = f"https://archive.org/download/{identifier}/{selected['name']}"
            mp3_out = os.path.splitext(output_path)[0] + ".mp3"
            print(f"        Downloading: '{doc.get('title', identifier)}' (Internet Archive CC)...")
            _download(url, mp3_out)
            print(f"        Music   : '{doc.get('title', identifier)}' by {doc.get('creator', 'Unknown')}")
            print(f"        License : https://creativecommons.org/licenses/")
            return mp3_out
        except Exception:
            continue

    return None


def _fetch_from_pixabay(
    topic: str,
    api_key: str,
    min_duration: float,
    output_path: str,
    used_ids: set | None = None,
) -> dict | None:
    """
    Download a CC0 track from Pixabay Music — royalty-free, no attribution required.
    Returns a music info dict on success, None on any failure.

    API key: free at https://pixabay.com/api/docs/ (same key works for images/videos/music)
    """
    if not api_key:
        return None

    _skip = used_ids or set()
    category = _pixabay_category_for_topic(topic)
    print(f"        Searching Pixabay Music (category: {category!r})...")

    def _query(params: dict) -> list:
        try:
            r = requests.get(PIXABAY_MUSIC_URL, params=params, timeout=15)
            r.raise_for_status()
            return r.json().get("hits", [])
        except Exception as exc:
            print(f"        Pixabay Music query failed ({exc})")
            return []

    # Attempt 1 — category + duration filter
    hits = _query({"key": api_key, "category": category, "min_duration": int(min_duration), "per_page": 30})

    # Attempt 2 — no category, any mood
    if not hits:
        hits = _query({"key": api_key, "min_duration": int(min_duration), "per_page": 30})

    # Attempt 3 — no filters at all
    if not hits:
        hits = _query({"key": api_key, "per_page": 30})

    if not hits:
        return None

    random.shuffle(hits)

    for hit in hits:
        track_id = str(hit.get("id", ""))
        if track_id in _skip:
            continue

        # Pixabay returns the audio under various field names depending on API version
        audio_url = (
            hit.get("audio")
            or hit.get("audioFile")
            or hit.get("full_audio_url")
            or hit.get("preview_url")
            or ""
        )
        if not audio_url or not audio_url.startswith("http"):
            continue

        title  = hit.get("title") or hit.get("tags", "Unknown")[:40]
        artist = hit.get("user", "Pixabay Artist")

        mp3_path = os.path.splitext(output_path)[0] + ".mp3"
        try:
            print(f"        Downloading: '{title}' by {artist} (Pixabay CC0)...")
            _download(audio_url, mp3_path)
            print(f"        License : https://pixabay.com/service/terms/ (CC0)")
            return {
                "path":        mp3_path,
                "track_name":  title,
                "artist_name": artist,
                "license_url": "https://pixabay.com/service/terms/",
                "track_id":    f"pixabay-{track_id}",
            }
        except Exception as e:
            print(f"        Download failed ({e}), trying next Pixabay track...")
            continue

    return None


def _fallback_ambient(duration: float, output_path: str) -> str:
    from src.ambient_generator import generate_ambient  # local import to avoid circular dep
    wav_path = os.path.splitext(output_path)[0] + ".wav"
    return generate_ambient(duration, wav_path)
