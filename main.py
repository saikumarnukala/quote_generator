"""
Peaceful Quotes Video Generator
================================
Generates calming AI landscape scenes paired with inspirational quotes
and peaceful ambient music. Ready for YouTube and Instagram.

Usage:
    python main.py                                  <- auto rotating topic
    python main.py "gratitude and inner peace"      <- custom topic
    python main.py --scenes 8 --lang te             <- Telugu, 8 scenes
    python main.py --music ./jamendo_track.mp3 --allow-jamendo-upload
"""
import json
import os
import random
import shutil
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from config import GROQ_API_KEY, PEXELS_API_KEY, OUTPUT_DIR, TEMP_DIR
from src.quote_generator import generate_quotes
from src.video_fetcher import fetch_nature_video
from src.ambient_generator import generate_ambient
from src.video_builder import build_video
from src.youtube_uploader import upload_to_youtube
from src.instagram_uploader import upload_to_instagram


# ---------------------------------------------------------------------------
# Rotating topic pool  (used when no topic is given)
# ---------------------------------------------------------------------------
TOPICS = [
    "inner peace and mindfulness",
    "the beauty of nature and solitude",
    "gratitude and joy in simple things",
    "courage and personal growth",
    "love, kindness and compassion",
    "letting go and finding freedom",
    "strength through silence",
    "the wisdom of patience",
    "harmony between mind and nature",
    "living in the present moment",
    "hope and new beginnings",
    "the power of a calm mind",
    "self-love and acceptance",
    "finding light in darkness",
    "the art of being still",
]

LANGUAGE_NAMES = {
    "en": "English",
    "te": "Telugu",
    "hi": "Hindi",
    "ta": "Tamil",
    "ja": "Japanese",
}


def _auto_topic() -> str:
    """Pick a topic that rotates 3 times per day automatically."""
    slot = datetime.now().hour // 8          # 0 (midnight), 1 (8am), 2 (4pm)
    idx  = (datetime.now().timetuple().tm_yday * 3 + slot) % len(TOPICS)
    return TOPICS[idx]


def _setup_dirs() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)


def _cleanup_temp() -> None:
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR, exist_ok=True)


def _safe_filename(title: str) -> str:
    return "".join(c if c.isalnum() or c in " _-" else "" for c in title).replace(" ", "_")[:60]


def _is_jamendo_track(music_path: str) -> bool:
    if not music_path:
        return False
    return "jamendo" in os.path.normpath(music_path).lower()


