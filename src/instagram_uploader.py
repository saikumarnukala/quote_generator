"""
Instagram Reels Uploader via Meta Graph API (Resumable Upload).

Uploads are disabled by default.
Supports dry-run mode, token validation, video conformity validation,
chunked streaming upload, processing status polling, and publication.
"""

from __future__ import annotations

import os
import time
import urllib.error
import urllib.request
from typing import Optional

import requests

from config import (
    INSTAGRAM_ACCESS_TOKEN,
    INSTAGRAM_USER_ID,
)
from src.video_validator import validate_mp4_video

GRAPH_BASE = "https://graph.facebook.com/v25.0"


def upload_to_instagram(
    video_path: str,
    caption: str,
    user_id: Optional[str] = None,
    access_token: Optional[str] = None,
    dry_run: bool = False,
    force_upload: bool = False,
) -> Optional[str]:
    """
    Upload video to Instagram Reels.

    Returns the public Reel URL on success, or None on failure/skip.
    """
    uid = user_id or INSTAGRAM_USER_ID
    token = access_token or INSTAGRAM_ACCESS_TOKEN

    if dry_run:
        print("  [Instagram] DRY RUN MODE: Simulating upload.")
        print(f"    File: {video_path}")
        print(f"    Caption snippet: {caption[:80]}...")
        mock_id = f"mock_ig_{int(time.time())}"
        return f"https://www.instagram.com/p/{mock_id}/"

    if not force_upload:
        print("  [Instagram] Upload disabled by default. Pass --upload-instagram to enable.")
        return None

    if not uid or not token:
        print("  [Instagram] Missing credentials (INSTAGRAM_USER_ID, INSTAGRAM_ACCESS_TOKEN). Skipping upload.")
        return None

    # Validate video
    report = validate_mp4_video(video_path)
    if not report.is_valid:
        print(f"  [Instagram] Pre-upload validation failed: {report.errors}. Skipping upload.")
        return None

    print("  [Instagram] Initiating upload session to Meta Graph API...")

    file_size = os.path.getsize(video_path)

    # Step 1: Create upload session
    try:
        r = requests.post(
            f"{GRAPH_BASE}/{uid}/media",
            data={
                "media_type": "REELS",
                "upload_type": "resumable",
                "share_to_feed": "true",
                "caption": caption,
                "access_token": token,
            },
            timeout=30,
        )
    except Exception as e:
        print(f"  [Instagram] Network error creating upload session: {e}")
        return None

    if r.status_code != 200:
        err_data = r.json() if "json" in r.headers.get("content-type", "") else r.text
        print(f"  [Instagram] Failed to create upload session (HTTP {r.status_code}): {err_data}")
        if "Session has expired" in str(err_data) or "Error validating access token" in str(err_data):
            print("  [Instagram] CRITICAL: Your INSTAGRAM_ACCESS_TOKEN has expired. Please generate a fresh token at https://developers.facebook.com/tools/explorer/")
        return None

    resp_data = r.json()
    container_id = resp_data.get("id")
    upload_uri = resp_data.get("uri")

    if not container_id or not upload_uri:
        print(f"  [Instagram] Invalid response from Meta: {resp_data}")
        return None

    time.sleep(2)

    # Step 2: Stream video bytes in 4 MB chunks
    chunk_size = 4 * 1024 * 1024
    offset = 0
    print(f"  [Instagram] Uploading {file_size / (1024*1024):.1f} MB in chunks...")

    with open(video_path, "rb") as fh:
        while offset < file_size:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            req = urllib.request.Request(upload_uri, method="POST", data=chunk)
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("offset", str(offset))
            req.add_header("file_size", str(file_size))
            req.add_header("Content-Type", "application/octet-stream")

            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    up_code = resp.status
            except urllib.error.HTTPError as e:
                up_code = e.code
                if up_code not in (200, 201, 206):
                    print(f"  [Instagram] Chunk upload error HTTP {up_code}: {e.read().decode('utf-8', errors='ignore')}")
                    return None

            offset += len(chunk)

    # Step 3: Poll container status until FINISHED (max 5 mins)
    print("  [Instagram] Waiting for Meta media processing...", end="", flush=True)
    for _ in range(30):
        time.sleep(10)
        try:
            status_r = requests.get(
                f"{GRAPH_BASE}/{container_id}",
                params={"fields": "status_code,status", "access_token": token},
                timeout=30,
            )
            payload = status_r.json()
            code = payload.get("status_code", "")
            if code == "FINISHED":
                print(" ready.")
                break
            elif code == "ERROR":
                print(f"\n  [Instagram] Media processing error: {payload}")
                return None
            print(".", end="", flush=True)
        except Exception:
            pass
    else:
        print("\n  [Instagram] Processing timed out after 5 minutes.")
        return None

    # Step 4: Publish
    try:
        pub = requests.post(
            f"{GRAPH_BASE}/{uid}/media_publish",
            data={"creation_id": container_id, "access_token": token},
            timeout=30,
        )
        pub_data = pub.json()
        media_id = pub_data.get("id")
        if not media_id:
            print(f"  [Instagram] Publish failed: {pub_data}")
            return None

        reel_url = f"https://www.instagram.com/p/{media_id}/"
        print(f"  [Instagram] Published successfully -> {reel_url}")
        return reel_url
    except Exception as e:
        print(f"  [Instagram] Publish error: {e}")
        return None
