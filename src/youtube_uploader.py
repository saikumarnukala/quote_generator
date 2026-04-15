"""
YouTube Shorts uploader using YouTube Data API v3 + OAuth2 refresh token.

Required GitHub Secrets (env vars):
    YT_CLIENT_ID       — OAuth2 client ID (from Google Cloud Console)
    YT_CLIENT_SECRET   — OAuth2 client secret
    YT_REFRESH_TOKEN   — Offline refresh token (run scripts/get_youtube_token.py once)

Note: For a video to appear as a YouTube Short it must be ≤60 seconds AND 9:16.
      Longer videos are uploaded as regular videos with #Shorts in the title.
"""

import os

YT_CLIENT_ID      = os.getenv("YT_CLIENT_ID")
YT_CLIENT_SECRET  = os.getenv("YT_CLIENT_SECRET")
YT_REFRESH_TOKEN  = os.getenv("YT_REFRESH_TOKEN")

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GoogleRequest
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    _HAS_GOOGLE = True
except ImportError:
    _HAS_GOOGLE = False


def upload_to_youtube(
    video_path: str,
    title: str,
    description: str = "",
    tags: list = None,
) -> str | None:
    """
    Upload *video_path* to YouTube.

    Returns the public YouTube URL on success.
    Returns None and prints a warning if credentials are not configured.
    Raises RuntimeError on API failure.
    """
    if not all([YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN]):
        print("  YouTube: credentials not set (YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN), skipping.")
        return None

    if not _HAS_GOOGLE:
        print("  YouTube: google-api-python-client not installed, skipping.")
        return None

    print("  Uploading to YouTube Shorts...")

    credentials = Credentials(
        token=None,
        refresh_token=YT_REFRESH_TOKEN,
        client_id=YT_CLIENT_ID,
        client_secret=YT_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    credentials.refresh(GoogleRequest())

    youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)

    # Add #Shorts tag so YouTube categorises it correctly
    shorts_title = title if "#Shorts" in title else f"{title} #Shorts"

    body = {
        "snippet": {
            "title":       shorts_title[:100],
            "description": description.strip()[:5000],   # YouTube limit: 5000 chars
            "tags": (tags or [
                "shorts", "quotes", "nature", "peaceful",
                "motivation", "mindfulness", "relaxing",
            ])[:500],   # YouTube allows up to 500 chars of tags total
            "categoryId": "22",   # People & Blogs
        },
        "status": {
            "privacyStatus":           "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        _, response = request.next_chunk()

    video_id = response.get("id")
    if not video_id:
        raise RuntimeError(f"YouTube upload failed: {response}")

    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"  YouTube ✓ → {url}")
    return url