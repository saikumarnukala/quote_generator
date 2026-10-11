"""
Subtitle Generator Module.

Generates synchronized SRT and ASS subtitle files from scene narrations
and actual measured audio durations. Formats subtitles within safe display margins
for 9:16 vertical video (YouTube Shorts).
"""

from __future__ import annotations

import os
import re
from typing import List, Tuple

# Safe margin for YouTube Shorts / Reels UI (bottom margin in pixels on 1080x1920)
SAFE_MARGIN_BOTTOM = 320
SAFE_MARGIN_SIDES = 80


def _format_srt_timestamp(seconds: float) -> str:
    """Format float seconds to SRT timestamp: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds % 1) * 1000))
    if millis >= 1000:
        secs += 1
        millis = 0
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _format_ass_timestamp(seconds: float) -> str:
    """Format float seconds to ASS timestamp: H:MM:SS.cc (centiseconds)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds % 1) * 100))
    if centis >= 100:
        secs += 1
        centis = 0
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def chunk_narration_phrases(text: str, max_words: int = 5) -> List[str]:
    """Chunk a sentence or paragraph into short, easily readable phrases."""
    words = text.strip().split()
    if not words:
        return []
    chunks = []
    curr = []
    for w in words:
        curr.append(w)
        # End chunk if punctuation or word limit reached
        if len(curr) >= max_words or w.endswith((".", ",", "!", "?", ";", ":")):
            chunks.append(" ".join(curr))
            curr = []
    if curr:
        chunks.append(" ".join(curr))
    return chunks


def build_subtitle_cues(
    narrations: List[str], durations: List[float]
) -> List[Tuple[float, float, str]]:
    """
    Build timed subtitle cues across all scenes.
    Returns list of (start_seconds, end_seconds, cue_text).
    """
    cues: List[Tuple[float, float, str]] = []
    timeline_offset = 0.0

    for text, duration in zip(narrations, durations):
        clean_text = text.strip()
        if not clean_text or duration <= 0:
            timeline_offset += max(duration, 0.0)
            continue

        phrases = chunk_narration_phrases(clean_text)
        if not phrases:
            timeline_offset += duration
            continue

        # Distribute scene duration proportional to character count of phrases
        total_chars = sum(len(p) for p in phrases) or 1
        scene_pos = timeline_offset

        for idx, phrase in enumerate(phrases):
            fraction = len(phrase) / total_chars
            phrase_dur = duration * fraction
            start_t = scene_pos
            end_t = (
                timeline_offset + duration
                if idx == len(phrases) - 1
                else scene_pos + phrase_dur
            )

            cues.append((start_t, end_t, phrase))
            scene_pos = end_t

        timeline_offset += duration

    return cues


def generate_srt(
    narrations: List[str], durations: List[float], output_path: str
) -> str:
    """Generate standard SRT subtitle file."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    cues = build_subtitle_cues(narrations, durations)

    lines = []
    for idx, (start_t, end_t, text) in enumerate(cues, start=1):
        lines.append(str(idx))
        lines.append(f"{_format_srt_timestamp(start_t)} --> {_format_srt_timestamp(end_t)}")
        lines.append(text)
        lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path


def generate_ass(
    narrations: List[str],
    durations: List[float],
    output_path: str,
    font_name: str = "Arial",
    font_size: int = 58,
) -> str:
    """
    Generate styled Advanced SubStation Alpha (ASS) subtitles.
    Pre-configured with bold high-contrast styling and safe vertical margins for 9:16 Shorts.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    cues = build_subtitle_cues(narrations, durations)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,{SAFE_MARGIN_SIDES},{SAFE_MARGIN_SIDES},{SAFE_MARGIN_BOTTOM},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for start_t, end_t, text in cues:
        st = _format_ass_timestamp(start_t)
        et = _format_ass_timestamp(end_t)
        # Escape any special characters for ASS
        escaped_text = text.replace("{", "(").replace("}", ")")
        events.append(f"Dialogue: 0,{st},{et},Default,,0,0,0,,{escaped_text}")

    full_content = header + "\n".join(events) + "\n"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_content)

    return output_path
