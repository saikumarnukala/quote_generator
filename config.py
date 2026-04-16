import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
HF_TOKEN           = os.getenv("HF_TOKEN")
PEXELS_API_KEY     = os.getenv("PEXELS_API_KEY")
JAMENDO_CLIENT_ID  = os.getenv("JAMENDO_CLIENT_ID", "")
PIXABAY_API_KEY    = os.getenv("PIXABAY_API_KEY", "")

# YouTube upload (optional — leave blank to skip)
YT_CLIENT_ID      = os.getenv("YT_CLIENT_ID")
YT_CLIENT_SECRET  = os.getenv("YT_CLIENT_SECRET")
YT_REFRESH_TOKEN  = os.getenv("YT_REFRESH_TOKEN")

# Instagram upload (optional — leave blank to skip)
INSTAGRAM_USER_ID      = os.getenv("INSTAGRAM_USER_ID")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")

# 9:16 vertical — YouTube Shorts & Instagram Reels (max supported: 1080×1920 @ 30fps)
VIDEO_WIDTH  = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS    = 30

OUTPUT_DIR = "output"
TEMP_DIR   = "temp"
