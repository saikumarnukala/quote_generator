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


def generate_quotes(topic: str, api_key: str, num_scenes: int = 7, language: str = "en") -> dict:
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

    prompt = f"""Create a calming, inspirational quote video about the theme: "{topic}"

Generate exactly {num_scenes} peaceful scenes. Return ONLY valid JSON — no markdown, no extra text.

{{
  "title": "video title in {lang_name}",
  "theme": "{topic}",
  "scenes": [
    {{
      "location": "short beautiful location name in {lang_name}",
      "video_search": "2-4 English words for Pexels search, e.g. 'rain forest leaves' or 'ocean waves sunset' or 'misty mountain waterfall'",
      "quote": "a timeless, profound inspirational quote in {lang_name}",
      "author": "Real person name, or 'Ancient Wisdom', or 'Unknown'",
      "narration": "2-3 sentences in {lang_name} spoken softly like a meditation guide"
    }}
  ]
}}

Rules:
- video_search MUST always be in English only — 2-4 descriptive nature words
- All other fields (title, location, quote, author, narration) MUST be in {lang_name}
- Quotes: timeless, uplifting, philosophical — mix famous and original
- video_search: vary widely — rain on leaves, waterfall mist, ocean waves, forest sunlight, snow mountains, cherry blossom, desert sunrise, bamboo wind, river calm, autumn forest
- Each scene should feel like a different magical corner of the world
- narration should feel warm, slow, and peaceful — not rushed"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.85,
        max_tokens=4000,
    )

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

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1500,
    )

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
