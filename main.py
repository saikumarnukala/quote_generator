"""
Infotainment Video Automation System — Main Orchestrator.

Transforms researched educational topics into engaging, verified,
9:16 vertical infotainment videos for YouTube Shorts.

Pipeline Flow:
  Topic Selection
    ↓
  Factual Research & Source Collection
    ↓
  Groq Script Generation & Schema Validation
    ↓
  Deepgram Aura Voiceover Generation & Timing
    ↓
  Synchronized Subtitle Generation
    ↓
  Multi-Tier Media Retrieval (Pexels / Pixabay / Graphics)
    ↓
  Curated Music Selection (YouTube Audio Library)
    ↓
  FFmpeg Video Assembly & Burn-In Subtitles
    ↓
  FFprobe Quality Validation
    ↓
  Thumbnail & Metadata Generation
    ↓
  Persistent History Recording
    ↓
  Optional YouTube Upload (Disabled by default)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import (
    DEEPGRAM_API_KEY,
    DEEPGRAM_VOICE,
    GROQ_API_KEY,
    OUTPUT_DIR,
    PEXELS_API_KEY,
    PIXABAY_API_KEY,
    TEMP_DIR,
    YOUTUBE_PRIVACY_STATUS,
    YOUTUBE_UPLOAD_ENABLED,
    INSTAGRAM_UPLOAD_ENABLED,
)
from src.audio_generator import generate_audio, get_audio_duration
from src.copyright_checker import check_music_track_licensing, check_visual_assets_integrity
from src.instagram_uploader import upload_to_instagram
from src.history import (
    get_used_asset_ids,
    get_used_music_tracks,
    get_used_topics,
    is_topic_already_used,
    record_infotainment_run,
)
from src.media_fetcher import RetrievedAsset, retrieve_scene_media
from src.metadata_generator import generate_infotainment_metadata
from src.music_manager import MusicTrack, select_background_track
from src.researcher import ResearchDossier, research_topic
from src.script_generator import InfotainmentScript, generate_infotainment_script
from src.subtitle_generator import generate_ass, generate_srt
from src.thumbnail_generator import generate_infotainment_thumbnail
from src.topic_manager import get_categories, select_topic
from src.video_builder import build_infotainment_video
from src.video_validator import ValidationReport, validate_mp4_video
from src.youtube_uploader import upload_to_youtube


def _safe_filename(text: str) -> str:
    """Generate a clean, cross-platform filesystem-safe filename."""
    cleaned = "".join(c if (c.isalnum() or c in " _-") else "" for c in text)
    return cleaned.strip().replace(" ", "_")[:50]


def run_pipeline(
    topic: Optional[str] = None,
    category: Optional[str] = None,
    num_scenes: int = 4,
    target_duration: float = 45.0,
    voice: Optional[str] = None,
    music_path: Optional[str] = None,
    no_music: bool = False,
    music_volume: float = 0.16,
    dry_run: bool = False,
    upload: bool = False,
    upload_instagram: bool = False,
    privacy: Optional[str] = None,
    output_custom: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute the full end-to-end infotainment video creation pipeline."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)

    print("\n" + "=" * 65)
    print("  INFOTAINMENT VIDEO AUTOMATION SYSTEM")
    print("=" * 65)

    # ── 1. Topic Selection ──────────────────────────────────────────────
    past_topics = get_used_topics()
    chosen_topic, chosen_category = select_topic(
        category=category,
        manual_topic=topic,
        past_topics=past_topics,
    )

    if is_topic_already_used(chosen_topic):
        print(f"  [Notice] Topic '{chosen_topic}' is similar to a recently covered topic.")

    print(f"  Category : {chosen_category.upper()}")
    print(f"  Topic    : {chosen_topic}")
    print(f"  Scenes   : {num_scenes}")

    # ── 2. Research & Source Collection ─────────────────────────────────
    print("\n[ 1/8 ] Researching topic and retrieving reliable sources...")
    dossier: ResearchDossier = research_topic(chosen_topic, category=chosen_category)
    print(f"        Primary Source : {dossier.primary_source_title}")
    print(f"        Source URL     : {dossier.primary_source_url}")
    print(f"        Extracted Facts: {len(dossier.key_facts)} verified claims")

    # ── 3. Script Generation & Schema Validation ────────────────────────
    print("\n[ 2/8 ] Generating and validating structured infotainment script...")
    script: InfotainmentScript = generate_infotainment_script(
        topic=chosen_topic,
        category=chosen_category,
        dossier=dossier,
        groq_api_key=GROQ_API_KEY,
        num_scenes=num_scenes,
        target_duration=target_duration,
    )
    print(f"        Title    : {script.title}")
    print(f"        Hook     : {script.hook}")
    print(f"        Scenes   : {len(script.scenes)} planned scenes")

    # ── 4. Voiceover Generation (Deepgram Aura) ─────────────────────────
    print("\n[ 3/8 ] Generating voiceover narration (Deepgram Aura)...")
    chosen_voice = voice or DEEPGRAM_VOICE or "aura-asteria-en"
    print(f"        Voice: {chosen_voice}")

    audio_paths: List[str] = []
    durations: List[float] = []

    for sc in script.scenes:
        audio_dest = os.path.join(TEMP_DIR, f"scene_{sc.scene_number:02d}_speech.mp3")
        try:
            generate_audio(
                text=sc.narration,
                output_path=audio_dest,
                voice=chosen_voice,
                api_key=DEEPGRAM_API_KEY,
            )
            dur = get_audio_duration(audio_dest)
            # Add small 0.3s visual pacing buffer per scene
            pacing_dur = max(dur + 0.3, 3.0)
            audio_paths.append(audio_dest)
            durations.append(pacing_dur)
            print(f"        Scene {sc.scene_number:02d}: {dur:.2f}s speech ('{sc.narration[:35]}...')")
        except Exception as e:
            print(f"        Audio error for scene {sc.scene_number}: {e}")
            raise

    total_spoken_duration = sum(durations)
    print(f"        Total Duration: {total_spoken_duration:.1f}s")

    # ── 5. Subtitle Generation ──────────────────────────────────────────
    print("\n[ 4/8 ] Generating synchronized ASS & SRT subtitles...")
    sub_srt_path = os.path.join(TEMP_DIR, "subtitles.srt")
    sub_ass_path = os.path.join(TEMP_DIR, "subtitles.ass")

    scene_narrations = [sc.narration for sc in script.scenes]
    generate_srt(scene_narrations, durations, sub_srt_path)
    generate_ass(scene_narrations, durations, sub_ass_path)
    print(f"        Generated ASS subtitles with safe margins -> {sub_ass_path}")

    # ── 6. Visual Media Retrieval ───────────────────────────────────────
    print("\n[ 5/8 ] Retrieving visual media assets (Pexels / Pixabay / Graphics)...")
    used_asset_ids = get_used_asset_ids()
    retrieved_assets: List[RetrievedAsset] = []
    scene_video_paths: List[str] = []

    for sc, sc_dur in zip(script.scenes, durations):
        print(f"      Scene {sc.scene_number}/{len(script.scenes)}: '{sc.main_subject}' ({sc_dur:.1f}s)")
        scene_clip_dest = os.path.join(TEMP_DIR, f"scene_{sc.scene_number:02d}_conformed.mp4")

        asset = retrieve_scene_media(
            scene_number=sc.scene_number,
            video_queries=sc.video_search_queries,
            image_queries=sc.image_search_queries,
            main_subject=sc.main_subject,
            target_duration=sc_dur,
            output_video_path=scene_clip_dest,
            used_ids=used_asset_ids,
            pexels_key=PEXELS_API_KEY,
            pixabay_key=PIXABAY_API_KEY,
        )
        retrieved_assets.append(asset)
        scene_video_paths.append(asset.path)
        used_asset_ids.add(str(asset.asset_id))

    assets_ok, bad_assets = check_visual_assets_integrity(retrieved_assets)
    if not assets_ok:
        print(f"  [Warning] Media check warnings: {bad_assets}")

    # ── 7. Background Music Selection ───────────────────────────────────
    print("\n[ 6/8 ] Selecting curated background music...")
    selected_track: Optional[MusicTrack] = None

    if no_music:
        print("        --no-music requested: rendering with narration only.")
    elif music_path and os.path.exists(music_path):
        print(f"        Using user-specified background music: {music_path}")
        selected_track = MusicTrack(
            filename=os.path.basename(music_path),
            title="User Background Track",
            artist="Custom",
            resolved_path=os.path.abspath(music_path),
            verified=True,
        )
    else:
        used_music = get_used_music_tracks()
        selected_track = select_background_track(
            category=chosen_category,
            used_track_names=used_music,
        )

    lic_check = check_music_track_licensing(selected_track)
    if not lic_check.is_compliant:
        print(f"  [Warning] Music track license check failed: {lic_check.reasons}. Omitting music.")
        selected_track = None

    final_music_path = selected_track.resolved_path if selected_track else None

    # ── 8. Video Assembly (FFmpeg) ──────────────────────────────────────
    print("\n[ 7/8 ] Rendering final 1080x1920 MP4 video...")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_topic = _safe_filename(chosen_topic)

    final_output_path = output_custom or os.path.join(OUTPUT_DIR, f"{safe_topic}_{ts}.mp4")

    build_infotainment_video(
        scene_video_paths=scene_video_paths,
        scene_audio_paths=audio_paths,
        scene_durations=durations,
        output_path=final_output_path,
        subtitle_ass_path=sub_ass_path,
        music_path=final_music_path,
        music_volume=music_volume,
    )

    # ── 9. Video Quality & Integrity Validation ─────────────────────────
    print("\n[ 8/8 ] Validating output MP4 with FFprobe...")
    report: ValidationReport = validate_mp4_video(final_output_path)
    if not report.is_valid:
        print(f"  [Error] Video validation errors: {report.errors}")
        raise RuntimeError(f"Rendered video failed validation: {report.errors}")

    print(f"        Validated: {report.width}x{report.height} @ {report.fps}fps")
    print(f"        Video Codec: {report.video_codec} | Audio: {report.audio_codec} ({report.audio_channels}ch)")
    print(f"        Duration   : {report.duration_seconds}s | Size: {report.file_size_bytes / (1024*1024):.2f} MB")

    # ── 10. Thumbnail & YouTube Metadata ────────────────────────────────
    thumb_path = os.path.splitext(final_output_path)[0] + "_thumb.jpg"
    hero_input = scene_video_paths[0] if scene_video_paths else None
    generate_infotainment_thumbnail(
        title=script.title,
        category=chosen_category,
        output_path=thumb_path,
        hero_video_or_image=hero_input,
    )

    meta = generate_infotainment_metadata(script, dossier, selected_track)
    meta_path = os.path.splitext(final_output_path)[0] + "_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"  [Metadata] Saved YouTube metadata -> {meta_path}")

    # ── 11. Optional YouTube & Instagram Uploads ────────────────────────
    yt_url, yt_id = None, None
    ig_url = None
    upload_status = "local_only"

    # YouTube upload
    if upload or YOUTUBE_UPLOAD_ENABLED or dry_run:
        print("\n[ Upload ] Processing YouTube upload...")
        yt_url, yt_id = upload_to_youtube(
            video_path=final_output_path,
            title=meta["title"],
            description=meta["description"],
            tags=meta["tags"],
            privacy_status=privacy or YOUTUBE_PRIVACY_STATUS,
            dry_run=dry_run,
            force_upload=upload,
        )
        if yt_url:
            upload_status = "uploaded"
            print(f"        YouTube URL: {yt_url}")
        else:
            upload_status = "skipped"

    # Instagram upload
    if upload_instagram or INSTAGRAM_UPLOAD_ENABLED or dry_run:
        print("\n[ Upload ] Processing Instagram Reels upload...")
        ig_caption = f"{meta['title']}\n\n{meta['description'][:500]}\n\n{' '.join(meta['hashtags'])}"
        ig_url = upload_to_instagram(
            video_path=final_output_path,
            caption=ig_caption,
            dry_run=dry_run,
            force_upload=upload_instagram or INSTAGRAM_UPLOAD_ENABLED,
        )
        if ig_url:
            print(f"        Instagram URL: {ig_url}")

    # ── 12. Record Run History ──────────────────────────────────────────
    record_infotainment_run(
        topic=chosen_topic,
        category=chosen_category,
        title=script.title,
        script_summary=script.hook,
        sources=[{"title": s.title, "url": s.url} for s in dossier.sources],
        visual_asset_ids=[a.asset_id for a in retrieved_assets],
        music_track_title=selected_track.title if selected_track else None,
        output_video_path=final_output_path,
        video_duration=report.duration_seconds,
        youtube_video_id=yt_id,
        upload_status=upload_status,
    )

    print("\n" + "=" * 65)
    print("  INFOTAINMENT VIDEO COMPLETE!")
    print(f"  Video     : {final_output_path}")
    print(f"  Thumbnail : {thumb_path}")
    print(f"  Metadata  : {meta_path}")
    print(f"  Duration  : {report.duration_seconds:.1f}s")
    if yt_url:
        print(f"  YouTube   : {yt_url}")
    if ig_url:
        print(f"  Instagram : {ig_url}")
    print("=" * 65 + "\n")

    return {
        "video_path": final_output_path,
        "thumbnail_path": thumb_path,
        "metadata_path": meta_path,
        "report": report.to_dict(),
        "topic": chosen_topic,
        "category": chosen_category,
        "youtube_url": yt_url,
        "instagram_url": ig_url,
    }


def main():
    parser = argparse.ArgumentParser(description="Infotainment Video Automation System")
    parser.add_argument("topic", nargs="*", default=None, help="Specific topic (leave empty for auto)")
    parser.add_argument("--category", choices=get_categories(), default=None, help="Infotainment category")
    parser.add_argument("--scenes", type=int, default=4, help="Number of scenes (default: 4)")
    parser.add_argument("--duration", type=float, default=45.0, help="Target duration in seconds")
    parser.add_argument("--voice", default=None, help="Deepgram Aura voice (default: aura-asteria-en)")
    parser.add_argument("--music", default=None, help="Path to custom music audio file")
    parser.add_argument("--no-music", action="store_true", help="Render video with voiceover only and no music")
    parser.add_argument("--music-volume", type=float, default=0.16, help="Background music mix volume (0.05 - 0.40)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate upload and external actions without quota use")
    parser.add_argument("--upload", action="store_true", help="Explicitly enable YouTube upload (disabled by default)")
    parser.add_argument("--upload-instagram", action="store_true", help="Explicitly enable Instagram Reels upload (disabled by default)")
    parser.add_argument("--upload-all", action="store_true", help="Enable upload to both YouTube and Instagram")
    parser.add_argument("--privacy", choices=["private", "unlisted", "public"], default=None, help="YouTube upload privacy")
    parser.add_argument("--output", default=None, help="Custom output video path")

    args = parser.parse_args()

    topic_str = " ".join(args.topic).strip() if args.topic else None
    upload_yt = args.upload or args.upload_all
    upload_ig = args.upload_instagram or args.upload_all

    try:
        run_pipeline(
            topic=topic_str,
            category=args.category,
            num_scenes=args.scenes,
            target_duration=args.duration,
            voice=args.voice,
            music_path=args.music,
            no_music=args.no_music,
            music_volume=args.music_volume,
            dry_run=args.dry_run,
            upload=upload_yt,
            upload_instagram=upload_ig,
            privacy=args.privacy,
            output_custom=args.output,
        )
    except Exception as e:
        print(f"\n[FATAL ERROR] Pipeline terminated with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
