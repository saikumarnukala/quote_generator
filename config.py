import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
HF_TOKEN     = os.getenv("HF_TOKEN")

VIDEO_WIDTH  = 1280
VIDEO_HEIGHT = 720
VIDEO_FPS    = 24

OUTPUT_DIR = "output"
TEMP_DIR   = "temp"
