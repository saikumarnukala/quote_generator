"""
YouTube Metadata Generation Module.

Generates YouTube titles, descriptions, tags, and hashtags
with verifiable source citations and required music attributions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.music_manager import MusicTrack
from src.researcher import ResearchDossier
from src.script_generator import InfotainmentScript


def generate_infotainment_metadata(
    script: InfotainmentScript,
    dossier: ResearchDossier,
    music_track: Optional[MusicTrack] = None,
) -> Dict[str, Any]:
    """
    Generate complete YouTube metadata for the video.
    """
    clean_title = script.title.strip()
    if "#Shorts" not in clean_title and len(clean_title) <= 90:
        yt_title = f"{clean_title} #Shorts"[:100]
    else:
        yt_title = clean_title[:100]

    desc_paragraphs = [
        f"Discover the fascinating science and story behind {script.title}.",
        f"Summary: {dossier.summary[:400]}...",
        "---",
        "Key Facts & Sources:",
    ]

    for s in dossier.sources:
        desc_paragraphs.append(f"• {s.title}: {s.url}")

    if music_track:
        desc_paragraphs.append("---")
        desc_paragraphs.append(f"Music: \"{music_track.title}\" by {music_track.artist} ({music_track.source})")
        desc_paragraphs.append(f"License: {music_track.license}")
        if music_track.attribution_required and music_track.attribution_text:
            desc_paragraphs.append(f"Attribution: {music_track.attribution_text}")

    # Standard clean hashtags
    category_slug = script.category.replace("_", "").lower()
    hashtags = [
        "#Shorts",
        "#Science",
        "#Education",
        "#DidYouKnow",
        f"#{category_slug.capitalize()}",
        "#Facts",
    ]

    desc_paragraphs.append("")
    desc_paragraphs.append(" ".join(hashtags))

    full_description = "\n".join(desc_paragraphs)

    # Plain text tags for YouTube SEO
    tags = [
        "shorts",
        "science",
        "facts",
        "educational",
        "did you know",
        script.category.replace("_", " "),
        script.title.lower(),
        "learn",
        "documentary",
    ]

    return {
        "title": yt_title,
        "description": full_description,
        "tags": tags[:20],
        "hashtags": hashtags,
    }
