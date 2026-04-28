"""
Instagram Reels uploader via Meta Graph API — resumable upload (no external hosting needed).

Required GitHub Secrets (env vars):
    INSTAGRAM_USER_ID       — numeric Instagram user ID
    INSTAGRAM_ACCESS_TOKEN  — long-lived access token (valid 60 days, auto-refreshed)

How to get these:
    1. Go to https://developers.facebook.com → Create app → Add "Instagram Graph API"
    2. Connect your Instagram Business or Creator account to a Facebook Page
    3. Use the Graph API Explorer to generate a long-lived token with scopes:
           instagram_basic, instagram_content_publish, pages_read_engagement
    4. Store INSTAGRAM_USER_ID and INSTAGRAM_ACCESS_TOKEN as GitHub Secrets
"""

import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

import requests

from config import INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET

GRAPH_BASE  = "https://graph.facebook.com/v25.0"
UPLOAD_BASE = "https://rupload.facebook.com/video-upload/v25.0"

INSTAGRAM_USER_ID      = os.getenv("INSTAGRAM_USER_ID")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")


def _refresh_token(token: str) -> str:
    """Refresh a long-lived Graph API token using fb_exchange_token.
    Requires INSTAGRAM_APP_SECRET (Meta app secret) to be set.
    Falls back to the original token if refresh fails.
    """
    if not INSTAGRAM_APP_SECRET:
        return token
    try:
        # Graph API: exchange existing long-lived token for a fresh 60-day token
        r = requests.get(
            f"{GRAPH_BASE}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": INSTAGRAM_APP_ID or "",
                "client_secret": INSTAGRAM_APP_SECRET,
                "fb_exchange_token": token,
            },
            timeout=30,
        )
        if r.status_code == 200:
            new_token = r.json().get("access_token")
            if new_token:
                print("  Instagram: token refreshed successfully.")
                return new_token
    except Exception as e:
        print(f"  Instagram: token refresh failed ({e}), using existing token.")
    return token


def _transcode_for_instagram(src: str) -> tuple[str, bool]:
    """
    Re-encode *src* with Instagram-safe FFmpeg settings.

    Returns (path, is_temp) where is_temp=True means the caller must delete the file.
    Falls back to (src, False) if FFmpeg is unavailable or fails.

    Key settings that prevent ProcessingFailedError:
      - Exact 1080x1920 9:16 ratio (Instagram is strict about dimensions)
      - yuv420p            : no alpha channel
      - cfr 30fps          : constant frame rate (VFR silently rejected by Meta)
      - movflags faststart : moov atom at start (required for streaming/processing)
      - H.264 main L4.0   : reliable profile for 1080p vertical video
      - AAC stereo 44100   : required audio spec
      - 2-sec keyframes    : required for Meta's segment processing
    """
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    ffprobe_bin = ffmpeg.replace("ffmpeg", "ffprobe")

    # Detect whether the source already has an audio stream
    has_audio = False
    try:
        probe = subprocess.run(
            [ffprobe_bin, "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0", src],
            capture_output=True, text=True, timeout=15,
        )
        has_audio = "audio" in probe.stdout
    except Exception:
        pass

    tmp = tempfile.mktemp(suffix="_ig.mp4")

    # Base video command (always re-encode to guarantee compliance)
    cmd = [
        ffmpeg, "-y", "-i", src,
    ]
    # If the input has no audio track, inject a silent one so Meta doesn't reject it.
    if not has_audio:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest"]

    cmd += [
        "-vf",        "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps=30",
        "-c:v",       "libx264",
        "-profile:v", "main",
        "-level:v",   "4.0",
        "-preset",    "fast",
        "-pix_fmt",   "yuv420p",
        "-vsync",     "cfr",
        "-bf",        "0",
        "-b:v",       "4000k",
        "-maxrate",   "4000k",
        "-bufsize",   "8000k",
        "-x264opts",  "keyint=60:min-keyint=60:no-scenecut",
        "-c:a",       "aac",
        "-ar",        "44100",
        "-ac",        "2",
        "-b:a",       "128k",
        "-movflags",  "+faststart",
        "-loglevel",  "error",
        tmp,
    ]
    try:
        result = subprocess.run(cmd, timeout=300, capture_output=True)
        if result.returncode == 0 and os.path.getsize(tmp) > 10_000:
            print("  Instagram: re-encoded for compliance (main H.264 L4.0, CFR, faststart).")
            return tmp, True
        print(f"  Instagram: FFmpeg transcode failed (rc={result.returncode}), uploading original.")
        if os.path.exists(tmp):
            os.unlink(tmp)
    except Exception as e:
        print(f"  Instagram: FFmpeg transcode error ({e}), uploading original.")
        if os.path.exists(tmp):
            os.unlink(tmp)
    return src, False


