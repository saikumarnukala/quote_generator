import asyncio
import time
import edge_tts


# Per-language prosody: (rate, pitch)
# Slightly slower + lower pitch → more natural, less robotic
_LANG_PROSODY: dict = {
    "en": ("-10%", "-2Hz"),
    "te": ("-12%", "-3Hz"),
    "hi": ("-12%", "-3Hz"),
    "ta": ("-12%", "-3Hz"),
    "ja": ("-8%", "-2Hz"),
}

_DEFAULT_PROSODY = ("-10%", "-2Hz")


async def _generate_async(text: str, output_path: str, voice: str, rate: str, pitch: str) -> None:
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(output_path)


def generate_audio(
    text: str,
    output_path: str,
    voice: str = "en-US-AnaNeural",
    retries: int = 4,
    lang: str = "en",
) -> str:
    """Generate speech audio from text using Edge-TTS."""
    rate, pitch = _LANG_PROSODY.get(lang, _DEFAULT_PROSODY)
    for attempt in range(retries):
        try:
            asyncio.run(_generate_async(text, output_path, voice, rate, pitch))
            return output_path
        except Exception as e:
            if attempt < retries - 1:
                wait = 5 + attempt * 5
                print(f"    Edge-TTS error, retrying in {wait}s... ({type(e).__name__})")
                time.sleep(wait)
            else:
                raise
    return output_path


def get_audio_duration(audio_path: str) -> float:
    """Return the duration of an audio file in seconds."""
    from moviepy.editor import AudioFileClip

    clip = AudioFileClip(audio_path)
    duration = clip.duration
    clip.close()
    return duration


def list_voices() -> None:
    """Print all available Edge-TTS voices (utility helper)."""

    async def _list():
        voices = await edge_tts.list_voices()
        for v in voices:
            print(f"{v['ShortName']}  —  {v['Locale']}  {v['Gender']}")

    asyncio.run(_list())
