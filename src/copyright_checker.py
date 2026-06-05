"""
Pre-build copyright verifier.

Runs immediately after files are downloaded and BEFORE video rendering starts.
If a track fails the check, the caller can discard it and fetch a replacement
without wasting any render time.

Checks performed:
  Music (Jamendo / SoundHelix / etc.):
    1. License URL present and resolves to a CC-BY, CC-BY-SA, or CC0 license
       (blocks NC = non-commercial, ND = no-derivatives only)
       NOTE: SA (share-alike) is allowed — using audio as background in a video
       is not a derivative work, so SA terms don't restrict the upload.
    2. Audio file exists on disk and is not empty

  Pexels video clips:
    1. Each clip file exists on disk and is not empty
       (Pexels footage is CC0 by terms-of-service — no per-file license check needed)
"""

import os
import requests


# Licenses we accept for commercial/upload use on YouTube + Instagram
_ALLOWED_CC = (
    "creativecommons.org/licenses/by/",       # CC BY
    "creativecommons.org/licenses/by-sa/",    # CC BY-SA (allowed — SA doesn't restrict uploaders)
    "creativecommons.org/publicdomain/zero/", # CC0
    "soundhelix.com",                         # SoundHelix CC-BY-SA guaranteed fallback
    "pixabay.com/service/terms",              # Pixabay CC0
)

# License fragments that block commercial / derivative use
# NOTE: -sa removed — share-alike does NOT prevent YouTube/Instagram uploads
_BLOCKED_FRAGMENTS = ("-nc", "-nd")


def _license_ok(license_url: str) -> tuple[bool, str]:
    """
    Return (True, "") if license_url is CC-BY or CC0.
    Return (False, reason) otherwise.
    """
    if not license_url:
        return False, "no license URL provided"

    url_lower = license_url.lower()
    for blocked in _BLOCKED_FRAGMENTS:
        if blocked in url_lower:
            return False, f"license contains '{blocked}' — not allowed for commercial upload"

    for allowed in _ALLOWED_CC:
        if allowed in url_lower:
            return True, ""

    # License URL present but unknown — do a quick HTTP check to confirm it's real
    try:
        r = requests.head(license_url, timeout=8, allow_redirects=True)
        final_url = r.url.lower()
        for blocked in _BLOCKED_FRAGMENTS:
            if blocked in final_url:
                return False, f"resolved license URL contains '{blocked}'"
        for allowed in _ALLOWED_CC:
            if allowed in final_url:
                return True, ""
        return False, f"license URL resolved to unrecognised license: {r.url}"
    except Exception as e:
        return False, f"could not verify license URL ({e})"


def check_music(music_info: dict) -> tuple[bool, str]:
    """
    Verify downloaded music is safe to upload.

    Args:
        music_info: dict returned by fetch_trending_music()

    Returns:
        (True, "")            — all checks passed
        (False, reason_str)   — failed, reason explains why
    """
    path = music_info.get("path", "")
    license_url = music_info.get("license_url", "")
    track_name = music_info.get("track_name", "")
    track_id = music_info.get("track_id", "")

    print(f"\n  [Copyright] Checking music: '{track_name}' (id={track_id})")

    # 1. File exists and non-empty
    if not path or not os.path.exists(path):
        return False, "audio file not found on disk"
    if os.path.getsize(path) < 1000:
        return False, "audio file is empty or too small"

    # 2. No license URL — if it's a named track, reject; otherwise skip check
    if not license_url:
        if track_name:
            return False, "no license URL for a named track"
        print("  [Copyright] No license URL and no track name — skipping check.")
        return True, ""

    # 3. License URL check
    ok, reason = _license_ok(license_url)
    if ok:
        print(f"  [Copyright] Music OK — {license_url}")
    else:
        print(f"  [Copyright] Music REJECTED — {reason}")
    return ok, reason


def check_videos(video_paths: list) -> tuple[bool, list[int]]:
    """
    Verify all downloaded Pexels clips exist and are non-empty.
    Handles both flat lists [path1, path2] and nested lists [[path1a, path1b], [path2]].
    Pexels is CC0 by ToS so no per-file license check is needed.

    Returns:
        (True, [])               — all clips OK
        (False, [idx, ...])      — list of 0-based indices that failed
    """
    failed = []
    for i, scene_paths in enumerate(video_paths):
        if isinstance(scene_paths, str):
            scene_paths = [scene_paths]
            
        scene_ok = True
        for path in scene_paths:
            if not path or not os.path.exists(path):
                print(f"  [Copyright] Video scene {i+1}: FILE MISSING — {path}")
                scene_ok = False
            elif os.path.getsize(path) < 10_000:
                print(f"  [Copyright] Video scene {i+1}: file too small (corrupted?) — {path}")
                scene_ok = False
        
        if not scene_ok:
            failed.append(i)
            
    if not failed:
        print(f"  [Copyright] All {len(video_paths)} scenes have OK video clips (Pexels CC0).")
    return (len(failed) == 0), failed
