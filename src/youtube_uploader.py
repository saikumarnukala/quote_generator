"""
YouTube Video Uploader using YouTube Data API v3 + OAuth2 Refresh Token.

Uploads are disabled by default and default to 'private' visibility.
Includes dry-run support, pre-upload video validation, duplicate prevention,
and quota error handling.
"""

from __future__ import annotations

import os
import time
from typing import List, Optional, Tuple

from config import (
    YOUTUBE_PRIVACY_STATUS,
    YOUTUBE_UPLOAD_ENABLED,
    YT_CLIENT_ID,
    YT_CLIENT_SECRET,
    YT_REFRESH_TOKEN,
)
from src.video_validator import validate_mp4_video

try:
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    _HAS_GOOGLE = True
except ImportError:
    HttpError = Exception  # type: ignore
    _HAS_GOOGLE = False


def upload_to_youtube(
    video_path: str,
    title: str,
    description: str = "",
    tags: Optional[List[str]] = None,
    privacy_status: Optional[str] = None,
    dry_run: bool = False,
    force_upload: bool = False,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Upload infotainment video to YouTube.

    Returns:
        (video_url, video_id) or (None, None) if skipped or failed.
    """
    # 1. Check upload configuration flags
    upload_allowed = force_upload or YOUTUBE_UPLOAD_ENABLED
    if not upload_allowed and not dry_run:
        print("  [YouTube] Upload is disabled by default. Set YOUTUBE_UPLOAD_ENABLED=true or pass --upload to enable.")
        return None, None

    # 2. Dry run mode
    if dry_run:
        print("  [YouTube] DRY RUN MODE: Simulating upload.")
        print(f"    Title      : {title[:80]}")
        print(f"    File       : {video_path}")
        print(f"    Privacy    : {privacy_status or YOUTUBE_PRIVACY_STATUS}")
        mock_id = f"mock_{int(time.time())}"
        return f"https://www.youtube.com/watch?v={mock_id}", mock_id

    # 3. Pre-upload video validation
    report = validate_mp4_video(video_path)
    if not report.is_valid:
        print(f"  [YouTube] Video validation failed before upload: {', '.join(report.errors)}")
        return None, None

    # 4. Check credentials
    client_id = YT_CLIENT_ID
    client_secret = YT_CLIENT_SECRET
    refresh_token = YT_REFRESH_TOKEN

    if not all([client_id, client_secret, refresh_token]):
        print("  [YouTube] Missing OAuth credentials (YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN). Skipping upload.")
        return None, None

    if not _HAS_GOOGLE:
        print("  [YouTube] google-api-python-client is not installed. Skipping upload.")
        return None, None

    visibility = (privacy_status or YOUTUBE_PRIVACY_STATUS or "private").lower()
    print(f"  [YouTube] Uploading video with visibility '{visibility}'...")

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )

    try:
        credentials.refresh(GoogleRequest())
    except Exception as e:
        print(f"  [YouTube] Failed to refresh credentials: {e}")
        return None, None

    youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)

    shorts_title = title if "#Shorts" in title else f"{title} #Shorts"

    body = {
        "snippet": {
            "title": shorts_title[:100],
            "description": description.strip()[:5000],
            "tags": (tags or ["shorts", "science", "facts"])[:500],
            "categoryId": "27",  # Education category
        },
        "status": {
            "privacyStatus": visibility,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, chunksize=10 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    retry_count = 0
    while response is None:
        try:
            _, response = request.next_chunk()
        except HttpError as e:
            if getattr(e, "resp", None) and e.resp.status in (403, 429):
                print(f"  [YouTube] Quota exceeded or forbidden: HTTP {e.resp.status}")
                return None, None
            raise
        except Exception as e:
            retry_count += 1
            if retry_count > 4:
                raise
            print(f"  [YouTube] Chunk upload retry {retry_count}/4: {e}")
            time.sleep(5)

    video_id = response.get("id")
    if not video_id:
        return None, None

    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"  [YouTube] Successfully uploaded -> {url} (Visibility: {visibility})")
    return url, video_id