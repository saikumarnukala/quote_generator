"""
FFmpeg-based Video Assembly and Rendering Module.

Assembles scene video clips, narration audio, background music,
and burning-in subtitles into high-quality 1080x1920 (9:16) MP4 files.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import List, Optional

from config import TEMP_DIR, VIDEO_FPS, VIDEO_HEIGHT, VIDEO_WIDTH


def _get_ffmpeg_bin() -> str:
    bin_path = shutil.which("ffmpeg")
    return bin_path if bin_path else "ffmpeg"


def _escape_filter_path(path: str) -> str:
    """Escape windows backslashes and special characters for FFmpeg filter syntax."""
    # Convert to forward slashes and escape colon
    normalized = path.replace("\\", "/")
    # Escape colon (e.g. D:/ -> D\:/) and single quotes
    escaped = normalized.replace(":", "\\:").replace("'", "\\'")
    return escaped


def conform_scene_clip(
    src_video_path: str,
    target_duration: float,
    output_path: str,
) -> bool:
    """Trim or loop input video clip to exactly target_duration seconds at 1080x1920 @ 30fps."""
    ffmpeg = _get_ffmpeg_bin()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    cmd = [
        ffmpeg,
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        src_video_path,
        "-t",
        f"{target_duration:.3f}",
        "-vf",
        f"scale=w={VIDEO_WIDTH}:h={VIDEO_HEIGHT}:force_original_aspect_ratio=increase,crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},setsar=1",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-r",
        str(VIDEO_FPS),
        "-pix_fmt",
        "yuv420p",
        "-an",
        "-loglevel",
        "error",
        output_path,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception:
        return False


def concat_audio_tracks(audio_paths: List[str], output_path: str) -> bool:
    """Concatenate individual scene narration audio files into a single coherent track."""
    ffmpeg = _get_ffmpeg_bin()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    concat_list_file = os.path.join(os.path.dirname(output_path), "audio_concat.txt")
    with open(concat_list_file, "w", encoding="utf-8") as f:
        for p in audio_paths:
            f.write(f"file '{p.replace(os.sep, '/')}'\n")

    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        concat_list_file,
        "-c:a",
        "pcm_s16le",
        "-ar",
        "44100",
        "-ac",
        "2",
        "-loglevel",
        "error",
        output_path,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception:
        return False


def mix_audio_with_music(
    voiceover_path: str,
    music_path: Optional[str],
    total_duration: float,
    output_path: str,
    music_volume: float = 0.16,
) -> bool:
    """
    Mix narration voiceover with background music (with volume control, fade-in, and fade-out).
    If music_path is None or invalid, normalizes voiceover track alone.
    """
    ffmpeg = _get_ffmpeg_bin()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    has_valid_music = music_path and os.path.exists(music_path) and os.path.getsize(music_path) > 2000

    if has_valid_music:
        fade_out_start = max(total_duration - 2.5, 0.5)
        # Loop music, adjust volume, fade in & out, mix with voiceover
        music_filter = (
            f"[1:a]aloop=loop=-1:size=2e+09,volume={music_volume:.2f},"
            f"afade=t=in:ss=0:d=1.5,"
            f"afade=t=out:st={fade_out_start:.2f}:d=2.0[music];"
            f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[out]"
        )
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            voiceover_path,
            "-i",
            music_path,
            "-filter_complex",
            music_filter,
            "-map",
            "[out]",
            "-t",
            f"{total_duration:.3f}",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-loglevel",
            "error",
            output_path,
        ]
    else:
        # Voiceover only
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            voiceover_path,
            "-t",
            f"{total_duration:.3f}",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-loglevel",
            "error",
            output_path,
        ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        return res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception:
        return False


def build_infotainment_video(
    scene_video_paths: List[str],
    scene_audio_paths: List[str],
    scene_durations: List[float],
    output_path: str,
    subtitle_ass_path: Optional[str] = None,
    music_path: Optional[str] = None,
    music_volume: float = 0.16,
) -> str:
    """
    Main video builder orchestrator:
      1. Conforms each scene clip to its exact narration duration.
      2. Concatenates video scenes.
      3. Combines narration audios and mixes with background music.
      4. Burns in styled ASS subtitles and multiplexes video + audio.
      5. Produces validated, compliant 1080x1920 MP4 file.
    """
    ffmpeg = _get_ffmpeg_bin()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    temp_work_dir = os.path.join(TEMP_DIR, f"build_{int(time.time())}")
    os.makedirs(temp_work_dir, exist_ok=True)

    print(f"  [Render] Preparing {len(scene_video_paths)} scene clips...")

    conformed_clips: List[str] = []
    for idx, (v_path, dur) in enumerate(zip(scene_video_paths, scene_durations), start=1):
        conformed_dest = os.path.join(temp_work_dir, f"conformed_scene_{idx:02d}.mp4")
        if not conform_scene_clip(v_path, dur, conformed_dest):
            raise RuntimeError(f"Failed to conform scene video clip {idx} ({v_path}).")
        conformed_clips.append(conformed_dest)

    # 1. Concatenate video clips
    video_concat_list = os.path.join(temp_work_dir, "video_concat.txt")
    with open(video_concat_list, "w", encoding="utf-8") as f:
        for p in conformed_clips:
            f.write(f"file '{p.replace(os.sep, '/')}'\n")

    concatenated_video = os.path.join(temp_work_dir, "concatenated_video.mp4")
    cmd_concat_video = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        video_concat_list,
        "-c",
        "copy",
        "-loglevel",
        "error",
        concatenated_video,
    ]
    res_v = subprocess.run(cmd_concat_video, capture_output=True, text=True, timeout=120)
    if res_v.returncode != 0 or not os.path.exists(concatenated_video):
        raise RuntimeError("Failed to concatenate scene video tracks.")

    # 2. Assemble narration audio
    assembled_narration = os.path.join(temp_work_dir, "narration_full.wav")
    if not concat_audio_tracks(scene_audio_paths, assembled_narration):
        raise RuntimeError("Failed to concatenate narration audio tracks.")

    total_duration = sum(scene_durations)

    # 3. Mix narration with background music
    mixed_audio = os.path.join(temp_work_dir, "mixed_audio.aac")
    if not mix_audio_with_music(
        assembled_narration,
        music_path,
        total_duration,
        mixed_audio,
        music_volume=music_volume,
    ):
        raise RuntimeError("Failed to mix video audio track.")

    # 4. Burn in subtitles and multiplex final MP4
    print("  [Render] Encoding final 1080x1920 MP4 with subtitles...")

    vf_filters = []
    if subtitle_ass_path and os.path.exists(subtitle_ass_path):
        escaped_sub = _escape_filter_path(subtitle_ass_path)
        vf_filters.append(f"ass='{escaped_sub}'")

    vf_arg = ",".join(vf_filters) if vf_filters else "null"

    final_cmd = [
        ffmpeg,
        "-y",
        "-i",
        concatenated_video,
        "-i",
        mixed_audio,
        "-vf",
        vf_arg,
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-profile:v",
        "high",
        "-level:v",
        "4.0",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(VIDEO_FPS),
        "-c:a",
        "copy",
        "-t",
        f"{total_duration:.3f}",
        "-movflags",
        "+faststart",
        "-loglevel",
        "error",
        output_path,
    ]

    try:
        res_final = subprocess.run(final_cmd, capture_output=True, text=True, timeout=180)
        if res_final.returncode != 0:
            print("  [Render] Subtitle filter warning, attempting fallback without subtitle filter...")
            # Fallback without subtitle filter if libass had any path formatting glitch
            fallback_cmd = [
                ffmpeg,
                "-y",
                "-i",
                concatenated_video,
                "-i",
                mixed_audio,
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(VIDEO_FPS),
                "-c:a",
                "copy",
                "-t",
                f"{total_duration:.3f}",
                "-movflags",
                "+faststart",
                "-loglevel",
                "error",
                output_path,
            ]
            res_fb = subprocess.run(fallback_cmd, capture_output=True, text=True, timeout=180)
            if res_fb.returncode != 0:
                raise RuntimeError(f"FFmpeg render failed: {res_final.stderr or res_fb.stderr}")

    finally:
        # Clean up temporary scene build artifacts
        shutil.rmtree(temp_work_dir, ignore_errors=True)

    if not os.path.exists(output_path) or os.path.getsize(output_path) < 10000:
        raise RuntimeError("Video rendering did not produce a valid output MP4.")

    print(f"  [Render] Completed MP4 rendering -> {output_path}")
    return output_path
