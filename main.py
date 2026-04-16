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
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from config import GROQ_API_KEY, PEXELS_API_KEY, JAMENDO_CLIENT_ID, OUTPUT_DIR, TEMP_DIR
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

    data     = generate_quotes(topic, GROQ_API_KEY, num_scenes=num_scenes, language=language,
                               used_quotes=used_quotes)
    scenes   = data["scenes"]
    title    = data["title"]
    print(f"        Title  : {title}")
    print(f"        Scenes : {len(scenes)}")

    with open(os.path.join(TEMP_DIR, "quotes.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("        Generating video metadata (title / description / hashtags)...")
    meta = generate_video_metadata(topic, title, scenes, GROQ_API_KEY, language=language)
    yt_title   = meta["yt_title"]
    yt_desc    = meta["description"]
    yt_tags    = meta["tags"]
    hashtags   = " ".join(meta["hashtags"])
    print(f"        YT Title: {yt_title}")

    # ── Step 2 / 3 · Fetch real nature footage from Pexels ───────────
    print("\n[ 2/3 ] Fetching real nature footage (Pexels)...")
    video_paths = []
    this_run_video_ids = []
    for i, scene in enumerate(scenes):
        print(f"        Scene {i + 1}/{len(scenes)}...")
        vid_path = os.path.join(TEMP_DIR, f"scene_{i + 1:02d}.mp4")
        search   = scene.get("video_search", scene.get("location", "peaceful nature"))
        vid_path_result, vid_id = fetch_nature_video(
            search, PEXELS_API_KEY, vid_path,
            used_ids=used_video_ids | set(this_run_video_ids),  # avoid dups within a run too
        )
        video_paths.append(vid_path_result)
        if vid_id:
            this_run_video_ids.append(vid_id)
            used_video_ids.add(vid_id)   # prevent same ID later in same run
        print(f"        Scene {i + 1} done")

    # ── Step 3 / 3 · Fetch music, copyright-check, then build video ──────
    total_duration = SCENE_DURATION * len(scenes)

    user_provided_music = music_path is not None  # remember before the path may be overwritten

    # ── Copyright check: videos ───────────────────────────────────────
    print("\n[ Copyright ] Verifying downloaded video clips...")
    vid_ok, bad_indices = check_videos(video_paths)
    if not vid_ok:
        # Re-download only the failed scenes
        for i in bad_indices:
            scene  = scenes[i]
            search = scene.get("video_search", scene.get("location", "peaceful nature"))
            print(f"  Re-downloading scene {i+1} ({search!r})...")
            vid_path = os.path.join(TEMP_DIR, f"scene_{i + 1:02d}.mp4")
            new_path, vid_id = fetch_nature_video(
                search, PEXELS_API_KEY, vid_path,
                used_ids=used_video_ids,
            )
            video_paths[i] = new_path
            if vid_id:
                this_run_video_ids[i] = vid_id
                used_video_ids.add(vid_id)

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

    build_video(
        scenes         = scenes,
        video_paths    = video_paths,
        output_path    = output,
        music_path     = music_path,
        quote_data     = scenes,
        scene_duration = SCENE_DURATION,
    )

    _cleanup_temp()

    # ── Record what we used so future runs produce fresh content ─────────
    this_run_quotes = [s.get("quote", "") for s in scenes]
    record_run(
        quotes    = this_run_quotes,
        video_ids = this_run_video_ids,
        music_id  = music_id or None,
    )

    print(f"\n{'=' * 55}")
    print(f"  Done!")
    print(f"  Video    -> {output}")
    print(f"  Duration ~ {total_duration:.0f}s  ({total_duration / 60:.1f} min)")
    print(f"  Scenes   : {len(scenes)}")
    print(f"{'=' * 55}\n")

    # ── Optional: Upload to YouTube & Instagram ────────────────────────
    # Uploads are silently skipped if the required secrets are not set.

    # Determine whether Jamendo music is in use:
    #   - auto-fetched: music_track is non-empty (empty only on fallback ambient)
    #   - user-supplied + --jamendo-music flag: jamendo_music=True
    used_jamendo = bool(music_track) or jamendo_music

    # Warn when a custom music file is provided without any license declaration
    if user_provided_music and not jamendo_music:
        print("  [Copyright] Warning: custom music file provided without license info.")
        print("              Ensure you hold the necessary rights before uploading this video.")

    # Build copyright attribution block
    credits_lines = ["\n---\nCredits & Licenses:"]
    credits_lines.append("Video footage: Pexels (https://www.pexels.com/license/) — free to use, no attribution required.")
    if music_track and music_artist:
        credits_lines.append(f'Music: "{music_track}" by {music_artist} — CC Licensed via Jamendo.')
        if music_license:
            credits_lines.append(f"License: {music_license}")
    credits_block = "\n".join(credits_lines)

    yt_desc_full = f"{yt_desc}\n{credits_block}"
    # Include credits in Instagram caption as well
    caption = f"{yt_title}\n\n{yt_desc}\n\n{credits_block}\n\n{hashtags}"

    # Enforce Jamendo upload gate — require explicit consent before posting
    if used_jamendo and not allow_jamendo_upload:
        print("  [Copyright] Uploads skipped — Jamendo CC music detected.")
        print("              Re-run with --allow-jamendo-upload once you confirm compliance with the CC license terms.")
        return output

    print("[ Upload ] Posting to social media...")
    try:
        yt_url = upload_to_youtube(
            output,
            title=yt_title,
            description=yt_desc_full,
            tags=yt_tags,
        )
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
            print(f"    YouTube  -> {yt_url}")
        if ig_url:
            print(f"    Instagram-> {ig_url}")

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
