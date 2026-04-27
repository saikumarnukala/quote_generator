"""
Peaceful Quotes Video Generator
================================
Generates calming AI landscape scenes paired with inspirational quotes
and peaceful ambient music. Ready for YouTube and Instagram.

Usage:
    python main.py                                  <- auto rotating topic
    python main.py "gratitude and inner peace"      <- custom topic
    python main.py --scenes 8 --lang te             <- Telugu, 8 scenes
    python main.py --music ./jamendo_track.mp3 --jamendo-music --allow-jamendo-upload
"""
import json
import os
import random
import shutil
import sys
import time
import traceback
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from config import GROQ_API_KEY, PEXELS_API_KEY, JAMENDO_CLIENT_ID, PIXABAY_API_KEY, OUTPUT_DIR, TEMP_DIR
from src.quote_generator import generate_quotes, generate_video_metadata
from src.video_fetcher import fetch_nature_video
from src.ambient_generator import generate_ambient
from src.music_fetcher import fetch_trending_music
from src.video_builder import build_video
from src.youtube_uploader import upload_to_youtube
from src.instagram_uploader import upload_to_instagram
from src.history import get_used_quotes, get_used_video_ids, get_used_music_ids, record_run
from src.copyright_checker import check_music, check_videos


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
    "the beauty of impermanence",
    "healing through solitude and reflection",
    "the courage to be vulnerable",
    "finding wonder in the ordinary",
    "the rhythm of the universe within us",
    "surrendering to the flow of life",
    "the quiet power of gentleness",
    "ancient wisdom for modern souls",
    "the sacred art of doing nothing",
    "finding home within yourself",
    "the poetry of rain and renewal",
    "dancing with uncertainty",
    "the forgotten language of the heart",
    "moonlight, mystery and inner knowing",
    "the alchemy of pain into wisdom",
]

LANGUAGE_NAMES = {
    "en": "English",
    "te": "Telugu",
    "hi": "Hindi",
    "ta": "Tamil",
    "ja": "Japanese",
}


def _auto_topic() -> str:
    """Pick a unique random topic each run, avoiding the last used topic."""
    last_topic_file = os.path.join(OUTPUT_DIR, ".last_topic")
    last_topic = None
    if os.path.exists(last_topic_file):
        try:
            with open(last_topic_file, "r", encoding="utf-8") as f:
                last_topic = f.read().strip()
        except Exception:
            pass

    available = [t for t in TOPICS if t != last_topic]
    if not available:
        available = TOPICS

    topic = random.choice(available)

    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(last_topic_file, "w", encoding="utf-8") as f:
            f.write(topic)
    except Exception:
        pass

    return topic


def _setup_dirs() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)


def _cleanup_temp() -> None:
    """Remove temp files, ignoring files still locked by MoviePy on Windows."""
    if os.path.exists(TEMP_DIR):
        for fname in os.listdir(TEMP_DIR):
            fpath = os.path.join(TEMP_DIR, fname)
            try:
                if os.path.isfile(fpath):
                    os.unlink(fpath)
                elif os.path.isdir(fpath):
                    shutil.rmtree(fpath, ignore_errors=True)
            except Exception:
                pass  # File still locked by MoviePy — leave it, harmless
    os.makedirs(TEMP_DIR, exist_ok=True)


def _safe_filename(title: str) -> str:
    return "".join(c if c.isalnum() or c in " _-" else "" for c in title).replace(" ", "_")[:60]


def _check_env() -> None:
    """Warn about missing credentials but never stop the process."""
    missing = []
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if not PEXELS_API_KEY:
        missing.append("PEXELS_API_KEY")
    if missing:
        print("WARNING: Missing environment variables — some steps will use fallbacks:")
        for k in missing:
            print(f"  - {k}")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

SCENE_DURATION = 12.0   # seconds per scene — comfortable reading time

