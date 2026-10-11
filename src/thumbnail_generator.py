"""
Thumbnail Generator Module using Pillow.

Creates high-contrast, clean 1080x1920 (9:16) thumbnail images
from hero frames, bold hook typography, and category badges.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from config import VIDEO_HEIGHT, VIDEO_WIDTH


def _extract_video_frame(video_path: str, output_frame_path: str, timestamp_sec: float = 1.0) -> bool:
    """Extract a single frame from video at given timestamp using FFmpeg."""
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        f"{timestamp_sec:.2f}",
        "-i",
        video_path,
        "-vframes",
        "1",
        "-q:v",
        "2",
        output_frame_path,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return res.returncode == 0 and os.path.exists(output_frame_path)
    except Exception:
        return False


def generate_infotainment_thumbnail(
    title: str,
    category: str,
    output_path: str,
    hero_video_or_image: Optional[str] = None,
    width: int = VIDEO_WIDTH,
    height: int = VIDEO_HEIGHT,
) -> str:
    """
    Generate an eye-catching, factual infotainment video thumbnail.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    hero_frame = None

    # Try extracting hero frame from video or image
    if hero_video_or_image and os.path.exists(hero_video_or_image):
        if hero_video_or_image.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            try:
                hero_frame = Image.open(hero_video_or_image).convert("RGB")
            except Exception:
                pass
        else:
            temp_frame = output_path + ".temp_frame.jpg"
            if _extract_video_frame(hero_video_or_image, temp_frame):
                try:
                    hero_frame = Image.open(temp_frame).convert("RGB")
                except Exception:
                    pass
                finally:
                    if os.path.exists(temp_frame):
                        os.unlink(temp_frame)

    if hero_frame is None:
        # Create atmospheric dark blue / slate backdrop
        hero_frame = Image.new("RGB", (width, height), color=(15, 23, 42))

    # Resize/crop hero frame to exact width and height (cover strategy)
    w_orig, h_orig = hero_frame.size
    ratio = max(width / w_orig, height / h_orig)
    new_w = int(w_orig * ratio)
    new_h = int(h_orig * ratio)
    hero_frame = hero_frame.resize((new_w, new_h), Image.LANCZOS)
    x1 = (new_w - width) // 2
    y1 = (new_h - height) // 2
    canvas = hero_frame.crop((x1, y1, x1 + width, y1 + height))

    # Add dark vignette gradient overlay for text readability
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d_overlay = ImageDraw.Draw(overlay)
    for y in range(height):
        # Darken top and bottom
        alpha = int(180 * (1.0 - (y / height)) + 200 * (y / height))
        d_overlay.line([(0, y), (width, y)], fill=(10, 15, 30, min(alpha, 210)))

    canvas.paste(overlay, (0, 0), overlay)
    draw = ImageDraw.Draw(canvas)

    # Load fonts
    try:
        font_badge = ImageFont.truetype("arial.ttf", 46)
        font_title = ImageFont.truetype("arial.ttf", 78)
        font_sub = ImageFont.truetype("arial.ttf", 40)
    except Exception:
        font_badge = ImageFont.load_default()
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    # 1. Category Pill Badge
    badge_text = category.upper().replace("_", " ")
    badge_x, badge_y = 100, 320
    draw.rounded_rectangle(
        [(badge_x, badge_y), (badge_x + 380, badge_y + 80)],
        radius=20,
        fill=(14, 165, 233),  # Cyan
    )
    draw.text((badge_x + 30, badge_y + 15), badge_text, fill=(255, 255, 255), font=font_badge)

    # 2. Wrapped Hook Title in Bold White with Drop Shadow
    title_words = title.split()
    lines = []
    curr = []
    for w in title_words:
        if len(" ".join(curr + [w])) <= 16:
            curr.append(w)
        else:
            lines.append(" ".join(curr))
            curr = [w]
    if curr:
        lines.append(" ".join(curr))

    y_pos = badge_y + 160
    for line in lines[:5]:
        # Drop shadow
        draw.text((104, y_pos + 4), line, fill=(0, 0, 0), font=font_title)
        # Main text
        draw.text((100, y_pos), line, fill=(255, 255, 255), font=font_title)
        y_pos += 96

    # 3. Footer tag
    draw.text((100, height - 260), "VERIFIED FACT • INFOTAINMENT", fill=(148, 163, 184), font=font_sub)

    canvas.save(output_path, "JPEG", quality=92)
    print(f"  [Thumbnail] Generated thumbnail -> {output_path}")
    return output_path
