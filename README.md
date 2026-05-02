# Peaceful Quotes Video Generator

Automated Python pipeline that generates **calming quote videos** with AI-generated landscapes, inspirational quotes, ambient music, and TTS narration — then publishes to **YouTube Shorts** and **Instagram Reels**. Runs locally or via **GitHub Actions** on a daily schedule.

## Features

- **AI Quote Generation** — Groq generates thematic inspirational quotes with cinematic scene descriptions
- **Stock Nature Videos** — Pexels + Pixabay APIs fetch calming landscape footage
- **Text-to-Speech Narration** — Microsoft Edge TTS reads quotes aloud
- **Dynamic Text Overlays** — Elegant quote text rendered over video with Noto/DejaVu fonts
- **Ambient Music** — Jamendo API downloads royalty-free peaceful background music
- **YouTube Upload** — Auto-publishes as YouTube Shorts via OAuth
- **Instagram Upload** — Auto-publishes as Instagram Reels via Graph API (with H.264 re-encoding)
- **Multi-language** — Supports English, Telugu, Hindi, Tamil, and Japanese
- **Run History** — Tracks used quotes, videos, and music to avoid repetition
- **Copyright Checking** — Validates music and video licensing before upload
- **GitHub Actions CI/CD** — Automated daily pipeline

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/saikumarnukala/quote_generator.git
cd quote_generator
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
```

### 2. Configure API keys

Create a `.env` file with your keys:

| Key | Where to Get | Required |
|-----|-------------|----------|
| `GROQ_API_KEY` | [Groq Console](https://console.groq.com/) — Free | Yes |
| `PEXELS_API_KEY` | [Pexels API](https://www.pexels.com/api/) — Free | Yes |
| `JAMENDO_CLIENT_ID` | [Jamendo Developer](https://developer.jamendo.com/) — Free | For music |
| `PIXABAY_API_KEY` | [Pixabay API](https://pixabay.com/api/docs/) — Free | Optional fallback |
| `YT_CLIENT_ID` | [Google Cloud Console](https://console.cloud.google.com/) | For YouTube |
| `YT_CLIENT_SECRET` | Google Cloud Console | For YouTube |
| `YT_REFRESH_TOKEN` | Generated via OAuth flow | For YouTube |
| `INSTAGRAM_USER_ID` | [Meta Developer Portal](https://developers.facebook.com/) | For Instagram |
| `INSTAGRAM_ACCESS_TOKEN` | Meta Developer Portal | For Instagram |

### 3. Run the pipeline

```bash
# Auto-select topic from rotating pool
python main.py

# Custom topic
python main.py "gratitude and inner peace"

# Telugu, 8 scenes
python main.py --scenes 8 --lang te

# With Jamendo music upload permission
python main.py --allow-jamendo-upload
```

## GitHub Actions (Automated Daily Pipeline)

The workflow runs **once daily** at peak engagement:

| Time (IST) | UTC | Workflow |
|---|---|---|
| 12:30 PM | 07:00 | Quote video generation + upload |

### Required GitHub Secrets

Go to **Settings > Secrets and variables > Actions** and add:

| Secret | Description |
|--------|-------------|
| `GROQ_API_KEY` | Groq API key |
| `PEXELS_API_KEY` | Pexels API key |
| `JAMENDO_CLIENT_ID` | Jamendo client ID |
| `YT_CLIENT_ID` | YouTube OAuth client ID |
| `YT_CLIENT_SECRET` | YouTube OAuth client secret |
| `YT_REFRESH_TOKEN` | YouTube OAuth refresh token |
| `INSTAGRAM_USER_ID` | Instagram business account user ID |
| `INSTAGRAM_ACCESS_TOKEN` | Instagram Graph API access token |

Optional: `PIXABAY_API_KEY`, `HF_TOKEN`, `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET`

### Manual trigger

Go to **Actions > Quote Generator Pipeline > Run workflow** — you can override topic, scene count, and language.

## Project Structure

```
quote_generator/
├── main.py                      # Main orchestrator
├── config.py                    # Environment config loader
├── requirements.txt
├── data/
│   └── history.json             # Run history (quotes, videos, music used)
├── .github/
│   └── workflows/
│       ├── generate.yml         # Primary GitHub Actions workflow
│       └── quote_generator.yml  # Alternative workflow
└── src/
    ├── quote_generator.py       # AI quote + metadata generation (Groq)
    ├── video_fetcher.py         # Pexels / Pixabay nature video fetcher
    ├── music_fetcher.py         # Jamendo ambient music fetcher
    ├── ambient_generator.py     # Ambient audio generation
    ├── audio_generator.py       # Edge TTS narration
    ├── video_builder.py         # MoviePy video assembly + text overlays
    ├── subtitle_generator.py    # Subtitle timing generator
    ├── youtube_uploader.py      # YouTube Shorts upload (OAuth)
    ├── instagram_uploader.py    # Instagram Reels upload (Graph API)
    ├── history.py               # Run history tracking (never-repeat)
    └── copyright_checker.py     # Music/video license validation
```

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `VIDEO_WIDTH` | `1080` | Output video width |
| `VIDEO_HEIGHT` | `1920` | Output video height (9:16 vertical) |
| `VIDEO_FPS` | `30` | Output framerate |
| `SKIP_COLOUR_GRADE` | `0` | Set `1` to skip color grading (faster CI) |

## Security

Never commit `.env` or OAuth credentials. All sensitive files are listed in `.gitignore`.

## License

[MIT](LICENSE) — Sai Kumar Nukala
