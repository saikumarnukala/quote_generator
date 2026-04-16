"""
Pre-build copyright verifier.

Runs immediately after files are downloaded and BEFORE video rendering starts.
If a track fails the check, the caller can discard it and fetch a replacement
without wasting any render time.

Checks performed:
  Music (Jamendo / Internet Archive):
    1. License URL present and resolves to a CC-BY or CC0 license
       (blocks NC = non-commercial, ND = no-derivatives, SA = share-alike)
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
    "creativecommons.org/publicdomain/zero/", # CC0
    "creativecommons.org/licenses/by/4",
    "creativecommons.org/licenses/by/3",
)

# License fragments that block commercial / derivative use
_BLOCKED_FRAGMENTS = ("-nc", "-nd", "-sa")


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

    # 2. No license URL means it's the synthesized ambient fallback — always safe
    if not license_url:
        if track_name:
            # Has a name but no license — reject
            return False, "no license URL for a named track"
        print("  [Copyright] Synthesized ambient — no license check needed.")
        return True, ""

    # 3. License URL check
    ok, reason = _license_ok(license_url)
    if ok:
        print(f"  [Copyright] Music OK — {license_url}")
    else:
        print(f"  [Copyright] Music REJECTED — {reason}")
    return ok, reason


def check_videos(video_paths: list[str]) -> tuple[bool, list[int]]:
    """
    Verify all downloaded Pexels clips exist and are non-empty.
    Pexels is CC0 by ToS so no per-file license check is needed.

    Returns:
        (True, [])               — all clips OK
        (False, [idx, ...])      — list of 0-based indices that failed
    """
    failed = []
    for i, path in enumerate(video_paths):
        if not path or not os.path.exists(path):
            print(f"  [Copyright] Video scene {i+1}: FILE MISSING — {path}")
            failed.append(i)
        elif os.path.getsize(path) < 10_000:
            print(f"  [Copyright] Video scene {i+1}: file too small (corrupted?) — {path}")
            failed.append(i)
    if not failed:
        print(f"  [Copyright] All {len(video_paths)} video clips OK (Pexels CC0).")
    return (len(failed) == 0), failed
