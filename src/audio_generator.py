"""
Audio Generation Module using Deepgram Aura TTS.

Provides high-quality English narration with deterministic caching,
bounded exponential backoff retries, duration measurement via ffprobe,
audio integrity validation, and an explicit, configurable Edge-TTS fallback.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import subprocess
import time
from typing import Optional

import requests

from config import (
    CACHE_DIR,
    DEEPGRAM_API_KEY,
    DEEPGRAM_VOICE,
    EDGE_TTS_VOICE,
    FALLBACK_TO_EDGE_TTS,
)

DEEPGRAM_TTS_URL = "https://api.deepgram.com/v1/speak"
AUDIO_CACHE_DIR = os.path.join(CACHE_DIR, "audio")


def _get_ffprobe_bin() -> str:
    """Return path to ffprobe binary."""
    probe = shutil.which("ffprobe")
    if probe:
        return probe
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        candidate = os.path.join(os.path.dirname(ffmpeg), "ffprobe.exe" if os.name == "nt" else "ffprobe")
        if os.path.exists(candidate):
            return candidate
    return "ffprobe"


def get_audio_duration(audio_path: str) -> float:
    """
    Measure exact duration of an audio file in seconds using ffprobe.
    Falls back to estimation if ffprobe fails.
    """
    if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 100:
        return 0.0

    probe_bin = _get_ffprobe_bin()
    cmd = [
        probe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode == 0 and res.stdout.strip():
            return float(res.stdout.strip())
    except Exception:
        pass

    # Basic fallback approximation for MP3 (~128kbps = 16000 bytes/sec)
    return round(os.path.getsize(audio_path) / 16000.0, 2)


def validate_audio_file(audio_path: str) -> bool:
    """Validate that audio file exists, has content, and reports valid duration."""
    if not os.path.exists(audio_path):
        return False
    if os.path.getsize(audio_path) < 1000:
        return False
    dur = get_audio_duration(audio_path)
    return dur > 0.2


def _cache_path_for_text(text: str, voice: str, provider: str = "deepgram") -> str:
    """Generate deterministic cache file path for given text and voice."""
    os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)
    cache_key = hashlib.sha256(f"{provider}:{voice}:{text.strip()}".encode("utf-8")).hexdigest()
    return os.path.join(AUDIO_CACHE_DIR, f"{cache_key}.mp3")


async def _generate_with_edge_tts(text: str, output_path: str, voice: str) -> str:
    """Generate speech using edge-tts asynchronously."""
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)
    return output_path


def generate_audio(
    text: str,
    output_path: str,
    voice: Optional[str] = None,
    api_key: Optional[str] = None,
    retries: int = 4,
    fallback_to_edge: Optional[bool] = None,
) -> str:
    """
    Generate speech audio for text using Deepgram Aura API.
    Caches audio deterministically, retries with bounded exponential backoff,
    and supports explicit Edge TTS fallback when enabled.

    Returns the absolute path to the generated audio file.
    """
    text = text.strip()
    if not text:
        raise ValueError("Cannot generate audio for empty text string.")

    selected_voice = voice or DEEPGRAM_VOICE or "aura-asteria-en"
    key = api_key or DEEPGRAM_API_KEY
    allow_edge_fallback = (
        fallback_to_edge if fallback_to_edge is not None else FALLBACK_TO_EDGE_TTS
    )

    # Check deterministic cache first
    cached_file = _cache_path_for_text(text, selected_voice, provider="deepgram")
    if os.path.exists(cached_file) and validate_audio_file(cached_file):
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        shutil.copyfile(cached_file, output_path)
        return output_path

    # Deepgram Aura execution
    if key:
        url = f"{DEEPGRAM_TTS_URL}?model={selected_voice}"
        headers = {
            "Authorization": f"Token {key}",
            "Content-Type": "application/json",
        }
        payload = {"text": text}

        for attempt in range(1, retries + 1):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=30)
                if resp.status_code == 200 and len(resp.content) > 500:
                    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                    with open(output_path, "wb") as f:
                        f.write(resp.content)

                    # Validate generated audio
                    if validate_audio_file(output_path):
                        # Save to cache
                        shutil.copyfile(output_path, cached_file)
                        return output_path

                if resp.status_code in (429, 500, 502, 503, 504):
                    backoff = min(2.0 * (2 ** (attempt - 1)), 20.0)
                    print(f"  [TTS] Deepgram status {resp.status_code}, retrying in {backoff:.1f}s (attempt {attempt}/{retries})...")
                    time.sleep(backoff)
                else:
                    print(f"  [TTS] Deepgram request failed with HTTP {resp.status_code}")
                    break
            except Exception as e:
                backoff = min(2.0 * (2 ** (attempt - 1)), 20.0)
                print(f"  [TTS] Network error during TTS request: {type(e).__name__}, retrying in {backoff:.1f}s...")
                time.sleep(backoff)

    # Explicit Fallback to Edge TTS if enabled
    if allow_edge_fallback:
        edge_voice = EDGE_TTS_VOICE or "en-US-ChristopherNeural"
        print(f"  [TTS] NOTICE: Deepgram unavailable — using explicit fallback to Edge TTS ({edge_voice}).")
        edge_cached = _cache_path_for_text(text, edge_voice, provider="edge_tts")
        if validate_audio_file(edge_cached):
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            shutil.copyfile(edge_cached, output_path)
            return output_path

        try:
            asyncio.run(_generate_with_edge_tts(text, output_path, edge_voice))
            if validate_audio_file(output_path):
                shutil.copyfile(output_path, edge_cached)
                return output_path
        except Exception as edge_err:
            print(f"  [TTS] Edge TTS fallback failed: {edge_err}")

    raise RuntimeError(
        "Audio generation failed: Deepgram Aura was unable to synthesize audio and "
        "no valid audio file was produced. Verify DEEPGRAM_API_KEY."
    )
