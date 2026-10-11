"""
Licensing and Asset Integrity Checker Module.

Validates that:
  - Background music tracks have verified status in the manifest.
  - Required attributions are formatted properly.
  - Visual stock footage and images from Pexels / Pixabay exist and are intact.

Note: Automated checks validate local metadata and file integrity;
they do not represent legal warranties of copyright clearance.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

from src.media_fetcher import RetrievedAsset
from src.music_manager import MusicTrack


@dataclass
class LicenseCheckResult:
    is_compliant: bool
    requires_attribution: bool
    attribution_text: str
    reasons: List[str]


def check_music_track_licensing(track: Optional[MusicTrack]) -> LicenseCheckResult:
    """
    Validate licensing terms and file status for selected music track.
    If no track is provided (no-music mode), returns compliant.
    """
    if track is None:
        return LicenseCheckResult(
            is_compliant=True,
            requires_attribution=False,
            attribution_text="",
            reasons=["No music track selected; speech-only delivery is compliant."],
        )

    reasons: List[str] = []

    if not track.verified:
        reasons.append(f"Track '{track.title}' is not marked as verified in the music manifest.")

    if not track.resolved_path or not os.path.exists(track.resolved_path):
        reasons.append(f"Track audio file missing on disk: {track.resolved_path}")
    elif os.path.getsize(track.resolved_path) < 2000:
        reasons.append(f"Track audio file is empty or corrupted: {track.resolved_path}")

    if track.attribution_required and not track.attribution_text:
        reasons.append(f"Track '{track.title}' requires attribution but attribution_text is blank.")

    is_compliant = len(reasons) == 0
    return LicenseCheckResult(
        is_compliant=is_compliant,
        requires_attribution=track.attribution_required,
        attribution_text=track.attribution_text if track.attribution_required else "",
        reasons=reasons,
    )


def check_visual_assets_integrity(assets: List[RetrievedAsset]) -> Tuple[bool, List[str]]:
    """
    Validate that all scene visual assets exist on disk and meet minimum file sizes.
    Returns (all_ok, failed_descriptions).
    """
    failed: List[str] = []
    for idx, asset in enumerate(assets, start=1):
        if not asset.path or not os.path.exists(asset.path):
            failed.append(f"Scene {idx}: missing media file ({asset.path})")
        elif os.path.getsize(asset.path) < 5000:
            failed.append(f"Scene {idx}: media file too small ({asset.path})")

    return len(failed) == 0, failed
