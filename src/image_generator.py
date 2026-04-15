import time
import requests
from PIL import Image
from io import BytesIO

# SD3 medium: confirmed working on hf-inference serverless API
HF_API_URL = "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-3-medium-diffusers"

NEGATIVE_PROMPT = (
    "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, "
    "fewer digits, cropped, worst quality, low quality, normal quality, "
    "jpeg artifacts, signature, watermark, username, blurry, deformed"
)


def generate_image(prompt: str, hf_token: str, output_path: str, retries: int = 5) -> str:
    """Generate an anime-style image via HuggingFace Inference API (SD3 medium)."""
    headers = {"Authorization": f"Bearer {hf_token}"}

    enhanced_prompt = (
        f"{prompt}, anime style, masterpiece, best quality, "
        "highly detailed, sharp focus, vibrant colors, cinematic composition"
    )

    payload = {
        "inputs": enhanced_prompt,
        "parameters": {
            "negative_prompt": NEGATIVE_PROMPT,
            "width": 768,
            "height": 432,
            "num_inference_steps": 25,
            "guidance_scale": 7.0,
        },
    }

    for attempt in range(retries):
        try:
            response = requests.post(
                HF_API_URL, headers=headers, json=payload, timeout=120
            )

            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if "image" not in content_type and len(response.content) < 1000:
                    raise ValueError(f"Unexpected response content: {response.text[:200]}")

                image = Image.open(BytesIO(response.content)).convert("RGB")
                image = image.resize((1280, 720), Image.LANCZOS)
                image.save(output_path)
                return output_path

            elif response.status_code in (503, 500):
                wait = 20 + attempt * 10
                print(f"    Server busy, waiting {wait}s... (attempt {attempt + 1}/{retries})")
                time.sleep(wait)

            elif response.status_code == 429:
                wait = 30
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)

            elif response.status_code == 400 and "out of memory" in response.text.lower():
                wait = 30 + attempt * 15
                print(f"    GPU busy (OOM), waiting {wait}s... (attempt {attempt + 1}/{retries})")
                time.sleep(wait)

            else:
                raise RuntimeError(
                    f"HuggingFace API error {response.status_code}: {response.text[:300]}"
                )

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < retries - 1:
                print(f"    Connection error, retrying... ({e})")
                time.sleep(10)
            else:
                raise

    raise RuntimeError(f"Failed to generate image after {retries} attempts")
