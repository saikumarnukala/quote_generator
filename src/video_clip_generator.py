"""
Generate animated video clips from static images using fal.ai's
Wan2.1 Image-to-Video model.

Each scene image is sent to fal.ai which returns a ~4-second animated
video clip where characters and elements actually move.
"""

import base64
import time
import requests


# fal.ai queue-based API (async job submission → polling → result)
FAL_MODEL = "fal-ai/wan/v2.1/image-to-video"
FAL_SUBMIT_URL = f"https://queue.fal.run/{FAL_MODEL}"
FAL_STATUS_URL = f"https://queue.fal.run/{FAL_MODEL}/requests/{{request_id}}/status"
FAL_RESULT_URL = f"https://queue.fal.run/{FAL_MODEL}/requests/{{request_id}}"


def _image_to_data_uri(image_path: str) -> str:
    """Convert a local image file to a data URI for the fal.ai API."""
    with open(image_path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    return f"data:image/png;base64,{b64}"


def generate_video_clip(
    image_path: str,
    prompt: str,
    output_path: str,
    fal_key: str,
    duration: str = "5",
    retries: int = 3,
) -> str:
    """
    Send a scene image to fal.ai Wan2.1 I2V and download the animated clip.

    Args:
        image_path: Path to the scene PNG image.
        prompt:     Motion prompt describing what should animate.
        output_path: Where to save the .mp4 clip.
        fal_key:    fal.ai API key.
        duration:   Video duration - "3" or "5" seconds.
        retries:    Number of retry attempts.

    Returns:
        output_path on success.
    """
    headers = {
        "Authorization": f"Key {fal_key}",
        "Content-Type": "application/json",
    }

    image_uri = _image_to_data_uri(image_path)

    payload = {
        "image_url": image_uri,
        "prompt": prompt,
        "num_frames": 81 if duration == "5" else 49,
        "frames_per_second": 16,
        "resolution": "480p",
        "enable_safety_checker": False,
    }

    for attempt in range(retries):
        try:
            # ── Submit job ──
            resp = requests.post(FAL_SUBMIT_URL, headers=headers, json=payload, timeout=30)
            if resp.status_code != 200:
                raise RuntimeError(f"fal.ai submit error {resp.status_code}: {resp.text[:300]}")

            request_id = resp.json()["request_id"]

            # ── Poll until complete ──
            status_url = FAL_STATUS_URL.format(request_id=request_id)
            result_url = FAL_RESULT_URL.format(request_id=request_id)

            for _ in range(120):  # max ~10 minutes
                time.sleep(5)
                status_resp = requests.get(status_url, headers=headers, timeout=15)
                status_data = status_resp.json()
                status = status_data.get("status", "")

                if status == "COMPLETED":
                    break
                elif status in ("FAILED", "CANCELLED"):
                    raise RuntimeError(f"fal.ai job failed: {status_data}")
            else:
                raise RuntimeError("fal.ai job timed out after 10 minutes")

            # ── Download result ──
            result_resp = requests.get(result_url, headers=headers, timeout=30)
            result_data = result_resp.json()

            video_url = result_data.get("video", {}).get("url")
            if not video_url:
                raise RuntimeError(f"No video URL in result: {result_data}")

            video_resp = requests.get(video_url, timeout=120)
            with open(output_path, "wb") as f:
                f.write(video_resp.content)

            return output_path

        except RuntimeError as e:
            # Do NOT retry on balance/auth errors — they will never succeed
            err_str = str(e)
            if "403" in err_str or "401" in err_str or "balance" in err_str.lower() or "locked" in err_str.lower():
                raise
            if attempt < retries - 1:
                wait = 10 + attempt * 10
                print(f"    fal.ai error, retrying in {wait}s... ({type(e).__name__}: {e})")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            if attempt < retries - 1:
                wait = 10 + attempt * 10
                print(f"    fal.ai error, retrying in {wait}s... ({type(e).__name__}: {e})")
                time.sleep(wait)
            else:
                raise

    return output_path