def upload_to_instagram(video_path: str, caption: str) -> str | None:
    """
    Upload *video_path* as an Instagram Reel using the resumable upload API.

    Flow:
        0. Re-encode to Instagram-safe format (baseline H.264, CFR, faststart)
        1. Create upload session (POST /media with upload_type=resumable)
        2. Stream video bytes to the returned upload URI
        3. Poll container status until FINISHED
        4. Publish via /media_publish

    Returns the Reel URL on success.
    Returns None and prints a warning if credentials are not configured.
    Raises RuntimeError on API failure.
    """
    if not all([INSTAGRAM_USER_ID, INSTAGRAM_ACCESS_TOKEN]):
        print("  Instagram: credentials not set (INSTAGRAM_USER_ID / INSTAGRAM_ACCESS_TOKEN), skipping.")
        return None

    token = _refresh_token(INSTAGRAM_ACCESS_TOKEN)
    print("  Uploading to Instagram Reels...")

    # Builder now outputs Instagram-safe H.264 — skip re-encoding to avoid corruption.
    # If you need to force a re-encode, set env var FORCE_INSTAGRAM_REENCODE=1.
    if os.getenv("FORCE_INSTAGRAM_REENCODE"):
        upload_path, is_temp = _transcode_for_instagram(video_path)
    else:
        upload_path, is_temp = video_path, False

    file_size = os.path.getsize(upload_path)

    # ── Optional: validate container with ffprobe ─────────────────────
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    ffprobe = ffmpeg_bin.replace("ffmpeg", "ffprobe")
    try:
        probe = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries",
             "format=duration,bit_rate:stream=codec_name,width,height,pix_fmt,r_frame_rate,profile,level",
             "-of", "json", upload_path],
            capture_output=True, text=True, timeout=15,
        )
        if probe.returncode == 0:
            print(f"  [debug] ffprobe: {probe.stdout[:500]}")
    except Exception:
        pass

    # ── Step 1: Create upload session ─────────────────────────────────
    r = requests.post(
        f"{GRAPH_BASE}/{INSTAGRAM_USER_ID}/media",
        data={
            "media_type":    "REELS",
            "upload_type":   "resumable",
            "caption":       caption,
            "access_token":  token,
        },
        timeout=30,
    )
    if r.status_code != 200:
        if is_temp and os.path.exists(upload_path):
            os.unlink(upload_path)
        raise RuntimeError(f"Instagram: failed to create upload session: {r.text}")

    resp_data    = r.json()
    print(f"  [debug] create_session response: {resp_data}")
    container_id = resp_data.get("id")
    upload_uri   = resp_data.get("uri")

    if not container_id or not upload_uri:
        if is_temp and os.path.exists(upload_path):
            os.unlink(upload_path)
        raise RuntimeError(f"Instagram: unexpected response creating session: {resp_data}")

    # ── Step 2: Upload video bytes ───────────────────────────────────
    # Meta's resumable endpoint accepts single-shot uploads for files < 1 GB.
    with open(upload_path, "rb") as fh:
        video_bytes = fh.read()

    # Try OAuth first, then Bearer — Meta accepts either depending on token type.
    for auth_prefix in ("OAuth", "Bearer"):
        req = urllib.request.Request(upload_uri, method="POST", data=video_bytes)
        req.add_header("Authorization", f"{auth_prefix} {token}")
        req.add_header("offset", "0")
        req.add_header("file_size", str(file_size))
        req.add_header("Content-Type", "application/octet-stream")
        # urllib handles Content-Length automatically from data length
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                up_body = resp.read().decode("utf-8", errors="replace")
                up_code = resp.status
            print(f"  [debug] upload response ({auth_prefix}): {up_code} {up_body[:400]}")
            break  # success — leave the loop
        except urllib.error.HTTPError as e:
            up_body = e.read().decode("utf-8", errors="replace")
            up_code = e.code
            print(f"  [debug] upload response ({auth_prefix}): {up_code} {up_body[:400]}")
            if auth_prefix == "Bearer" or up_code not in (400, 401, 403):
                if is_temp and os.path.exists(upload_path):
                    os.unlink(upload_path)
                raise RuntimeError(
                    f"Instagram: video upload failed ({up_code}): {up_body}"
                )
            # If OAuth 400/401, try Bearer next iteration
            continue
        except Exception as e:
            if is_temp and os.path.exists(upload_path):
                os.unlink(upload_path)
            raise RuntimeError(f"Instagram: upload request error: {e}")

    if is_temp and os.path.exists(upload_path):
        os.unlink(upload_path)

    # ── Step 3: Poll until processing finishes (max 5 minutes) ────────
    print("  Instagram: processing", end="", flush=True)
    for _ in range(30):
        time.sleep(10)
        status_r = requests.get(
            f"{GRAPH_BASE}/{container_id}",
            params={"fields": "status_code,status", "access_token": token},
            timeout=30,
        )
        payload = status_r.json()
        code    = payload.get("status_code", "")
        if code == "FINISHED":
            print(" ready.")
            break
        if code == "ERROR":
            raise RuntimeError(f"Instagram: media processing error: {payload}")
        print(".", end="", flush=True)
    else:
        raise RuntimeError("Instagram: processing timed out after 5 minutes.")

    # ── Step 4: Publish ────────────────────────────────────────────────
    pub = requests.post(
        f"{GRAPH_BASE}/{INSTAGRAM_USER_ID}/media_publish",
        data={"creation_id": container_id, "access_token": token},
        timeout=30,
    )
    pub_data = pub.json()
    media_id = pub_data.get("id")
    if not media_id:
        raise RuntimeError(f"Instagram: publish failed: {pub_data}")

    url = f"https://www.instagram.com/p/{media_id}/"
    print(f"  Instagram [OK] -> {url}")
    return url
