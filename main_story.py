"""
Anime Story Video Generator
===========================
Generates dramatic anime story videos using AI.
- Story: Groq (Llama 3.3)
- Images: HuggingFace (SD3)
- Animation: fal.ai (Wan 2.1)
- Voiceover: Edge-TTS
- Assembly: MoviePy

Ready for YouTube Shorts and Instagram Reels.
"""
import json
import os
import random
import shutil
import sys
import time
import asyncio
import traceback
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from config import GROQ_API_KEY, HF_TOKEN, YT_CLIENT_ID, OUTPUT_DIR, TEMP_DIR
# fal.ai key is usually FAL_KEY or similar
FAL_KEY = os.getenv("FAL_KEY")

from src.story_generator import generate_story
from src.image_generator import generate_image
from src.video_clip_generator import generate_video_clip
from src.audio_generator import generate_audio, get_audio_duration
from src.video_builder import build_video
from src.youtube_uploader import upload_to_youtube
from src.instagram_uploader import upload_to_instagram
from src.history import record_run
from src.quote_generator import generate_video_metadata

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STORY_TOPICS = [
    "A lonely samurai finding peace in a hidden valley",
    "A cyberpunk hacker discovering an ancient digital spirit",
    "A magical girl protecting the last cherry blossom tree",
    "A space explorer landing on a planet of floating islands",
    "A mysterious train that travels through dreams",
]

def _auto_topic() -> str:
    return random.choice(STORY_TOPICS)

def _setup_dirs() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)

def _cleanup_temp() -> None:
    if os.path.exists(TEMP_DIR):
        for fname in os.listdir(TEMP_DIR):
            fpath = os.path.join(TEMP_DIR, fname)
            try:
                if os.path.isfile(fpath):
                    os.unlink(fpath)
                elif os.path.isdir(fpath):
                    shutil.rmtree(fpath, ignore_errors=True)
            except Exception:
                pass
    os.makedirs(TEMP_DIR, exist_ok=True)

def _safe_filename(title: str) -> str:
    return "".join(c if c.isalnum() or c in " _-" else "" for c in title).replace(" ", "_")[:60]

def _upload_with_retry(platform: str, fn, retries: int = 3, delay: int = 30):
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as e:
            print(f"  {platform} attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(delay)
    return None

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run(topic: str = None, num_scenes: int = 5, language: str = "en"):
    _setup_dirs()
    if not topic:
        topic = _auto_topic()

    print(f"\n{'=' * 55}")
    print(f"  Anime Story Video Generator")
    print(f"  Topic   : {topic}")
    print(f"  Scenes  : {num_scenes}")
    print(f"  Language: {language}")
    print(f"{'=' * 55}\n")

    # 1. Generate Story
    print("[ 1/5 ] Generating story script (Groq)...")
    used_quotes = get_used_quotes()
    try:
        story_data = generate_story(topic, GROQ_API_KEY, num_scenes=num_scenes, language=language, used_quotes=used_quotes)
    except Exception as e:
        print(f"  Story generation failed: {e}")
        return

    title = story_data["title"]
    scenes = story_data["scenes"]
    print(f"        Title: {title}")

    # 2. Generate Images & Audio
    print("\n[ 2/5 ] Generating images (SD3) and narration (Edge-TTS)...")
    video_paths = []
    audio_paths = []
    scene_durations = []

    for i, scene in enumerate(scenes):
        print(f"        Scene {i+1}/{len(scenes)}...")
        
        # Audio
        audio_path = os.path.join(TEMP_DIR, f"audio_{i+1:02d}.mp3")
        generate_audio(scene["narration"], audio_path, lang=language)
        audio_paths.append(audio_path)
        
        # Get duration for this scene based on audio
        dur = get_audio_duration(audio_path) + 1.0  # Add 1s padding
        scene_durations.append(dur)

        # Image
        img_path = os.path.join(TEMP_DIR, f"image_{i+1:02d}.png")
        generate_image(scene["image_prompt"], HF_TOKEN, img_path)
        
        # 3. Animate (Image to Video)
        print(f"        Animating Scene {i+1} (fal.ai)...")
        vid_path = os.path.join(TEMP_DIR, f"scene_{i+1:02d}.mp4")
        try:
            generate_video_clip(img_path, "cinematic movement, anime style", vid_path, FAL_KEY, duration="5")
        except Exception as e:
            print(f"        Animation failed for scene {i+1}: {e} — using static image as fallback.")
            # video_builder now handles .png/.jpg directly as static clips
            vid_path = img_path 

        video_paths.append(vid_path)

    # 4. Generate Metadata
    print("\n[ 3/5 ] Generating YouTube metadata...")
    # Adapt story scenes to quote structure for the metadata generator
    meta_scenes = []
    for s in scenes:
        meta_scenes.append({
            "quote": s["narration"],
            "author": "Anime Narrator"
        })
    
    try:
        meta = generate_video_metadata(topic, title, meta_scenes, GROQ_API_KEY, language=language)
        yt_title = meta["yt_title"]
        yt_desc  = meta["description"]
        yt_tags  = meta["tags"]
        hashtags = " ".join(meta["hashtags"])
    except Exception:
        yt_title = f"{title} #Shorts"
        yt_desc  = f"An epic anime story about {topic}."
        yt_tags  = ["anime", "story", "shorts", "aiart"]
        hashtags = "#anime #aiart #shorts"

    # 5. Build Final Video
    print("\n[ 4/5 ] Assembling final video...")
    if not FAL_KEY:
        print("  WARNING: FAL_KEY not set — animation will likely fail.")

    safe = _safe_filename(title)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(OUTPUT_DIR, f"Story_{safe}_{ts}.mp4")

    try:
        # Use a dynamic duration per scene based on audio, or a fixed 5s for animation
        # Since build_video uses a fixed scene_duration for now, we'll use 6s as a good middle ground
        build_video(
            scenes=scenes,
            video_paths=video_paths,
            output_path=output_path,
            audio_paths=audio_paths,
            music_path=None,
            quote_data=scenes,  # This will show narration as text
            scene_duration=6.0
        )
    except Exception as e:
        print(f"  Video build failed: {e}")
        traceback.print_exc()
        return

    print(f"\n  Done! Video -> {output_path}")

    # 6. Record History
    try:
        record_run(
            quotes=[s["narration"] for s in scenes],
            video_ids=[],  # We use fal.ai, not Pexels, so no IDs to track
            music_id=None
        )
    except Exception as e:
        print(f"  [History] Save failed: {e}")

    # 7. Upload
    print("\n[ 5/5 ] Uploading to YouTube...")
    yt_url = _upload_with_retry(
        "YouTube",
        lambda: upload_to_youtube(output_path, title=yt_title, description=yt_desc, tags=yt_tags)
    )

    print(f"\n  Published YouTube -> {yt_url or '(failed)'}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", help="Story theme")
    parser.add_argument("--scenes", type=int, default=5)
    parser.add_argument("--lang", default="en")
    args = parser.parse_args()
    
    run(topic=args.topic, num_scenes=args.scenes, language=args.lang)
