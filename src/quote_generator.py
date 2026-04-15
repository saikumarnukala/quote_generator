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
              "image_prompt": str,   # English prompt for image generation
              "quote":        str,   # the inspirational quote
              "author":       str,   # attribution
              "narration":    str,   # text spoken aloud
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
      "image_prompt": "photorealistic 4K landscape photograph, [specific peaceful natural place], golden hour or sunrise lighting, serene atmosphere, dramatic yet calming, ultra detailed, professional photography, no people, cinematic wide shot, breathtaking beauty",
      "quote": "a timeless, profound inspirational quote in {lang_name}",
      "author": "Real person name, or 'Ancient Wisdom', or 'Unknown'",
      "narration": "2-3 sentences in {lang_name} spoken softly like a meditation guide: describe the beauty of the location, then gently introduce the meaning of the quote"
    }}
  ]
}}

Rules:
- image_prompt MUST always be in English only (never translate it)
- All other fields (title, location, quote, author, narration) MUST be in {lang_name}
- Quotes: timeless, uplifting, philosophical — mix famous and original
- Locations: vary widely — Himalayan peaks, Amazon forest, Japanese bamboo grove, Sahara sunrise, Norwegian fjord, Bali rice terraces, Scottish highlands, etc.
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
