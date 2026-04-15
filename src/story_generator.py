import json
from groq import Groq


LANGUAGE_NAMES = {
    "en": "English",
    "te": "Telugu",
    "hi": "Hindi",
    "ta": "Tamil",
    "ja": "Japanese",
}


def generate_story(topic: str, api_key: str, num_scenes: int = 7, language: str = "en") -> dict:
    """Generate an anime story with scenes using Groq API."""
    client = Groq(api_key=api_key)

    lang_name = LANGUAGE_NAMES.get(language, language)
    narration_instruction = (
        f"Write ALL narration text in {lang_name}. Keep image_prompt in English."
        if language != "en"
        else "Write all narration text in English."
    )

    prompt = f"""You are a talented anime story writer. Create a short dramatic anime story about: "{topic}"

{narration_instruction}

Return ONLY a valid JSON object with this exact structure:
{{
    "title": "Epic Story Title",
    "genre": "fantasy",
    "scenes": [
        {{
            "scene_number": 1,
            "narration": "The narration text spoken by the narrator. Make it dramatic and engaging. 2-3 sentences.",
            "image_prompt": "Detailed anime art prompt describing: character appearances, setting/background, mood/atmosphere, lighting conditions, anime style, highly detailed, masterpiece"
        }}
    ]
}}

Requirements:
- Exactly {num_scenes} scenes
- Each narration: 2-3 sentences, emotional and cinematic
- Image prompts: always in English, very specific and visual, mention art style, character details, colors
- Build a complete arc: introduction → rising action → climax → resolution
- Anime aesthetic: dramatic expressions, vivid colors, epic world-building"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.8,
    )

    data = json.loads(response.choices[0].message.content)

    # Normalize: ensure 'scenes' key exists
    if "scenes" not in data:
        raise ValueError(f"Unexpected story format from Groq: {list(data.keys())}")

    return data
