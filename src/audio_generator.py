import time
import requests
from config import DEEPGRAM_API_KEY

def generate_audio(
    text: str,
    output_path: str,
    voice: str = "aura-asteria-en",
    retries: int = 4,
    lang: str = "en",
) -> str:
    """Generate speech audio from text using Deepgram Aura API."""
    if not DEEPGRAM_API_KEY:
        raise ValueError("DEEPGRAM_API_KEY is not set in environment or config.")
        
    url = f"https://api.deepgram.com/v1/speak?model={voice}"
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {"text": text}

    for attempt in range(retries):
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            with open(output_path, "wb") as f:
                f.write(response.content)
            return output_path
        except Exception as e:
            if attempt < retries - 1:
                wait = 5 + attempt * 5
                print(f"    Deepgram error, retrying in {wait}s... ({type(e).__name__}): {e}")
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
