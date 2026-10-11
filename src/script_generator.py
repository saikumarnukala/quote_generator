"""
Script Generation and Validation Module.

Generates structured infotainment scripts using Groq (Llama 3.3 / Llama 3.1)
with strict JSON schema validation, duration estimation, and source-grounded fallback.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from groq import Groq

from src.researcher import ResearchDossier

# Current active production models on Groq
GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

# Average spoken English rate: ~2.5 words per second (150 words per minute)
WORDS_PER_SECOND = 2.4


@dataclass
class SceneData:
    scene_number: int
    narration: str
    duration_est: float
    main_subject: str
    visual_type: str = "video"  # "video" or "image"
    video_search_queries: List[str] = field(default_factory=list)
    image_search_queries: List[str] = field(default_factory=list)
    onscreen_text: str = ""
    source_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InfotainmentScript:
    title: str
    category: str
    hook: str
    target_duration: float
    scenes: List[SceneData] = field(default_factory=list)
    sources: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["scenes"] = [s.to_dict() for s in self.scenes]
        return data

    @property
    def total_words(self) -> int:
        return sum(len(s.narration.split()) for s in self.scenes)

    @property
    def calculated_duration(self) -> float:
        return max(round(self.total_words / WORDS_PER_SECOND, 1), 15.0)


def estimate_narration_duration(text: str) -> float:
    """Estimate spoken duration in seconds based on word count."""
    words = len(text.strip().split())
    # Minimum 3.5s per scene for visual breathing room
    return max(round(words / WORDS_PER_SECOND, 1), 3.5)


def validate_script_dict(data: Dict[str, Any]) -> bool:
    """Validate that parsed dictionary complies with infotainment script schema."""
    if not isinstance(data, dict):
        return False
    if not data.get("title") or not isinstance(data.get("title"), str):
        return False
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or len(scenes) < 3:
        return False

    for i, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            return False
        if not sc.get("narration") or not isinstance(sc.get("narration"), str):
            return False
        if not sc["narration"].strip():
            return False
        # Must have at least one search query
        v_queries = sc.get("video_search_queries") or []
        img_queries = sc.get("image_search_queries") or []
        if not v_queries and not img_queries:
            return False
    return True


def normalize_script_data(
    data: Dict[str, Any], topic: str, category: str, dossier: ResearchDossier
) -> InfotainmentScript:
    """Normalize raw dictionary into a validated InfotainmentScript dataclass."""
    raw_scenes = data.get("scenes", [])
    normalized_scenes: List[SceneData] = []

    for idx, sc in enumerate(raw_scenes, start=1):
        narr = sc.get("narration", "").strip()
        dur = sc.get("duration_est")
        if not dur or not isinstance(dur, (int, float)):
            dur = estimate_narration_duration(narr)

        v_queries = sc.get("video_search_queries")
        if isinstance(v_queries, str):
            v_queries = [v_queries]
        elif not isinstance(v_queries, list):
            v_queries = []

        img_queries = sc.get("image_search_queries")
        if isinstance(img_queries, str):
            img_queries = [img_queries]
        elif not isinstance(img_queries, list):
            img_queries = []

        # If queries are empty, populate intelligent subject queries
        subj = sc.get("main_subject", topic).strip() or topic
        if not v_queries:
            v_queries = [f"{subj} science 4k", f"{topic} footage"]
        if not img_queries:
            img_queries = [f"{subj} high resolution", f"{topic} close up"]

        ost = sc.get("onscreen_text", "").strip()
        if not ost:
            words = narr.split()
            ost = " ".join(words[:4]).upper() if words else subj.upper()

        refs = sc.get("source_refs") or [dossier.primary_source_title]
        if isinstance(refs, str):
            refs = [refs]

        scene_obj = SceneData(
            scene_number=idx,
            narration=narr,
            duration_est=float(dur),
            main_subject=subj,
            visual_type=sc.get("visual_type", "video"),
            video_search_queries=[q.strip() for q in v_queries if q.strip()],
            image_search_queries=[q.strip() for q in img_queries if q.strip()],
            onscreen_text=ost,
            source_refs=refs,
        )
        normalized_scenes.append(scene_obj)

    title = data.get("title", f"The Science of {topic}").strip()
    hook = data.get("hook", normalized_scenes[0].narration).strip()

    sources_list = [
        {"title": s.title, "url": s.url}
        for s in dossier.sources
    ]

    script = InfotainmentScript(
        title=title,
        category=category,
        hook=hook,
        target_duration=sum(s.duration_est for s in normalized_scenes),
        scenes=normalized_scenes,
        sources=sources_list,
    )
    return script


def build_fallback_script(
    topic: str, category: str, dossier: ResearchDossier, num_scenes: int = 4
) -> InfotainmentScript:
    """
    Construct a verified, factual infotainment script directly from ResearchDossier.
    Used when Groq API is offline, credentials are not set, or rate limits occur.
    """
    facts = dossier.key_facts or [dossier.summary]
    if len(facts) < num_scenes:
        # Split summary into sentences if facts list is short
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", dossier.summary) if len(s.strip()) > 20]
        facts = (facts + sentences + [f"This reveals the incredible reality of {topic}."])[:num_scenes]

    scenes: List[SceneData] = []
    # Scene 1: Hook
    hook_text = f"Have you ever wondered what makes {topic} so extraordinary? Let's break down the facts."
    scenes.append(
        SceneData(
            scene_number=1,
            narration=hook_text,
            duration_est=estimate_narration_duration(hook_text),
            main_subject=f"{topic} overview",
            visual_type="video",
            video_search_queries=[f"{topic} cinematic", f"{category} technology aerial"],
            image_search_queries=[f"{topic} discovery", f"{category} scientific"],
            onscreen_text=f"THE TRUTH ABOUT {topic.upper()[:25]}",
            source_refs=[dossier.primary_source_title],
        )
    )

    # Core scenes from facts
    for idx in range(1, num_scenes - 1):
        fact = facts[min(idx - 1, len(facts) - 1)]
        scene_narr = f"First discovered through rigorous research: {fact}" if idx == 1 else f"Furthermore: {fact}"
        scenes.append(
            SceneData(
                scene_number=idx + 1,
                narration=scene_narr,
                duration_est=estimate_narration_duration(scene_narr),
                main_subject=f"{topic} detailed study",
                visual_type="video",
                video_search_queries=[f"{topic} laboratory research", f"{category} macro science"],
                image_search_queries=[f"{topic} diagram", f"{topic} close up"],
                onscreen_text=f"KEY FACT #{idx}",
                source_refs=[dossier.primary_source_title],
            )
        )

    # Final scene: Conclusion / Takeaway
    final_narr = (
        f"Understanding {topic} changes how we see {category}. "
        "Science continues to uncover new secrets every day."
    )
    scenes.append(
        SceneData(
            scene_number=num_scenes,
            narration=final_narr,
            duration_est=estimate_narration_duration(final_narr),
            main_subject=f"{topic} conclusion",
            visual_type="video",
            video_search_queries=[f"{category} future tech cinematic", "earth space horizon 4k"],
            image_search_queries=[f"{topic} modern", f"{category} innovation"],
            onscreen_text="THE TAKEAWAY",
            source_refs=[dossier.primary_source_title],
        )
    )

    title = f"The Shocking Truth About {topic}"[:80]
    return InfotainmentScript(
        title=title,
        category=category,
        hook=hook_text,
        target_duration=sum(s.duration_est for s in scenes),
        scenes=scenes,
        sources=[{"title": s.title, "url": s.url} for s in dossier.sources],
    )


def generate_infotainment_script(
    topic: str,
    category: str,
    dossier: ResearchDossier,
    groq_api_key: str,
    num_scenes: int = 4,
    target_duration: float = 45.0,
) -> InfotainmentScript:
    """
    Generate an engaging, factual infotainment video script using Groq.
    Validates output structure and falls back to researched factual script on failure.
    """
    if not groq_api_key or not groq_api_key.startswith("gsk_"):
        print("  [Script] Valid GROQ_API_KEY not configured — using research-grounded fallback generator.")
        return build_fallback_script(topic, category, dossier, num_scenes=num_scenes)

    facts_text = "\n".join(f"- {f}" for f in dossier.key_facts[:6])

    prompt = f"""You are an elite science documentary writer and video producer creating an engaging 30-60s English infotainment short.

