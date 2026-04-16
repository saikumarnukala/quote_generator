"""
Fetch real 4K nature footage from Pexels API.
Searches by keyword and downloads the best portrait (9:16) or landscape clip,
then pre-transcodes to 1080x1920 portrait for Shorts/Reels so MoviePy
processes lightweight frames instead of raw 4K.
"""

import os
import random
import subprocess
import time

import requests

PEXELS_SEARCH = "https://api.pexels.com/videos/search"

# Target portrait dimensions
TARGET_W = 1080
TARGET_H = 1920

# Minimum acceptable source resolution
MIN_W = 720
MIN_H = 720


def _best_file(video_files: list) -> dict | None:
    """
    Pick the best file: prefer ~1920p HD over 4K for faster processing.
    Falls back to 4K if nothing smaller is available.
    """
    scored = []
    for f in video_files:
        w = f.get("width", 0)
        h = f.get("height", 0)
        if w < MIN_W or h < MIN_H:
            continue
        pixels = w * h
        # Prefer HD (roughly 1080p-1440p range) — faster to process than 4K
        preference = 0 if pixels <= 1920 * 1080 * 2 else 1
        scored.append((preference, pixels, f))
    if not scored:
        return None
    scored.sort(key=lambda x: (x[0], x[1]))
    return scored[0][2]


def _download(url: str, dest: str, api_key: str) -> bool:
    """Stream-download a video file."""
    headers = {"Authorization": api_key}
    try:
        r = requests.get(url, headers=headers, stream=True, timeout=120)
        if r.status_code != 200:
            return False
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        return os.path.getsize(dest) > 10_000
    except Exception:
        return False


def _get_ffmpeg() -> str:
    """Return path to the ffmpeg executable (system or imageio-bundled)."""
    import shutil
    # Try system ffmpeg first
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    # Fall back to imageio-ffmpeg bundled binary
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"  # Last resort — will fail gracefully if missing


def _pretranscode(src: str, dest: str) -> bool:
    """
    Use FFmpeg to scale+crop the source clip to 1080×1920 (portrait cover).
    This runs once at download time so MoviePy never touches large frames.
    Returns True on success, False if FFmpeg is unavailable or fails.
    """
    # Cover-fit to 1080×1920: scale up so both dims are >= target, then centre-crop
    vf = (
        "scale=w=1080:h=1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920"
    )
    cmd = [
        _get_ffmpeg(), "-y", "-i", src,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy",
        "-loglevel", "error",
        dest,
    ]
    try:
        result = subprocess.run(cmd, timeout=300, capture_output=True)
        if result.returncode == 0 and os.path.getsize(dest) > 10_000:
            return True
        return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def fetch_nature_video(
    search_query: str,
    api_key: str,
    output_path: str,
    fallback_queries: list[str] | None = None,
    retries: int = 3,
) -> str:
    """
    Search Pexels for a nature clip matching `search_query`,
    download the best quality file to `output_path`.

    Falls back to `fallback_queries` if no results found.
    Returns output_path on success, raises RuntimeError on failure.
    """
    headers = {"Authorization": api_key}

    all_queries = [search_query] + (fallback_queries or [
        "peaceful nature",
        "forest rain",
        "calm water",
        "sunrise mountains",
    ])

    for query in all_queries:
        for attempt in range(retries):
            try:
                params = {
                    "query": query,
                    "per_page": 15,
                    "orientation": "portrait",  # prefer 9:16 native
                    "size": "large",
                }
                resp = requests.get(
                    PEXELS_SEARCH, headers=headers, params=params, timeout=30
                )

                if resp.status_code == 429:
                    time.sleep(10)
                    continue

                if resp.status_code != 200:
                    break

                videos = resp.json().get("videos", [])

                # Also try landscape if portrait has nothing
                if not videos:
                    params["orientation"] = "landscape"
                    resp = requests.get(
                        PEXELS_SEARCH, headers=headers, params=params, timeout=30
                    )
                    videos = resp.json().get("videos", []) if resp.status_code == 200 else []

                if not videos:
                    break

                # Shuffle to avoid always picking the same clip for same topic
                random.shuffle(videos)

                for video in videos:
                    best = _best_file(video.get("video_files", []))
                    if best is None:
                        continue
                    url = best["link"]
                    w, h = best.get("width", 0), best.get("height", 0)
                    print(f"        Downloading: {query!r} -> {video.get('id')} ({w}x{h})")
                    # Download to a temp path, then pre-transcode to target resolution
                    raw_path = output_path + ".raw.mp4"
                    if _download(url, raw_path, api_key):
                        print(f"          Pre-transcoding to 1080x1920 ...", end=" ", flush=True)
                        if _pretranscode(raw_path, output_path):
                            os.remove(raw_path)
                            print("done")
                        else:
                            # FFmpeg not available — use raw file as-is
                            os.replace(raw_path, output_path)
                            print("(FFmpeg unavailable, using raw)")
                        return output_path

            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError) as e:
                if attempt < retries - 1:
                    time.sleep(5)
                else:
                    print(f"        Network error for query {query!r}: {e}")

    raise RuntimeError(
        f"Could not download any video for queries: {all_queries}"
    )
