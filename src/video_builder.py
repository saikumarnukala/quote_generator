import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip,
    ImageSequenceClip,
    concatenate_videoclips,
)

VIDEO_W = 1280
VIDEO_H = 720
FPS     = 24


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
        ("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",         36, 24),
        ("/usr/share/fonts/truetype/noto/NotoSansTelugu-Regular.ttf",   36, 24),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",             36, 24),
        # Windows fonts
        ("C:/Windows/Fonts/NirmalaUI.ttf",  36, 24),
        ("C:/Windows/Fonts/Georgia.ttf",    36, 24),
        ("C:/Windows/Fonts/Calibri.ttf",    36, 24),
        ("C:/Windows/Fonts/Arial.ttf",      36, 24),
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

    line_h   = 48
    author_h = 32
    pad_v    = 24
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
        x = max(60, (width - tw) // 2)
        draw.text((x + 2, y + 2), line, font=font,  fill=(0, 0, 0, 180))
        draw.text((x,     y),     line, font=font,  fill=(255, 248, 210, 245))
        y += line_h

    if author_line:
        try:
            tw = draw.textbbox((0, 0), author_line, font=q_font)[2]
        except Exception:
            tw = len(author_line) * 14
        x = max(60, (width - tw) // 2)
        draw.text((x + 1, y + 1), author_line, font=q_font, fill=(0, 0, 0, 140))
        draw.text((x,     y),     author_line, font=q_font, fill=(200, 200, 200, 220))

    return np.array(overlay)


# =====================================================================
# Floating particle system
# =====================================================================

def _create_particles(count=45, seed=42):
    rng = np.random.RandomState(seed)
    return {
        "x":          rng.uniform(0, VIDEO_W, count),
        "y":          rng.uniform(0, VIDEO_H, count),
        "size":       rng.uniform(2, 5, count),
        "brightness": rng.uniform(190, 255, count),
        "speed_x":    rng.uniform(-0.35, 0.35, count),
        "speed_y":    rng.uniform(-1.0, -0.25, count),
        "phase":      rng.uniform(0, 2 * math.pi, count),
    }


def _overlay_particles(frame, particles, fi):
    result = frame.astype(np.float32)
    t = fi / FPS
    n = len(particles["x"])
    for i in range(n):
        px = (particles["x"][i] + particles["speed_x"][i] * fi
              + 8 * math.sin(particles["phase"][i] + t * 0.7)) % VIDEO_W
        py = (particles["y"][i] + particles["speed_y"][i] * fi) % VIDEO_H
        alpha = 0.22 + 0.18 * math.sin(particles["phase"][i] + t * 1.8)
        if alpha < 0.05:
            continue
        s  = int(particles["size"][i])
        y0 = max(0, int(py) - s);  y1 = min(VIDEO_H, int(py) + s + 1)
        x0 = max(0, int(px) - s);  x1 = min(VIDEO_W, int(px) + s + 1)
        if y0 >= y1 or x0 >= x1:
            continue
        ys   = np.arange(y0, y1, dtype=np.float32).reshape(-1, 1)
        xs   = np.arange(x0, x1, dtype=np.float32).reshape(1, -1)
        dist = np.sqrt((ys - py) ** 2 + (xs - px) ** 2)
        mask = np.clip(1.0 - dist / (s + 0.5), 0, 1) * alpha
        b    = particles["brightness"][i]
        glow = np.array([b, b, b * 0.93], dtype=np.float32)
        reg  = result[y0:y1, x0:x1]
        result[y0:y1, x0:x1] = reg + mask[:, :, np.newaxis] * (glow - reg)
    return np.clip(result, 0, 255).astype(np.uint8)


_DIRECTIONS = [
    (1, 0), (-1, 0), (0, 1), (1, -1), (-1, 1), (1, 1), (-1, -1),
]


# =====================================================================
# Animated scene builder
# =====================================================================

def _create_animated_scene(image_path: str, duration: float, scene_idx: int,
                            overlay_rgba=None) -> ImageSequenceClip:
    """
    Create a smooth parallax + breathing-zoom animated clip.
    Optionally composite a pre-rendered quote overlay onto every frame.
    """
    SCALE    = 1.40
    CANVAS_W = int(VIDEO_W * SCALE)
    CANVAS_H = int(VIDEO_H * SCALE)

    img    = Image.open(image_path).convert("RGB").resize((CANVAS_W, CANVAS_H), Image.LANCZOS)
    canvas = np.array(img)

    n_frames = max(2, int(duration * FPS))
    dx, dy   = _DIRECTIONS[scene_idx % len(_DIRECTIONS)]
    max_sx   = int(VIDEO_W * 0.14)
    max_sy   = int(VIDEO_H * 0.09)

    depth     = np.linspace(0.08, 1.0, VIDEO_H, dtype=np.float64).reshape(-1, 1)
    base_cols = np.arange(VIDEO_W, dtype=np.intp).reshape(1, -1)
    center_x  = (CANVAS_W - VIDEO_W) // 2
    center_y  = (CANVAS_H - VIDEO_H) // 2
    base_rows = (np.arange(VIDEO_H, dtype=np.intp) + center_y).reshape(-1, 1)
    particles = _create_particles(45, seed=scene_idx * 7 + 13)

    # Pre-compute overlay alpha for blending (if quote overlay provided)
    ov_alpha = ov_rgb = None
    if overlay_rgba is not None:
        ov_alpha = overlay_rgba[:, :, 3:4].astype(np.float32) / 255.0
        ov_rgb   = overlay_rgba[:, :, :3].astype(np.float32)

    frames = []
    for fi in range(n_frames):
        t    = fi / max(n_frames - 1, 1)
        ease = t * t * (3 - 2 * t)

        shift_x = (depth * max_sx * ease * dx).astype(np.intp)
        shift_y = (depth * max_sy * ease * dy).astype(np.intp)

        breath     = 1.0 + 0.018 * math.sin(2 * math.pi * fi / (FPS * 2.5))
        zoom_off_x = int((VIDEO_W * (breath - 1)) / 2)
        zoom_off_y = int((VIDEO_H * (breath - 1)) / 2)

        sample_x = base_cols + center_x + shift_x - zoom_off_x
        sample_y = base_rows + shift_y - zoom_off_y
        np.clip(sample_x, 0, CANVAS_W - 1, out=sample_x)
        np.clip(sample_y, 0, CANVAS_H - 1, out=sample_y)

        frame = canvas[sample_y, sample_x]
        frame = _overlay_particles(frame, particles, fi)

        if ov_alpha is not None:
            frame = np.clip(
                frame.astype(np.float32) * (1 - ov_alpha) + ov_rgb * ov_alpha, 0, 255
            ).astype(np.uint8)

        frames.append(frame)

    return ImageSequenceClip(frames, fps=FPS)


# =====================================================================
# Public API
# =====================================================================

def build_video(
    scenes: list,
    image_paths: list,
    output_path: str,
    music_path: str = None,
    quote_data: list = None,
    scene_duration: float = 12.0,
):
    """
    Build the final peaceful quotes video.

    Args:
        scenes:         List of scene dicts from quote_generator.
        image_paths:    Landscape PNG per scene.
        output_path:    Where to write the final MP4.
        music_path:     Path to ambient WAV/MP3 file.
        quote_data:     Same as scenes — used to render text overlay.
        scene_duration: Seconds per scene (default 12s).
    """
    print(f"        Rendering {len(scenes)} scenes at {scene_duration}s each...")
    scene_clips = []

    for i, scene in enumerate(scenes):
        print(f"        Scene {i + 1}/{len(scenes)}")
        overlay = None
        if quote_data and i < len(quote_data):
            q = quote_data[i]
            overlay = _make_quote_overlay(VIDEO_W, VIDEO_H,
                                          q.get("quote", ""),
                                          q.get("author", ""))
        clip = _create_animated_scene(image_paths[i], scene_duration, i, overlay)
        scene_clips.append(clip)

    # Crossfade transitions between scenes
    CROSSFADE = 0.8
    if len(scene_clips) > 1:
        final = concatenate_videoclips(scene_clips, method="compose", padding=-CROSSFADE)
    else:
        final = scene_clips[0]

    # Attach ambient music
    if music_path and os.path.exists(music_path):
        from moviepy.editor import AudioFileClip
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
        c.close()
    final.close()
