"""
Media Retrieval and Selection Module.

Implements multi-tiered visual asset retrieval:
  1. Pexels Video (Primary)
  2. Pixabay Video (Secondary Fallback)
  3. Pexels / Pixabay Image (Tertiary Fallback)
  4. Informative Synthetic Graphics Card (Quaternary Fallback)

Normalizes all media to 1080x1920 9:16 portrait MP4s using FFmpeg.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from PIL import Image, ImageDraw, ImageFont

from config import CACHE_DIR, PEXELS_API_KEY, PIXABAY_API_KEY, VIDEO_FPS, VIDEO_HEIGHT, VIDEO_WIDTH

PEXELS_VIDEOS_URL = "https://api.pexels.com/videos/search"
PEXELS_PHOTOS_URL = "https://api.pexels.com/v1/search"
PIXABAY_VIDEOS_URL = "https://pixabay.com/api/videos/"
PIXABAY_PHOTOS_URL = "https://pixabay.com/api/"

MEDIA_CACHE_DIR = os.path.join(CACHE_DIR, "media")


@dataclass
class RetrievedAsset:
    path: str
    provider: str
    asset_id: str
    media_type: str  # "video" or "image"
    source_url: str
    query: str
    width: int
    height: int
    duration: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _get_ffmpeg_bin() -> str:
    bin_path = shutil.which("ffmpeg")
    return bin_path if bin_path else "ffmpeg"


def _get_ffprobe_bin() -> str:
    bin_path = shutil.which("ffprobe")
    return bin_path if bin_path else "ffprobe"


def validate_media_file(file_path: str, is_video: bool = True) -> bool:
    """Validate media file existence, non-trivial size, and stream readability."""
    if not os.path.exists(file_path) or os.path.getsize(file_path) < 5000:
        return False

    ffprobe = _get_ffprobe_bin()
    stream_type = "v" if is_video else "v"
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        stream_type,
        "-show_entries",
        "stream=codec_name,width,height",
        "-of",
        "json",
        file_path,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if res.returncode == 0:
            data = json.loads(res.stdout or "{}")
            streams = data.get("streams", [])
            return len(streams) > 0 and streams[0].get("width", 0) > 0
    except Exception:
        pass
    return False


def _download_file(url: str, dest_path: str, headers: Optional[Dict[str, str]] = None) -> bool:
    """Stream download remote media file."""
    try:
        r = requests.get(url, headers=headers or {}, stream=True, timeout=60)
        if r.status_code != 200:
            return False
        os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
        return os.path.getsize(dest_path) > 5000
    except Exception:
        return False


def transcode_to_portrait_video(
    src_path: str,
    dest_path: str,
    target_duration: float,
    is_image: bool = False,
) -> bool:
    """
    Scale, crop, and conform input video or image to 1080x1920 portrait MP4.
    If input is an image, generates a video clip of the requested duration.
    """
    ffmpeg = _get_ffmpeg_bin()
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)

    # Scale to cover 1080x1920 then center crop
    vf_filter = (
        f"scale=w={VIDEO_WIDTH}:h={VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},setsar=1"
    )

    if is_image:
        cmd = [
            ffmpeg,
            "-y",
            "-loop",
            "1",
            "-i",
            src_path,
            "-t",
            f"{target_duration:.2f}",
            "-vf",
            vf_filter,
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(VIDEO_FPS),
            "-loglevel",
            "error",
            dest_path,
        ]
    else:
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            src_path,
            "-t",
            f"{target_duration:.2f}",
            "-vf",
            vf_filter,
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(VIDEO_FPS),
            "-an",
            "-loglevel",
            "error",
            dest_path,
        ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if res.returncode == 0 and validate_media_file(dest_path, is_video=True):
            return True
    except Exception:
        pass
    return False


def create_infographic_card(
    title: str,
    subtitle: str,
    output_image_path: str,
    width: int = VIDEO_WIDTH,
    height: int = VIDEO_HEIGHT,
) -> str:
    """Generate an informative, elegant synthetic graphic card when stock media is unavailable."""
    os.makedirs(os.path.dirname(os.path.abspath(output_image_path)), exist_ok=True)
    img = Image.new("RGB", (width, height), color=(15, 23, 42))  # Slate dark
    draw = ImageDraw.Draw(img)

    # Gradient background accents
    for y in range(0, height, 4):
        ratio = y / height
        r = int(15 + ratio * 20)
        g = int(23 + ratio * 35)
        b = int(42 + ratio * 70)
        draw.line([(0, y), (width, y)], fill=(r, g, b), width=4)

    # Accent decorative box
    draw.rounded_rectangle(
        [(80, 200), (width - 80, height - 200)],
        radius=30,
        outline=(56, 189, 248),
        width=4,
    )

    # Load default or platform font
    try:
        font_large = ImageFont.truetype("arial.ttf", 64)
        font_small = ImageFont.truetype("arial.ttf", 42)
    except Exception:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Title & Subtitle text
    draw.text((120, 280), "INFOTAINMENT FACT", fill=(56, 189, 248), font=font_small)

    # Wrap title
    words = title.split()
    lines = []
    curr = []
    for w in words:
        if len(" ".join(curr + [w])) <= 22:
            curr.append(w)
        else:
            lines.append(" ".join(curr))
            curr = [w]
    if curr:
        lines.append(" ".join(curr))

    y_text = 400
    for line in lines[:4]:
        draw.text((120, y_text), line, fill=(248, 250, 252), font=font_large)
        y_text += 80

    # Subtitle text
    sub_words = subtitle.split()
    sub_lines = []
    curr_sub = []
    for w in sub_words:
        if len(" ".join(curr_sub + [w])) <= 28:
            curr_sub.append(w)
        else:
            sub_lines.append(" ".join(curr_sub))
            curr_sub = [w]
    if curr_sub:
        sub_lines.append(" ".join(curr_sub))

    y_sub = y_text + 60
    for s_line in sub_lines[:6]:
        draw.text((120, y_sub), s_line, fill=(203, 213, 225), font=font_small)
        y_sub += 60

    img.save(output_image_path, "PNG")
    return output_image_path


# ---------------------------------------------------------------------------
# Pexels Video & Image Retrievers
# ---------------------------------------------------------------------------

def _fetch_pexels_video(
    query: str,
    api_key: str,
    dest_path: str,
    used_ids: Set[str],
) -> Optional[RetrievedAsset]:
    if not api_key:
        return None
    headers = {"Authorization": api_key}
    for orientation in ("portrait", "landscape"):
        try:
            params = {"query": query, "per_page": 15, "orientation": orientation}
            r = requests.get(PEXELS_VIDEOS_URL, headers=headers, params=params, timeout=20)
            if r.status_code != 200:
                continue
            videos = r.json().get("videos", [])
            for v in videos:
                vid_id = str(v.get("id"))
                if vid_id in used_ids:
                    continue
                files = v.get("video_files", [])
                # Prefer HD/UHD files >= 720p
                valid_files = [f for f in files if (f.get("width", 0) >= 720 or f.get("height", 0) >= 720)]
                if not valid_files:
                    valid_files = files
                if not valid_files:
                    continue
                valid_files.sort(key=lambda x: x.get("width", 0) * x.get("height", 0), reverse=True)
                download_url = valid_files[0].get("link")
                if download_url and _download_file(download_url, dest_path):
                    if validate_media_file(dest_path, is_video=True):
                        return RetrievedAsset(
                            path=dest_path,
                            provider="pexels",
                            asset_id=vid_id,
                            media_type="video",
                            source_url=v.get("url", ""),
                            query=query,
                            width=valid_files[0].get("width", 1080),
                            height=valid_files[0].get("height", 1920),
                            duration=float(v.get("duration", 10)),
                        )
        except Exception:
            pass
    return None


def _fetch_pexels_photo(
    query: str,
    api_key: str,
    dest_path: str,
    used_ids: Set[str],
) -> Optional[RetrievedAsset]:
    if not api_key:
        return None
    headers = {"Authorization": api_key}
    for orientation in ("portrait", "landscape"):
        try:
            params = {"query": query, "per_page": 10, "orientation": orientation}
            r = requests.get(PEXELS_PHOTOS_URL, headers=headers, params=params, timeout=20)
            if r.status_code != 200:
                continue
            photos = r.json().get("photos", [])
            for p in photos:
                photo_id = str(p.get("id"))
                if photo_id in used_ids:
                    continue
                src_dict = p.get("src", {})
                img_url = src_dict.get("large2x") or src_dict.get("large") or src_dict.get("original")
                if img_url and _download_file(img_url, dest_path):
                    if validate_media_file(dest_path, is_video=False):
                        return RetrievedAsset(
                            path=dest_path,
                            provider="pexels",
                            asset_id=photo_id,
                            media_type="image",
                            source_url=p.get("url", ""),
                            query=query,
                            width=p.get("width", 1080),
                            height=p.get("height", 1920),
                            duration=0.0,
                        )
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Pixabay Video & Image Retrievers (Secondary Fallback)
# ---------------------------------------------------------------------------

def _fetch_pixabay_video(
    query: str,
    api_key: str,
    dest_path: str,
    used_ids: Set[str],
) -> Optional[RetrievedAsset]:
    if not api_key:
        return None
    try:
        params = {
            "key": api_key,
            "q": query[:100],
            "per_page": 10,
            "safesearch": "true",
        }
        r = requests.get(PIXABAY_VIDEOS_URL, params=params, timeout=20)
        if r.status_code != 200:
            return None
        hits = r.json().get("hits", [])
        for hit in hits:
            vid_id = str(hit.get("id"))
            if vid_id in used_ids:
                continue
            v_sizes = hit.get("videos", {})
            # Prefer large -> medium -> small
            choice = v_sizes.get("large") or v_sizes.get("medium") or v_sizes.get("small")
            if not choice or not choice.get("url"):
                continue
            if _download_file(choice["url"], dest_path):
                if validate_media_file(dest_path, is_video=True):
                    return RetrievedAsset(
                        path=dest_path,
                        provider="pixabay",
                        asset_id=vid_id,
                        media_type="video",
                        source_url=hit.get("pageURL", ""),
                        query=query,
                        width=choice.get("width", 1080),
                        height=choice.get("height", 1920),
                        duration=float(hit.get("duration", 10)),
                    )
    except Exception:
        pass
    return None


def _fetch_pixabay_photo(
    query: str,
    api_key: str,
    dest_path: str,
    used_ids: Set[str],
) -> Optional[RetrievedAsset]:
    if not api_key:
        return None
    try:
        params = {
            "key": api_key,
            "q": query[:100],
            "image_type": "photo",
            "per_page": 10,
            "safesearch": "true",
        }
        r = requests.get(PIXABAY_PHOTOS_URL, params=params, timeout=20)
        if r.status_code != 200:
            return None
        hits = r.json().get("hits", [])
        for hit in hits:
            photo_id = str(hit.get("id"))
            if photo_id in used_ids:
                continue
            img_url = hit.get("largeImageURL") or hit.get("webformatURL")
            if img_url and _download_file(img_url, dest_path):
                if validate_media_file(dest_path, is_video=False):
                    return RetrievedAsset(
                        path=dest_path,
                        provider="pixabay",
                        asset_id=photo_id,
                        media_type="image",
                        source_url=hit.get("pageURL", ""),
                        query=query,
                        width=hit.get("imageWidth", 1080),
                        height=hit.get("imageHeight", 1920),
                        duration=0.0,
                    )
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Public Scene Media Orchestrator
# ---------------------------------------------------------------------------

def retrieve_scene_media(
    scene_number: int,
    video_queries: List[str],
    image_queries: List[str],
    main_subject: str,
    target_duration: float,
    output_video_path: str,
    used_ids: Optional[Set[str]] = None,
    pexels_key: Optional[str] = None,
    pixabay_key: Optional[str] = None,
) -> RetrievedAsset:
    """
    Retrieve and transcode scene visual asset according to strict fallback hierarchy:
      1. Pexels video
      2. Pixabay video
      3. Pexels image
      4. Pixabay image
      5. Informative synthetic card
    """
    used = used_ids if used_ids is not None else set()
    p_key = pexels_key or PEXELS_API_KEY
    pb_key = pixabay_key or PIXABAY_API_KEY

    os.makedirs(os.path.dirname(os.path.abspath(output_video_path)), exist_ok=True)
    raw_dir = os.path.join(os.path.dirname(output_video_path), "raw")
    os.makedirs(raw_dir, exist_ok=True)

    # 1. Pexels Video
    for q in video_queries:
        print(f"    [Media] Searching Pexels Video for: '{q}'...")
        raw_dest = os.path.join(raw_dir, f"scene_{scene_number:02d}_pexels_raw.mp4")
        asset = _fetch_pexels_video(q, p_key, raw_dest, used)
        if asset:
            print(f"      Found Pexels Video #{asset.asset_id} ({asset.width}x{asset.height})")
            if transcode_to_portrait_video(asset.path, output_video_path, target_duration, is_image=False):
                asset.path = output_video_path
                return asset

    # 2. Pixabay Video
    if pb_key:
        for q in video_queries:
            print(f"    [Media] Searching Pixabay Video fallback for: '{q}'...")
            raw_dest = os.path.join(raw_dir, f"scene_{scene_number:02d}_pixabay_raw.mp4")
            asset = _fetch_pixabay_video(q, pb_key, raw_dest, used)
            if asset:
                print(f"      Found Pixabay Video #{asset.asset_id} ({asset.width}x{asset.height})")
                if transcode_to_portrait_video(asset.path, output_video_path, target_duration, is_image=False):
                    asset.path = output_video_path
                    return asset

    # 3. Pexels Image
    for q in image_queries + video_queries:
        print(f"    [Media] Searching Pexels Image fallback for: '{q}'...")
        raw_dest = os.path.join(raw_dir, f"scene_{scene_number:02d}_pexels_raw.jpg")
        asset = _fetch_pexels_photo(q, p_key, raw_dest, used)
        if asset:
            print(f"      Found Pexels Photo #{asset.asset_id}")
            if transcode_to_portrait_video(asset.path, output_video_path, target_duration, is_image=True):
                asset.path = output_video_path
                return asset

    # 4. Pixabay Image
    if pb_key:
        for q in image_queries + video_queries:
            print(f"    [Media] Searching Pixabay Image fallback for: '{q}'...")
            raw_dest = os.path.join(raw_dir, f"scene_{scene_number:02d}_pixabay_raw.jpg")
            asset = _fetch_pixabay_photo(q, pb_key, raw_dest, used)
            if asset:
                print(f"      Found Pixabay Photo #{asset.asset_id}")
                if transcode_to_portrait_video(asset.path, output_video_path, target_duration, is_image=True):
                    asset.path = output_video_path
                    return asset

    # 5. Synthetic Graphics Card Fallback
    print(f"    [Media] Generating high-resolution infographic card for: '{main_subject}'...")
    card_img_path = os.path.join(raw_dir, f"scene_{scene_number:02d}_card.png")
    create_infographic_card(
        title=main_subject.upper(),
        subtitle=f"Scientific and factual overview of {main_subject}.",
        output_image_path=card_img_path,
    )
    if transcode_to_portrait_video(card_img_path, output_video_path, target_duration, is_image=True):
        return RetrievedAsset(
            path=output_video_path,
            provider="synthetic",
            asset_id=f"card_{scene_number}_{int(time.time())}",
            media_type="image",
            source_url="local://infographic_generator",
            query=main_subject,
            width=VIDEO_WIDTH,
            height=VIDEO_HEIGHT,
            duration=target_duration,
        )

    raise RuntimeError(f"Failed to retrieve or generate visual asset for scene {scene_number}.")
