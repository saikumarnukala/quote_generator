import os
from dotenv import load_dotenv

load_dotenv()

# --- AI & API Credentials ---
GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "").strip()
PEXELS_API_KEY     = os.getenv("PEXELS_API_KEY", "").strip()
PIXABAY_API_KEY    = os.getenv("PIXABAY_API_KEY", "").strip()
DEEPGRAM_API_KEY   = os.getenv("DEEPGRAM_API_KEY", "").strip()

# --- Voice Settings ---
DEEPGRAM_VOICE     = os.getenv("DEEPGRAM_VOICE", "aura-asteria-en").strip()
EDGE_TTS_VOICE     = os.getenv("EDGE_TTS_VOICE", "en-US-ChristopherNeural").strip()
FALLBACK_TO_EDGE_TTS = os.getenv("FALLBACK_TO_EDGE_TTS", "false").lower() in ("true", "1", "yes")

# --- YouTube Upload Settings (Upload disabled by default) ---
YT_CLIENT_ID           = os.getenv("YT_CLIENT_ID", "").strip()
YT_CLIENT_SECRET       = os.getenv("YT_CLIENT_SECRET", "").strip()
YT_REFRESH_TOKEN       = os.getenv("YT_REFRESH_TOKEN", "").strip()
YOUTUBE_UPLOAD_ENABLED = os.getenv("YOUTUBE_UPLOAD_ENABLED", "false").lower() in ("true", "1", "yes")
YOUTUBE_PRIVACY_STATUS = os.getenv("YOUTUBE_PRIVACY_STATUS", "private").strip()

# --- Instagram Upload Settings (Optional / Disabled by default) ---
INSTAGRAM_USER_ID        = os.getenv("INSTAGRAM_USER_ID", "").strip()
INSTAGRAM_ACCESS_TOKEN   = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
INSTAGRAM_UPLOAD_ENABLED = os.getenv("INSTAGRAM_UPLOAD_ENABLED", "false").lower() in ("true", "1", "yes")

# --- Video Specs: 9:16 vertical (1080x1920 @ 30fps) ---
VIDEO_WIDTH  = int(os.getenv("VIDEO_WIDTH", "1080"))
VIDEO_HEIGHT = int(os.getenv("VIDEO_HEIGHT", "1920"))
VIDEO_FPS    = int(os.getenv("VIDEO_FPS", "30"))

# --- Directory Paths ---
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TEMP_DIR   = os.path.join(BASE_DIR, "temp")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
MUSIC_DIR  = os.path.join(ASSETS_DIR, "music")
DATA_DIR   = os.path.join(BASE_DIR, "data")
CACHE_DIR  = os.path.join(TEMP_DIR, "cache")