TOPIC: {topic}
CATEGORY: {category}
VERIFIED FACTS FROM RESEARCH:
{facts_text}
PRIMARY SOURCE: {dossier.primary_source_title} ({dossier.primary_source_url})

CRITICAL GUIDELINES:
1. Every claim MUST be factually true and supported by the verified facts above. Do NOT invent fake stats, fictitious quotes, or pseudo-science.
2. Structure:
   - Scene 1 MUST be a high-energy HOOK that asks a compelling question or presents a mind-blowing fact.
   - Middle scenes explain the underlying science/mechanism step-by-step with clear, accessible logic.
   - Final scene delivers a punchy takeaway or perspective shift.
3. Total scenes: Exactly {num_scenes}.
4. Duration: Target total duration is {target_duration:.0f} seconds (~10-12s per scene). Spoken narration must be 20-30 words per scene.
5. Search queries: Provide 2-3 specific English stock video queries per scene that match what is being described. Avoid generic terms like "nature" or "cool background".

Return ONLY valid JSON matching this exact structure:
{{
  "title": "A high-CTR, curiosity-driven YouTube Shorts title (max 80 chars)",
  "hook": "The opening hook sentence",
  "scenes": [
    {{
      "scene_number": 1,
      "narration": "Spoken English narration for this scene (20-30 words). Conversational, clear, factual.",
      "duration_est": 10.0,
      "main_subject": "Visual subject description",
      "visual_type": "video",
      "video_search_queries": ["query 1", "query 2"],
      "image_search_queries": ["image query 1"],
      "onscreen_text": "PUNCHY 3-5 WORD CAPTION",
      "source_refs": ["{dossier.primary_source_title}"]
    }}
  ]
}}"""

    client = Groq(api_key=groq_api_key)
    parsed_data = None
    last_error = None

    for model_name in GROQ_MODELS:
        try:
            print(f"  [Script] Generating script with Groq ({model_name})...")
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a factual infotainment scriptwriter. Output strictly valid JSON without markdown wrapping.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=1800,
            )
            raw_content = completion.choices[0].message.content.strip()
            data = json.loads(raw_content)
            if validate_script_dict(data):
                parsed_data = data
                print(f"  [Script] Successfully generated and validated script via {model_name}.")
                break
            else:
                print(f"  [Script] Model {model_name} response failed schema validation.")
        except Exception as err:
            last_error = err
            print(f"  [Script] Model {model_name} error: {err}")

    if parsed_data:
        return normalize_script_data(parsed_data, topic, category, dossier)

    print(f"  [Script] Groq generation unavailable ({last_error}) — generating grounded factual script.")
    return build_fallback_script(topic, category, dossier, num_scenes=num_scenes)