def _check_env() -> None:
    missing = []
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if not PEXELS_API_KEY:
        missing.append("PEXELS_API_KEY")
    if missing:
        print("ERROR: Missing environment variables in .env:")
        for k in missing:
            print(f"  - {k}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

SCENE_DURATION = 12.0   # seconds per scene — comfortable reading time


def run(topic: str = None, num_scenes: int = 7, language: str = "en",
        music_path: str = None, allow_jamendo_upload: bool = False) -> str:
    _check_env()
    _setup_dirs()

    if not topic:
        topic = _auto_topic()

    lang_name = LANGUAGE_NAMES.get(language, "English")

    print(f"\n{'=' * 55}")
    print(f"  Peaceful Quotes Video Generator")
    print(f"  Topic   : {topic}")
    print(f"  Scenes  : {num_scenes}")
    print(f"  Language: {lang_name}")
    print(f"{'=' * 55}\n")

    # ── Step 1 / 3 · Generate quotes & scene descriptions ─────────────
    print("[ 1/3 ] Generating quotes & peaceful scenes (Groq)...")
    data     = generate_quotes(topic, GROQ_API_KEY, num_scenes=num_scenes, language=language)
    scenes   = data["scenes"]
    title    = data["title"]
    print(f"        Title  : {title}")
    print(f"        Scenes : {len(scenes)}")

    with open(os.path.join(TEMP_DIR, "quotes.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # ── Step 2 / 3 · Fetch real nature footage from Pexels ───────────
    print("\n[ 2/3 ] Fetching real nature footage (Pexels)...")
    video_paths = []
    for i, scene in enumerate(scenes):
        print(f"        Scene {i + 1}/{len(scenes)}...")
        vid_path = os.path.join(TEMP_DIR, f"scene_{i + 1:02d}.mp4")
        search   = scene.get("video_search", scene.get("location", "peaceful nature"))
        fetch_nature_video(search, PEXELS_API_KEY, vid_path)
        video_paths.append(vid_path)
        print(f"        Scene {i + 1} ✓")

    # ── Step 3 / 3 · Build video ───────────────────────────────────────
    total_duration = SCENE_DURATION * len(scenes)

    if not music_path:
        print("\n[ 3/3 ] Generating ambient music + building video...")
        ambient_path = os.path.join(TEMP_DIR, "ambient.wav")
        generate_ambient(total_duration, ambient_path)
        music_path = ambient_path
    else:
        print("\n[ 3/3 ] Building video...")

    safe   = _safe_filename(title)
    ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = os.path.join(OUTPUT_DIR, f"{safe}_{ts}.mp4")

    build_video(
        scenes         = scenes,
        video_paths    = video_paths,
        output_path    = output,
        music_path     = music_path,
        quote_data     = scenes,
        scene_duration = SCENE_DURATION,
    )

    _cleanup_temp()

    print(f"\n{'=' * 55}")
    print(f"  Done!")
    print(f"  Video    → {output}")
    print(f"  Duration ~ {total_duration:.0f}s  ({total_duration / 60:.1f} min)")
    print(f"  Scenes   : {len(scenes)}")
    print(f"{'=' * 55}\n")

    # ── Optional: Upload to YouTube & Instagram ────────────────────────
    # Uploads are silently skipped if the required secrets are not set.
    if _is_jamendo_track(music_path) and not allow_jamendo_upload:
        print("[ Upload ] Skipped YouTube/Instagram upload.")
        print("  Reason: Jamendo music detected. Upload is blocked by default to reduce copyright claims.")
        print("  If you own the required Jamendo license/rights, rerun with --allow-jamendo-upload.")
        return output

    hashtags = "#peaceful #quotes #nature #mindfulness #motivation #shorts"
    caption  = f"{title}\n\n{hashtags}"

    print("[ Upload ] Posting to social media...")
    try:
        yt_url = upload_to_youtube(output, title=title, description=topic)
    except Exception as e:
        print(f"  YouTube upload failed: {e}")
        yt_url = None

    try:
        ig_url = upload_to_instagram(output, caption=caption)
    except Exception as e:
        print(f"  Instagram upload failed: {e}")
        ig_url = None

    if yt_url or ig_url:
        print(f"\n  Published:")
        if yt_url:
            print(f"    YouTube  → {yt_url}")
        if ig_url:
            print(f"    Instagram→ {ig_url}")

    return output


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Peaceful Quotes Video Generator")
    parser.add_argument("topic", nargs="*", help="Quote theme (optional — auto-rotates if omitted)")
    parser.add_argument("--scenes",  type=int, default=7,   help="Number of scenes (default: 7)")
    parser.add_argument("--lang",    default="en",
                        choices=list(LANGUAGE_NAMES.keys()),
                        help="Language: en, te (Telugu), hi (Hindi), ta (Tamil), ja (Japanese)")
    parser.add_argument("--music",   default=None,          help="Path to custom background music file")
    parser.add_argument("--allow-jamendo-upload", action="store_true",
                        help="Allow auto-upload when using Jamendo music (only if you have proper rights/license)")
    args = parser.parse_args()

    _topic = " ".join(args.topic).strip() if args.topic else None

    run(
        _topic,
        num_scenes=args.scenes,
        language=args.lang,
        music_path=args.music,
        allow_jamendo_upload=args.allow_jamendo_upload,
    )
