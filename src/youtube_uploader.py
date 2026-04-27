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
import time

# YouTube credentials will be fetched inside the function to ensure they are available after load_dotenv()

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GoogleRequest
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    _HAS_GOOGLE = True
except ImportError:
    HttpError = Exception  # Fallback
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
    yt_client_id     = os.getenv("YT_CLIENT_ID")
    yt_client_secret = os.getenv("YT_CLIENT_SECRET")
    yt_refresh_token = os.getenv("YT_REFRESH_TOKEN")

    if not all([yt_client_id, yt_client_secret, yt_refresh_token]):
        print("  YouTube: credentials not set (YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN), skipping.")
        print(f"    YT_CLIENT_ID: {'SET' if yt_client_id else 'MISSING'}")
        print(f"    YT_CLIENT_SECRET: {'SET' if yt_client_secret else 'MISSING'}")
        print(f"    YT_REFRESH_TOKEN: {'SET' if yt_refresh_token else 'MISSING'}")
        return None

    if not _HAS_GOOGLE:
        print("  YouTube: google-api-python-client not installed, skipping.")
        return None

    print("  Uploading to YouTube Shorts...")

    credentials = Credentials(
        token=None,
        refresh_token=yt_refresh_token,
        client_id=yt_client_id,
        client_secret=yt_client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    try:
        credentials.refresh(GoogleRequest())
    except Exception as e:
        print(f"  YouTube: failed to refresh credentials: {e}")
        print("    Try running 'python scripts/get_youtube_token.py' again to get a fresh refresh token.")
        return None

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
            if e.resp.status in (403, 429):
                print(f"  YouTube ERROR: Quota exceeded or forbidden ({e.resp.status}).")
                return None
            raise
        except Exception as e:
            retry_count += 1
            if retry_count > 5:
                raise
            print(f"  YouTube chunk error (attempt {retry_count}/5): {e} — retrying in 10s...")
            time.sleep(10)

    video_id = response.get("id")
    if not video_id:
        raise RuntimeError(f"YouTube upload failed: {response}")

    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"  YouTube [OK] -> {url}")
    return url