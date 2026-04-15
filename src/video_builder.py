import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip,
    VideoFileClip,
    ImageClip,
    concatenate_videoclips,
    CompositeVideoClip,
)

VIDEO_W = 1080
VIDEO_H = 1920
FPS     = 30


# =====================================================================
# Quote text overlay
# =====================================================================

def _make_quote_overlay(width: int, height: int, quote: str, author: str = ""):
    """
    Render a quote as a semi-transparent RGBA numpy array (H, W, 4).
    Pre-computed once per scene and composited onto every frame.
    Returns None on failure.
    """
    if not quote:
        return None

    font_candidates = [
        # Noto fonts (installed by GitHub Actions / Ubuntu)
        ("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",         56, 36),
        ("/usr/share/fonts/truetype/noto/NotoSansTelugu-Regular.ttf",   56, 36),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",             56, 36),
        # Windows fonts
        ("C:/Windows/Fonts/NirmalaUI.ttf",  56, 36),
        ("C:/Windows/Fonts/Georgia.ttf",    56, 36),
        ("C:/Windows/Fonts/Calibri.ttf",    56, 36),
        ("C:/Windows/Fonts/Arial.ttf",      56, 36),
    ]
    font = q_font = None
    for fp, fs, afs in font_candidates:
        try:
            font   = ImageFont.truetype(fp, fs)
            q_font = ImageFont.truetype(fp, afs)
            break
        except Exception:
            continue
    if font is None:
        font = q_font = ImageFont.load_default()

    _probe = Image.new("RGBA", (1, 1))
    _draw  = ImageDraw.Draw(_probe)
    max_w  = int(width * 0.82)

    def _wrap(text, f):
        words, lines, cur = text.split(), [], []
        for w in words:
            test = " ".join(cur + [w])
            try:
                tw = _draw.textbbox((0, 0), test, font=f)[2]
            except Exception:
                tw = len(test) * 18
            if tw <= max_w or not cur:
                cur.append(w)
            else:
                lines.append(" ".join(cur))
                cur = [w]
        if cur:
            lines.append(" ".join(cur))
        return lines

    quote_lines = _wrap(quote, font)
    author_line = f"\u2014 {author}" if author else None

    line_h   = 72
    author_h = 48
    pad_v    = 40
    total_h  = len(quote_lines) * line_h + (author_h if author_line else 0) + pad_v * 2

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)

    strip_y = height - total_h - 44
    draw.rectangle([0, strip_y, width, height], fill=(0, 0, 0, 170))
    draw.line([0, strip_y, width, strip_y], fill=(255, 220, 100, 140), width=2)

    y = strip_y + pad_v
    for line in quote_lines:
        try:
            tw = draw.textbbox((0, 0), line, font=font)[2]
        except Exception:
            tw = len(line) * 18
        x = max(80, (width - tw) // 2)
        draw.text((x + 2, y + 2), line, font=font,  fill=(0, 0, 0, 180))
        draw.text((x,     y),     line, font=font,  fill=(255, 248, 210, 245))
        y += line_h

    if author_line:
        try:
            tw = draw.textbbox((0, 0), author_line, font=q_font)[2]
        except Exception:
            tw = len(author_line) * 14
        x = max(80, (width - tw) // 2)
        draw.text((x + 1, y + 1), author_line, font=q_font, fill=(0, 0, 0, 140))
        draw.text((x,     y),     author_line, font=q_font, fill=(200, 200, 200, 220))

    return np.array(overlay)


# =====================================================================
# Crop / fit a raw clip to 1080×1920 portrait
# =====================================================================

def _fit_to_portrait(clip):
    """Scale+crop source footage to VIDEO_W × VIDEO_H (cover strategy).
    If the clip is already the right size (pre-transcoded), returns it as-is."""
    src_w, src_h = clip.size

    # Fast path: clip already matches target (pre-transcoded by video_fetcher)
    if src_w == VIDEO_W and src_h == VIDEO_H:
        return clip

    target_ratio = VIDEO_W / VIDEO_H
    src_ratio    = src_w  / src_h

    if src_ratio > target_ratio:
        new_h = VIDEO_H
        new_w = int(src_w * VIDEO_H / src_h)
    else:
        new_w = VIDEO_W
        new_h = int(src_h * VIDEO_W / src_w)

    x1 = (new_w - VIDEO_W) // 2
    y1 = (new_h - VIDEO_H) // 2

    def _process(frame):
        img = Image.fromarray(frame).resize((new_w, new_h), Image.LANCZOS)
        arr = np.array(img)
        return arr[y1:y1 + VIDEO_H, x1:x1 + VIDEO_W]

    return clip.fl_image(_process)


# =====================================================================
# Colour grade — warm cinematic look
# =====================================================================

def _colour_grade(frame: np.ndarray) -> np.ndarray:
    """Warm tint + gentle vignette for a cinematic moody feel."""
    f = frame.astype(np.float32)

    # Warm tint: boost reds, reduce blues slightly
    f[:, :, 0] = np.clip(f[:, :, 0] * 1.06, 0, 255)
    f[:, :, 2] = np.clip(f[:, :, 2] * 0.92, 0, 255)

    # Vignette
    h, w = f.shape[:2]
    ys = np.linspace(-1, 1, h, dtype=np.float32).reshape(-1, 1)
    xs = np.linspace(-1, 1, w, dtype=np.float32).reshape(1, -1)
    vignette = np.clip(1.0 - 0.35 * (ys**2 + xs**2), 0.55, 1.0)[:, :, np.newaxis]
    f = f * vignette

    return np.clip(f, 0, 255).astype(np.uint8)


# =====================================================================
# Build single scene from real footage
# =====================================================================

def _build_scene_clip(video_path: str, duration: float, scene_idx: int,
                      overlay_rgba=None):
    """
    Load a Pexels video, trim to `duration`, crop to portrait,
    apply colour grade and bake in quote overlay.
    """
    raw = VideoFileClip(video_path, audio=False)

    # Loop if clip is shorter than needed
    if raw.duration < duration:
        loops = math.ceil(duration / raw.duration)
        raw   = concatenate_videoclips([raw] * loops)

    # Varied but deterministic start offset
    max_start = max(0.0, raw.duration - duration)
    start     = (scene_idx * 3.7) % (max_start + 0.001)
    start     = min(start, max_start)
    clip      = raw.subclip(start, start + duration)

    # Portrait crop
    clip = _fit_to_portrait(clip)

    # Colour grade
    clip = clip.fl_image(_colour_grade)

    # Quote overlay
    if overlay_rgba is not None:
        overlay_img = ImageClip(overlay_rgba, ismask=False).set_duration(duration)
        clip = CompositeVideoClip([clip, overlay_img])

    return clip.set_fps(FPS)


# =====================================================================
# Public API
# =====================================================================

def build_video(
    scenes: list,
    video_paths: list = None,
    output_path: str = "",
    music_path: str = None,
    quote_data: list = None,
    scene_duration: float = 12.0,
    # Legacy compat
    image_paths: list = None,
):
    """
    Build the final peaceful quotes video from real Pexels footage.

    Args:
        scenes:         List of scene dicts from quote_generator.
        video_paths:    Downloaded MP4 per scene (replaces image_paths).
        output_path:    Where to write the final MP4.
        music_path:     Path to ambient WAV file.
        quote_data:     Same as scenes — used to render text overlay.
        scene_duration: Seconds per scene (default 12s).
    """
    if video_paths is None:
        video_paths = image_paths or []

    print(f"        Compositing {len(scenes)} scenes at {scene_duration}s each...")
    scene_clips = []

    for i, scene in enumerate(scenes):
        print(f"        Scene {i + 1}/{len(scenes)}")
        overlay = None
        if quote_data and i < len(quote_data):
            q = quote_data[i]
            overlay = _make_quote_overlay(VIDEO_W, VIDEO_H,
                                          q.get("quote", ""),
                                          q.get("author", ""))
        clip = _build_scene_clip(video_paths[i], scene_duration, i, overlay)
        scene_clips.append(clip)

    # Crossfade transitions
    CROSSFADE = 0.8
    if len(scene_clips) > 1:
        final = concatenate_videoclips(scene_clips, method="compose", padding=-CROSSFADE)
    else:
        final = scene_clips[0]

    # Attach ambient music
    if music_path and os.path.exists(music_path):
        music = AudioFileClip(music_path).volumex(0.80).set_duration(final.duration)
        final = final.set_audio(music)

    final.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
        logger="bar",
    )

    for c in scene_clips:
        try:
            c.close()
        except Exception:
            pass
    try:
        final.close()
    except Exception:
        pass
