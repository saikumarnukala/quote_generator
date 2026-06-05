"""
Generate peaceful location scenes paired with inspirational quotes using Groq API.
Each scene has a landscape image prompt, a quote, and a soft narration.
"""

import json
import re

from groq import Groq

LANGUAGE_NAMES = {
    "en": "English",
    "te": "Telugu",
    "hi": "Hindi",
    "ta": "Tamil",
    "ja": "Japanese",
}


def generate_quotes(topic: str, api_key: str, num_scenes: int = 7, language: str = "en",
                    used_quotes: list[str] | None = None) -> dict:
    """
    Generate peaceful location scenes + inspirational quotes via Groq Llama 3.3 70B.

    Returns a dict with the same structure as generate_story() so the
    existing image / audio / video pipeline works without changes:
        {
          "title": str,
          "theme": str,
          "scenes": [
            {
              "location":     str,   # location name (display only)
              "video_search": str,   # English keywords for Pexels video search
              "quote":        str,   # the inspirational quote
              "author":       str,   # attribution
              "narration":    str,   # text for soft narration
            }, ...
          ]
        }
    """
    client = Groq(api_key=api_key)
    lang_name = LANGUAGE_NAMES.get(language, "English")

    # Build forbidden-quotes block so the LLM never repeats them
    forbidden_block = ""
    if used_quotes:
        # Send the most recent 80 to keep the prompt manageable
        recent = used_quotes[-80:]
        forbidden_list = "\n".join(f'  - "{q}"' for q in recent)
        forbidden_block = (
            f"\n\nFORBIDDEN — do NOT use these quotes (already used in previous videos):\n"
            f"{forbidden_list}\n"
            f"Every quote MUST be completely different from the above list.\n"
        )

    prompt = f"""You are a world-class screenwriter creating a short cinematic meditation film about: "{topic}"
{forbidden_block}
Generate exactly {num_scenes} visually stunning scenes. Return ONLY valid JSON — no markdown, no extra text.

{{
  "title": "a curiosity-driven, search-friendly YouTube title in {lang_name} — max 70 chars, use an emotional hook, question, or power number (e.g. '7 Words That Will Change How You See Life' or 'Why Silence Is the Greatest Gift You Can Give Yourself')",
  "theme": "{topic}",
  "scenes": [
    {{
      "location": "short beautiful location name in {lang_name}",
      "video_searches": ["Array of 3 distinct hyper-specific English search queries for Pexels. They MUST be dark, moody, cinematic aesthetics (e.g. 'rain against window dark')"],
      "quote": "a deeply moving, soul-stirring quote in {lang_name}",
      "author": "ONLY public-domain authors (died before 1928) such as Rumi, Lao Tzu, Marcus Aurelius, Khalil Gibran, Rabindranath Tagore, Walt Whitman, Nikola Tesla, Abraham Lincoln, Epictetus, Seneca — OR use 'Ancient Wisdom' / 'Unknown'. NEVER use living authors or anyone who died after 1927.",
      "narration": "2-3 sentences in {lang_name} — poetic, intimate, like a whisper to the soul"
    }}
  ]
}}

Rules:
- THE FIRST SCENE MUST BE A HOOK: The `quote` and `narration` for the very first scene MUST be an attention-grabbing hook targeting a specific emotional pain point (e.g. "Listen to this if you are struggling to move on from a breakup" or "3 ancient quotes you need to hear if you feel completely lost in life"). Do NOT use a regular quote for the first scene.
- video_searches MUST always be an array of 3 distinct, ultra-specific English queries per scene. They MUST follow a DARK CORE, MOODY AESTHETIC.
  GOOD: "rain against glass window night", "dark foggy forest drone", "lonely street light rain", "stormy ocean waves slow motion", "driving at night blurry lights"
  BAD: "nature", "sunny mountains", "bright flowers", "peaceful daylight"
- All other fields (title, location, quote, author, narration) MUST be in {lang_name}
- Quotes: Mix these styles across scenes:
  * Profound philosophical wisdom (Rumi, Lao Tzu, Marcus Aurelius, Seneca, Epictetus)
  * Raw emotional truth that hits the heart
  * Poetic metaphors about life, nature, and the human spirit
  * Short powerful one-liners that linger in the mind
- NO generic motivational clichés — every quote must feel like it was written by a poet
- CRITICAL copyright rule: author field must ONLY be a person who died before 1928 (public domain),
  or the literal string 'Ancient Wisdom' or 'Unknown'. NEVER attribute quotes to Maya Angelou,
  Paulo Coelho, Eckhart Tolle, Brené Brown, or any other living or recently deceased author.
- video_searches: Use DARK CINEMATIC search terms — rain, night, fog, storm, dark ocean, solitary environments.
  Vary across: stormy oceans, dark rainy streets, foggy pine forests, moonlight on water, lonely roads at night.
- Each scene should feel emotionally heavy but ultimately comforting.
- narration: intimate and poetic — as if speaking directly to one person's soul, not a crowd"""

    model_candidates = [
        "llama-3.3-70b-versatile",
        "llama-3.3-70b-specdec",
        "llama-3.1-70b-versatile",
        "llama-3.1-8b-instant",
    ]
    last_err = None
    for model in model_candidates:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.85,
                max_tokens=4000,
            )
            break
        except Exception as e:
            last_err = e
            print(f"  Quote generation model {model} failed: {e}")
            continue
    else:
        raise RuntimeError(f"All Groq models failed. Last error: {last_err}")

    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if present
    raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\n?```$", "", raw, flags=re.MULTILINE)

    # Extract outermost JSON object
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        raw = match.group(0)

    return json.loads(raw)


def generate_video_metadata(
    topic: str,
    video_title: str,
    scenes: list,
    api_key: str,
    language: str = "en",
) -> dict:
    """
    Generate a catchy YouTube title, SEO-rich description, and targeted
    hashtags for the video using Groq.

    Returns:
        {
          "yt_title":    str,   # punchy YouTube title (≤90 chars, includes #Shorts)
          "description": str,   # multi-paragraph YouTube description
          "hashtags":    list,  # list of 25–30 hashtag strings (with #)
          "tags":        list,  # plain tag words for YouTube API
        }
    """
    client = Groq(api_key=api_key)

    # Build a brief summary of the quotes for context
    quote_lines = "\n".join(
        f'- "{s.get("quote", "")}" — {s.get("author", "")}'
        for s in scenes[:5]
    )

    prompt = f"""You are a YouTube SEO expert and content strategist specialising in
peaceful, motivational and mindfulness content. Create metadata for this video:

Topic: {topic}
Video title from AI: {video_title}
Sample quotes:
{quote_lines}

Return ONLY valid JSON — no markdown, no extra text:
{{
  "yt_title": "A punchy YouTube title under 90 characters. Must include #Shorts. Make it emotionally compelling and searchable.",
  "description": "A 3-paragraph YouTube video description. Paragraph 1: Hook — 1-2 compelling sentences about the video theme. Paragraph 2: What viewers will feel/gain. Paragraph 3: Call to action — ask viewers to subscribe to @silent_mind_talks, like, and comment their favourite quote. End with the full hashtag block on its own line.",
  "hashtags": ["list", "of", "25", "to", "30", "hashtags", "each", "with", "#", "include", "niche", "and", "broad", "tags"],
  "tags": ["plain", "tag", "words", "for", "YouTube", "API", "15", "to", "20", "items"]
}}

Rules:
- yt_title: emotional, short, has #Shorts, no clickbait, max 90 chars
- description: warm tone, 3 clear paragraphs, ends with hashtags block
- hashtags: mix of broad (#meditation #quotes #shorts) and niche (#innerpeace #calmvibes) — 25–30 items
- tags: plain English phrases, no #, 15–20 items, great for YouTube SEO"""

    model_candidates = [
        "llama-3.3-70b-versatile",
        "llama-3.3-70b-specdec",
        "llama-3.1-70b-versatile",
        "llama-3.1-8b-instant",
    ]
    last_err = None
    for model in model_candidates:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1500,
            )
            break
        except Exception as e:
            last_err = e
            print(f"  Metadata generation model {model} failed: {e}")
            continue
    else:
        raise RuntimeError(f"All Groq models failed. Last error: {last_err}")

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\n?```$", "", raw, flags=re.MULTILINE)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        raw = match.group(0)

    try:
        meta = json.loads(raw)
    except Exception:
        # Fallback to safe defaults if parsing fails
        meta = {}

    # Ensure all keys exist with safe fallbacks
    if not meta.get("yt_title"):
        meta["yt_title"] = f"{video_title} #Shorts"[:90]

    if not meta.get("description"):
        meta["description"] = (
            f"{topic.capitalize()} — a peaceful video to calm your mind and uplift your spirit.\n\n"
            "Take a breath, slow down, and let these words guide you.\n\n"
            "Like & Subscribe to @silent_mind_talks for daily peaceful quotes. Drop your favourite quote in the comments!"
        )

    if not meta.get("hashtags"):
        meta["hashtags"] = [
            "#shorts", "#quotes", "#peaceful", "#mindfulness", "#motivation",
            "#nature", "#meditation", "#innerpeace", "#calmvibes", "#dailyquotes",
        ]

    if not meta.get("tags"):
        meta["tags"] = [
            "shorts", "quotes", "peaceful", "mindfulness", "motivation",
            "nature", "meditation", "inner peace", "calm", "daily quotes",
        ]

    return meta