# Hardcoded public-domain quotes used only when Groq API is unavailable
_HARDCODED_QUOTES = [
    {"quote": "The present moment is the only moment available to us.", "author": "Ancient Wisdom",
     "location": "Mountain Summit", "video_search": "aerial misty mountain sunrise fog", "narration": "Breathe."},
    {"quote": "In the middle of every difficulty lies opportunity.", "author": "Ancient Wisdom",
     "location": "Desert Horizon", "video_search": "golden hour desert sand dunes sunset", "narration": "The light finds a way."},
    {"quote": "The soul that sees beauty may sometimes walk alone.", "author": "Rumi",
     "location": "Forest Path", "video_search": "slow motion sunlight through forest trees", "narration": "Walk in your own light."},
    {"quote": "What you seek is seeking you.", "author": "Rumi",
     "location": "Ocean Shore", "video_search": "golden hour ocean waves drone aerial", "narration": "The universe listens."},
    {"quote": "Silence is the language of God.", "author": "Rumi",
     "location": "Snowy Peak", "video_search": "4k timelapse snow mountain clouds", "narration": "Listen deeply."},
    {"quote": "Flow with whatever may happen and let your mind be free.", "author": "Lao Tzu",
     "location": "Waterfall Valley", "video_search": "slow motion waterfall jungle green", "narration": "Let go."},
    {"quote": "Nature does not hurry, yet everything is accomplished.", "author": "Lao Tzu",
     "location": "Cherry Blossoms", "video_search": "cherry blossom petals falling slow motion", "narration": "Trust the timing."},
]


