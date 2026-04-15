"""
Synthesize a peaceful ambient music track using numpy.
No external audio library needed — writes a .wav using Python's built-in wave module.

Uses layered sine waves (a soft minor-pentatonic drone pad) with slow tremolo
and a gentle volume envelope for a calm, meditative feel.
"""

import math
import struct
import wave

import numpy as np


def generate_ambient(duration_seconds: float, output_path: str, sample_rate: int = 44100) -> str:
    """
    Generate a peaceful ambient WAV track.

    Args:
        duration_seconds: Total length in seconds (will add 2s fade-out).
        output_path:      Where to write the .wav file.
        sample_rate:      Audio sample rate (default 44100 Hz).

    Returns:
        output_path on success.
    """
    total_dur = duration_seconds + 2.0          # small tail for fade-out
    n_samples = int(sample_rate * total_dur)
    t = np.linspace(0, total_dur, n_samples, endpoint=False)

    # ── Peaceful minor-pentatonic drone ───────────────────────────────────
    # Frequencies: A2, C3, E3, G3, A3, E4 — calm and introspective
    layers = [
        # (freq_hz, amplitude, detune_hz, tremolo_rate, tremolo_depth)
        (110.00, 0.28, 0.00,  0.08, 0.04),   # A2  — deep root
        (130.81, 0.18, 0.07,  0.11, 0.05),   # C3  — minor 3rd
        (164.81, 0.22, 0.00,  0.09, 0.04),   # E3  — 5th
        (196.00, 0.14, -0.05, 0.13, 0.06),   # G3  — minor 7th
        (220.00, 0.20, 0.00,  0.07, 0.03),   # A3  — octave
        (329.63, 0.10, 0.08,  0.15, 0.05),   # E4  — high 5th (shimmer)
        (440.00, 0.06, -0.06, 0.18, 0.07),   # A4  — high shimmer
    ]

    signal = np.zeros(n_samples, dtype=np.float64)

    for freq, amp, detune, trem_rate, trem_depth in layers:
        # Main tone + soft detuned copy for warmth
        tone = np.sin(2 * math.pi * freq * t)
        if detune != 0:
            tone = (tone + np.sin(2 * math.pi * (freq + detune) * t)) * 0.5

        # Soft tremolo (slow amplitude modulation)
        tremolo = 1.0 - trem_depth + trem_depth * np.sin(2 * math.pi * trem_rate * t)
        signal += amp * tone * tremolo

    # ── Add a very soft high-frequency shimmer (5th octave harmonic) ─────
    shimmer_freq = 880.0
    shimmer = 0.03 * np.sin(2 * math.pi * shimmer_freq * t)
    shimmer *= (0.5 + 0.5 * np.sin(2 * math.pi * 0.25 * t))   # slow pulse
    signal += shimmer

    # ── Volume envelope: slow fade-in (3s) + fade-out (last 3s) ──────────
    fade_in_samples  = min(int(sample_rate * 3.0), n_samples // 4)
    fade_out_samples = min(int(sample_rate * 3.0), n_samples // 4)

    env = np.ones(n_samples, dtype=np.float64)
    env[:fade_in_samples]   = np.linspace(0.0, 1.0, fade_in_samples)
    env[-fade_out_samples:] = np.linspace(1.0, 0.0, fade_out_samples)
    signal *= env

    # ── Soft overall compression (prevent clipping) ───────────────────────
    peak = np.max(np.abs(signal))
    if peak > 0:
        signal = signal / peak * 0.72    # leave headroom

    # ── Convert to 16-bit PCM ─────────────────────────────────────────────
    pcm = (signal * 32767).astype(np.int16)

    # ── Write WAV ─────────────────────────────────────────────────────────
    with wave.open(output_path, "w") as wf:
        wf.setnchannels(1)           # mono
        wf.setsampwidth(2)           # 16-bit = 2 bytes
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())

    return output_path
