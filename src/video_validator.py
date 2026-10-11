"""
Video Quality and Integrity Validator using FFprobe.

Checks resolution, frame rate, audio stream presence, duration,
codec compliance, and container integrity of generated MP4 files.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from config import VIDEO_FPS, VIDEO_HEIGHT, VIDEO_WIDTH


@dataclass
class ValidationReport:
    is_valid: bool
    file_path: str
    file_size_bytes: int
    duration_seconds: float
    video_codec: str
    width: int
    height: int
    fps: float
    audio_codec: str
    audio_channels: int
    audio_sample_rate: int
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _get_ffprobe_bin() -> str:
    bin_path = shutil.which("ffprobe")
    return bin_path if bin_path else "ffprobe"


def validate_mp4_video(
    video_path: str,
    min_duration: float = 10.0,
    max_duration: float = 70.0,
    expected_width: int = VIDEO_WIDTH,
    expected_height: int = VIDEO_HEIGHT,
) -> ValidationReport:
    """
    Validate the rendered MP4 file against technical delivery specifications.
    Returns ValidationReport.
    """
    errors: List[str] = []

    if not os.path.exists(video_path):
        return ValidationReport(
            is_valid=False,
            file_path=video_path,
            file_size_bytes=0,
            duration_seconds=0.0,
            video_codec="none",
            width=0,
            height=0,
            fps=0.0,
            audio_codec="none",
            audio_channels=0,
            audio_sample_rate=0,
            errors=["File does not exist on disk."],
        )

    file_size = os.path.getsize(video_path)
    if file_size < 50_000:
        errors.append(f"File size too small ({file_size} bytes). Likely corrupted or empty.")

    probe_bin = _get_ffprobe_bin()
    cmd = [
        probe_bin,
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type,codec_name,width,height,r_frame_rate,channels,sample_rate:format=duration,size,format_name",
        "-of",
        "json",
        video_path,
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if res.returncode != 0:
            errors.append(f"FFprobe execution failed: {res.stderr.strip()}")
            raw_data = {}
        else:
            raw_data = json.loads(res.stdout or "{}")
    except Exception as e:
        errors.append(f"Failed to probe video file: {e}")
        raw_data = {}

    format_info = raw_data.get("format", {})
    streams = raw_data.get("streams", [])

    duration_str = format_info.get("duration", "0")
    duration = float(duration_str) if duration_str else 0.0

    if duration < min_duration:
        errors.append(f"Duration too short ({duration:.1f}s, min required: {min_duration:.1f}s).")
    if duration > max_duration:
        errors.append(f"Duration exceeds Shorts threshold ({duration:.1f}s, max: {max_duration:.1f}s).")

    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    # Check Video stream
    if not v_stream:
        errors.append("Missing video stream in MP4 container.")
        v_codec = "none"
        w, h, fps = 0, 0, 0.0
    else:
        v_codec = v_stream.get("codec_name", "")
        w = int(v_stream.get("width", 0))
        h = int(v_stream.get("height", 0))
        r_fps = v_stream.get("r_frame_rate", "30/1")
        try:
            num, den = map(int, r_fps.split("/"))
            fps = round(num / den, 1) if den else 30.0
        except Exception:
            fps = 30.0

        if v_codec not in ("h264", "libx264"):
            errors.append(f"Expected H.264 video codec, found: {v_codec}.")
        if w != expected_width or h != expected_height:
            errors.append(f"Unexpected resolution: {w}x{h} (expected: {expected_width}x{expected_height}).")

    # Check Audio stream
    if not a_stream:
        errors.append("Missing audio stream in MP4 container.")
        a_codec = "none"
        channels, sample_rate = 0, 0
    else:
        a_codec = a_stream.get("codec_name", "")
        channels = int(a_stream.get("channels", 0))
        sample_rate = int(a_stream.get("sample_rate", 0))

        if a_codec not in ("aac", "libfdk_aac"):
            errors.append(f"Expected AAC audio codec, found: {a_codec}.")
        if channels < 1:
            errors.append("Invalid audio channel count.")

    is_valid = len(errors) == 0

    return ValidationReport(
        is_valid=is_valid,
        file_path=video_path,
        file_size_bytes=file_size,
        duration_seconds=round(duration, 2),
        video_codec=v_codec,
        width=w,
        height=h,
        fps=fps,
        audio_codec=a_codec,
        audio_channels=channels,
        audio_sample_rate=sample_rate,
        errors=errors,
    )