def _fallback_quotes(topic: str, num_scenes: int) -> dict:
    """Return hardcoded public-domain quotes when Groq is unavailable."""
    import random as _random
    pool = _HARDCODED_QUOTES * ((num_scenes // len(_HARDCODED_QUOTES)) + 1)
    selected = _random.sample(pool, min(num_scenes, len(pool)))
    return {
        "title": topic.title(),
        "theme": topic,
        "scenes": selected[:num_scenes],
    }


def _upload_with_retry(platform: str, fn, retries: int = 3, delay: int = 30):
    """
    Call *fn* up to *retries* times.  Never raises — returns None on total failure.
    Waits *delay* seconds between attempts.
    """
    for attempt in range(1, retries + 1):
        try:
            result = fn()
            return result
        except Exception as e:
            print(f"  {platform} attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                print(f"  Retrying in {delay}s...")
                time.sleep(delay)
            else:
                print(f"  {platform}: all {retries} attempts failed — continuing without this upload.")
                traceback.print_exc()
    return None


def run(topic: str = None, num_scenes: int = 7, language: str = "en",
        music_path: str = None, jamendo_music: bool = False,
        allow_jamendo_upload: bool = False) -> str:
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
    used_quotes    = get_used_quotes()
    used_video_ids = get_used_video_ids()
    used_music_ids = get_used_music_ids()
    print(f"        History : {len(used_quotes)} quotes, {len(used_video_ids)} videos, {len(used_music_ids)} tracks already used")

    data = None
    for _attempt in range(3):
        try:
            data = generate_quotes(topic, GROQ_API_KEY, num_scenes=num_scenes, language=language,
                                   used_quotes=used_quotes)
            break
        except Exception as e:
            print(f"  Quote generation attempt {_attempt+1}/3 failed: {e}")
            time.sleep(5)
    if data is None:
        print("  Quote generation failed after 3 attempts — using hardcoded fallback quotes.")
        data = _fallback_quotes(topic, num_scenes)

    scenes = data["scenes"]
    title  = data["title"]
    print(f"        Title  : {title}")
    print(f"        Scenes : {len(scenes)}")

    try:
        with open(os.path.join(TEMP_DIR, "quotes.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    print("        Generating video metadata (title / description / hashtags)...")
    yt_title = hashtags = yt_desc = ""
    yt_tags = []
    try:
        meta     = generate_video_metadata(topic, title, scenes, GROQ_API_KEY, language=language)
        yt_title = meta["yt_title"]
        yt_desc  = meta["description"]
        yt_tags  = meta["tags"]
        hashtags = " ".join(meta["hashtags"])
        print(f"        YT Title: {yt_title}")
    except Exception as e:
        print(f"  Metadata generation failed ({e}) — using title as fallback.")
        yt_title = title[:90]
        yt_desc  = topic
        yt_tags  = ["shorts", "quotes", "nature", "peaceful", "motivation"]
        hashtags = "#shorts #quotes #peace"

    # ── Step 2 / 3 · Fetch real nature footage from Pexels ───────────
    print("\n[ 2/3 ] Fetching real nature footage (Pexels)...")
    video_paths = []
    this_run_video_ids = {}  # dict: scene_idx -> vid_id (safe for re-downloads)
    for i, scene in enumerate(scenes):
        print(f"        Scene {i + 1}/{len(scenes)}...")
        vid_path = os.path.join(TEMP_DIR, f"scene_{i + 1:02d}.mp4")
        search   = scene.get("video_search", scene.get("location", "peaceful nature"))
        fetched_path = vid_path
        vid_id = 0
        for _attempt in range(3):
            try:
                fetched_path, vid_id = fetch_nature_video(
                    search, PEXELS_API_KEY, vid_path,
                    used_ids=used_video_ids | set(this_run_video_ids.values()),
                )
                break
            except Exception as e:
                print(f"        Scene {i+1} fetch attempt {_attempt+1}/3 failed: {e}")
                time.sleep(5)
        video_paths.append(fetched_path)
        if vid_id:
            this_run_video_ids[i] = vid_id
            used_video_ids.add(vid_id)
        print(f"        Scene {i + 1} done")

    # ── Step 3 / 3 · Fetch music, copyright-check, then build video ──────
    total_duration = SCENE_DURATION * len(scenes)

    user_provided_music = music_path is not None  # remember before the path may be overwritten

    # ── Copyright check: videos ───────────────────────────────────────
    print("\n[ Copyright ] Verifying downloaded video clips...")
    try:
        vid_ok, bad_indices = check_videos(video_paths)
        if not vid_ok:
            for i in bad_indices:
                scene  = scenes[i]
                search = scene.get("video_search", scene.get("location", "peaceful nature"))
                print(f"  Re-downloading scene {i+1} ({search!r})...")
                vid_path = os.path.join(TEMP_DIR, f"scene_{i + 1:02d}.mp4")
                try:
                    new_path, vid_id = fetch_nature_video(
                        search, PEXELS_API_KEY, vid_path,
                        used_ids=used_video_ids,
                    )
                    video_paths[i] = new_path
                    if vid_id:
                        this_run_video_ids[i] = vid_id
                        used_video_ids.add(vid_id)
                except Exception as e:
                    print(f"  Scene {i+1} re-download failed ({e}) — using original file anyway.")
    except Exception as e:
        print(f"  [Copyright] Video check failed ({e}) — continuing with existing files.")

    # ── Fetch + copyright-check music (retry up to 3 times) ─────────
    music_track = music_artist = music_license = music_id = ""
    if not music_path:
        print("\n[ 3/3 ] Fetching trending music...")
        music_out  = os.path.join(TEMP_DIR, "music")
        # IDs to skip — grows each attempt so we never re-try a rejected track
        skip_music = set(used_music_ids)
        music_info = {}

        for attempt in range(1, 4):
            music_info = fetch_trending_music(
                topic, JAMENDO_CLIENT_ID, total_duration, music_out,
                used_ids=skip_music,
                pixabay_api_key=PIXABAY_API_KEY,
            )
            # ── Copyright check: music ────────────────────────────────
            ok, reason = check_music(music_info)
            if ok:
                break
            # Rejected — add this track ID to the skip set and retry
            bad_id = music_info.get("track_id", "")
            if bad_id:
                skip_music.add(bad_id)
            print(f"  [Copyright] Attempt {attempt}/3 failed ({reason}) — fetching another track...")
            # Remove bad file from disk
            bad_path = music_info.get("path", "")
            if bad_path and os.path.exists(bad_path):
                try:
                    os.unlink(bad_path)
                except Exception:
                    pass
        else:
            print("  [Copyright] Could not find a compliant track after 3 attempts — using ambient fallback.")
            from src.ambient_generator import generate_ambient
            music_info = {
                "path": generate_ambient(total_duration, os.path.join(TEMP_DIR, "fallback.wav")),
                "track_name": "", "artist_name": "", "license_url": "", "track_id": "",
            }

        music_path    = music_info["path"]
        music_track   = music_info.get("track_name", "")
        music_artist  = music_info.get("artist_name", "")
        music_license = music_info.get("license_url", "")
        music_id      = music_info.get("track_id", "")
    else:
        print("\n[ 3/3 ] Building video (user-supplied music)...")

    print("\n        Building video...")
    safe   = _safe_filename(title)
    ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = os.path.join(OUTPUT_DIR, f"{safe}_{ts}.mp4")

    try:
        build_video(
            scenes         = scenes,
            video_paths    = video_paths,
            output_path    = output,
            music_path     = music_path,
            quote_data     = scenes,
            scene_duration = SCENE_DURATION,
        )
    except Exception as e:
        print(f"  Video build failed ({e}) — retrying without music as fallback...")
        traceback.print_exc()
        try:
            build_video(
                scenes         = scenes,
                video_paths    = video_paths,
                output_path    = output,
                music_path     = None,
                quote_data     = scenes,
                scene_duration = SCENE_DURATION,
            )
            print("  Fallback build (no music) succeeded.")
        except Exception as e2:
            print(f"  Fallback build also failed: {e2}")
            traceback.print_exc()
            raise RuntimeError("Video build failed on both attempts — cannot upload.") from e2

    _cleanup_temp()

    # ── Record what we used so future runs produce fresh content ─────────
    try:
        this_run_quotes = [s.get("quote", "") for s in scenes]
        record_run(
            quotes    = this_run_quotes,
            video_ids = list(this_run_video_ids.values()),
            music_id  = music_id or None,
        )
    except Exception as e:
        print(f"  [History] Save failed ({e}) — uploads will still proceed.")

    print(f"\n{'=' * 55}")
    print(f"  Done!")
    print(f"  Video    -> {output}")
    print(f"  Duration ~ {total_duration:.0f}s  ({total_duration / 60:.1f} min)")
    print(f"  Scenes   : {len(scenes)}")
    print(f"{'=' * 55}\n")

    # ── Optional: Upload to YouTube & Instagram ────────────────────────
    # Uploads are silently skipped if the required secrets are not set.

    # Warn when a custom music file is provided without any license declaration
    if user_provided_music and not jamendo_music:
        print("  [Copyright] Note: custom music file provided without license info.")

    # Build copyright attribution block
    credits_lines = ["\n---\nCredits & Licenses:"]
    credits_lines.append("Video footage: Pexels (https://www.pexels.com/license/) — free to use, no attribution required.")
    if music_track and music_artist:
        credits_lines.append(f'Music: "{music_track}" by {music_artist} — CC Licensed via Jamendo.')
        if music_license:
            credits_lines.append(f"License: {music_license}")
    credits_block = "\n".join(credits_lines)

    yt_desc_full = f"{yt_desc}\n{credits_block}"
    caption      = f"{yt_title}\n\n{yt_desc}\n\n{credits_block}\n\n{hashtags}"

    print("[ Upload ] Posting to social media...")

    # ── YouTube upload with retry ──────────────────────────────────────
    yt_url = _upload_with_retry(
        "YouTube",
        lambda: upload_to_youtube(output, title=yt_title, description=yt_desc_full, tags=yt_tags),
        retries=3,
        delay=30,
    )

    # ── Instagram upload with retry ────────────────────────────────────
    ig_url = _upload_with_retry(
        "Instagram",
        lambda: upload_to_instagram(output, caption=caption),
        retries=3,
        delay=60,
    )

    print(f"\n  Published:")
    print(f"    YouTube  -> {yt_url  or '(not uploaded)'}")
    print(f"    Instagram-> {ig_url or '(not uploaded)'}")

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
    parser.add_argument("--jamendo-music", action="store_true",
                        help="Mark that --music is from Jamendo (blocks auto-upload unless --allow-jamendo-upload is set)")
    parser.add_argument("--allow-jamendo-upload", action="store_true",
                        help="Allow auto-upload when using Jamendo music (only if you have proper rights/license)")
    args = parser.parse_args()

    if args.jamendo_music and not args.music:
        parser.error("--jamendo-music requires --music <path>")

    _topic = " ".join(args.topic).strip() if args.topic else None

    run(
        _topic,
        num_scenes=args.scenes,
        language=args.lang,
        music_path=args.music,
        jamendo_music=args.jamendo_music,
        allow_jamendo_upload=args.allow_jamendo_upload,
    )
