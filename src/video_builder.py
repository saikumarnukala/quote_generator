import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip,
    AudioClip,
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

    # Place quote at the TOP so it is not covered by YouTube channel name / controls
    strip_top    = 0
    strip_bottom = total_h + pad_v * 2
    draw.rectangle([0, strip_top, width, strip_bottom], fill=(0, 0, 0, 210))
    # Decorative gold line at the bottom edge of the strip
    draw.line([0, strip_bottom, width, strip_bottom], fill=(255, 220, 100, 140), width=2)

    y = strip_top + pad_v
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
    """Fast cinematic colour grade — warm highlights, teal shadows, film-like contrast.
    Optimised for speed: vectorised numpy ops, no per-pixel Python loops.
    """
    f = frame.astype(np.float32)

    # Lift contrast slightly (S-curve approximation)
    f = np.clip((f - 128) * 1.08 + 128, 0, 255)

    # Warm highlights: boost reds/yellows in bright areas
    bright_mask = (f.mean(axis=2, keepdims=True) / 255.0)
    f[:, :, 0] = np.clip(f[:, :, 0] + 6 * bright_mask[:, :, 0], 0, 255)
    f[:, :, 1] = np.clip(f[:, :, 1] + 2 * bright_mask[:, :, 0], 0, 255)

    # Teal shadows: push blue/cyan into dark areas
    shadow_mask = 1.0 - bright_mask
    f[:, :, 2] = np.clip(f[:, :, 2] + 8 * shadow_mask[:, :, 0], 0, 255)
    f[:, :, 1] = np.clip(f[:, :, 1] + 3 * shadow_mask[:, :, 0], 0, 255)

    # Vignette — precompute once per shape to avoid reallocation every frame
    h, w = f.shape[:2]
    key = (h, w)
    if key not in _vignette_cache:
        ys = np.linspace(-1, 1, h, dtype=np.float32).reshape(-1, 1)
        xs = np.linspace(-1, 1, w, dtype=np.float32).reshape(1, -1)
        _vignette_cache[key] = np.clip(1.0 - 0.40 * (ys**2 + xs**2), 0.50, 1.0)[:, :, np.newaxis]
    f = f * _vignette_cache[key]

    return np.clip(f, 0, 255).astype(np.uint8)


_vignette_cache = {}


# =====================================================================
# Build single scene from real footage
# =====================================================================

def _build_scene_clip(video_path: str, duration: float, scene_idx: int,
                      overlay_rgba=None):
    """
    Load a video or image, trim/extend to `duration`, crop to portrait,
    apply colour grade and bake in quote overlay.
    """
    if video_path.lower().endswith((".png", ".jpg", ".jpeg")):
        raw = ImageClip(video_path).set_duration(duration)
    else:
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

    # Colour grade (skipped in CI if SKIP_COLOUR_GRADE=1 to save ~70% render time)
    if not os.environ.get("SKIP_COLOUR_GRADE"):
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
    music_path:     str = None,
    audio_paths:    list = None,
    quote_data:     list = None,
    scene_duration: float = 12.0,
    # Legacy compat
    image_paths: list = None,
):
    """
    Build the final video from scenes.

    Args:
        scenes:         List of scene dicts.
        video_paths:    Downloaded/generated MP4 per scene.
        output_path:    Where to write the final MP4.
        music_path:     Path to background music (optional).
        audio_paths:    List of narration audio files per scene (optional).
        quote_data:     Data for text overlay (optional).
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
                                          q.get("quote", q.get("narration", "")),
                                          q.get("author", ""))
        clip = _build_scene_clip(video_paths[i], scene_duration, i, overlay)
        
        # Attach per-scene audio if provided
        if audio_paths and i < len(audio_paths) and audio_paths[i]:
            if os.path.exists(audio_paths[i]):
                scene_audio = AudioFileClip(audio_paths[i])
                # If audio is longer than scene, we might need to adjust or let it be
                clip = clip.set_audio(scene_audio)
        
        scene_clips.append(clip)

    # Crossfade transitions — longer for smoother cinematic flow
    CROSSFADE = 1.2
    if len(scene_clips) > 1:
        final = concatenate_videoclips(scene_clips, method="compose", padding=-CROSSFADE)
    else:
        final = scene_clips[0]

    # Attach ambient music (or silent placeholder — Instagram requires AAC audio)
    if music_path and os.path.exists(music_path):
        music = AudioFileClip(music_path).volumex(0.80).set_duration(final.duration)
        final = final.set_audio(music)
    else:
        # Create a silent stereo AAC placeholder so the output always has an audio stream.
        # Instagram's Reels API rejects video-only MP4s with ProcessingFailedError.
        silent = AudioClip(
            lambda t: np.zeros((2,)),
            duration=final.duration,
            fps=44100,
        )
        final = final.set_audio(silent)

    final.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="fast",
        bitrate="5000k",
        threads=4,
        logger="bar",
        # Instagram / YouTube Shorts requirements:
        #   - yuv420p pixel format (Instagram rejects yuva420p / other formats)
        #   - H.264 Main profile level 4.0 (standard for 1080p; baseline 3.1 maxes at 720p)
        #   - No B-frames (Meta's Reels processor rejects them)
        #   - Stereo AAC audio at 44100 Hz
        #   - movflags faststart: moov atom at file start (required by Meta's transcoder)
        #   - vsync cfr: constant frame rate (VFR causes ProcessingFailedError on Instagram)
        ffmpeg_params=[
            "-pix_fmt",     "yuv420p",
            "-profile:v",   "main",
            "-level:v",     "4.0",
            "-bf",          "0",
            "-r",           str(FPS),
            "-vsync",       "cfr",
            "-ar",          "44100",
            "-ac",          "2",
            "-movflags",    "+faststart",
        ],
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
