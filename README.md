# Infotainment Video Automation System

An automated, reliable Python system that transforms researched science, technology, history, and educational topics into high-quality **9:16 vertical infotainment videos** (YouTube Shorts).

Engineered to operate with **zero local GPU requirements**, low operational cost, factual accuracy, verified source citations, and deterministic asset caching.

---

## Architecture Overview

```
                      ┌──────────────────────────────────────┐
                      │           Topic Selection            │
                      │ (User input / Curated category pool) │
                      └──────────────────┬───────────────────┘
                                         │
                                         ▼
                      ┌──────────────────────────────────────┐
                      │    Factual Research & Citations      │
                      │        (Wikipedia REST API)          │
                      └──────────────────┬───────────────────┘
                                         │
                                         ▼
                      ┌──────────────────────────────────────┐
                      │       Groq Script Generation         │
                      │  (Llama 3.3 / Llama 3.1 JSON Schema) │
                      └──────────────────┬───────────────────┘
                                         │
                                         ▼
                      ┌──────────────────────────────────────┐
                      │   Deepgram Aura Speech Narration     │
                      │  (Deterministic SHA-256 Audio Cache) │
                      └──────────────────┬───────────────────┘
                                         │
                                         ▼
                      ┌──────────────────────────────────────┐
                      │    Synchronized Subtitle Timing      │
                      │  (Safe margins for 9:16 Shorts UI)   │
                      └──────────────────┬───────────────────┘
                                         │
                                         ▼
                      ┌──────────────────────────────────────┐
                      │     Multi-Tier Media Retrieval       │
                      │   1. Pexels Video (Primary)          │
                      │   2. Pixabay Video (Fallback)        │
                      │   3. Pexels / Pixabay Photo          │
                      │   4. Informative Infographic Card    │
                      └──────────────────┬───────────────────┘
                                         │
                                         ▼
                      ┌──────────────────────────────────────┐
                      │    Curated Background Music Mixing   │
                      │   (YouTube Audio Library Collection) │
                      └──────────────────┬───────────────────┘
                                         │
                                         ▼
                      ┌──────────────────────────────────────┐
                      │    FFmpeg Native Video Assembly      │
                      │ (1080x1920 @ 30fps, H.264, Faststart)│
                      └──────────────────┬───────────────────┘
                                         │
                                         ▼
                      ┌──────────────────────────────────────┐
                      │      FFprobe Quality Validation      │
                      │   (Resolution, Codecs, Stream Check) │
                      └──────────────────┬───────────────────┘
                                         │
                                         ▼
                      ┌──────────────────────────────────────┐
                      │     Thumbnails & YouTube Metadata    │
                      │  (SEO Titles, Descriptions, Citations)
                      └──────────────────┬───────────────────┘
                                         │
                                         ▼
                      ┌──────────────────────────────────────┐
                      │     Persistent Run History Save      │
                      │   (Topics, Assets, Video IDs)        │
                      └──────────────────┬───────────────────┘
                                         │
                                         ▼
                      ┌──────────────────────────────────────┐
                      │  Optional YouTube Data API v3 Upload │
                      │   (Disabled by default; Private)     │
                      └──────────────────────────────────────┘
```

---

## Key Features

1. **Grounded Factual Research**:
   - Queries open institutional knowledge (Wikipedia REST APIs) to extract verified facts, canonical source titles, and source URLs.
   - Distinguishes facts from speculation and provides factual anchors for AI scriptwriting.

2. **Schema-Validated Scriptwriting**:
   - Structured JSON generation with Groq (`llama-3.3-70b-versatile`, `llama-3.1-8b-instant`).
   - Generates opening hook, step-by-step explanatory logic, scene visual descriptions, on-screen text, and stock footage search queries.
   - Automated duration budgeting targeting 30–60 second video pacing.
   - Built-in deterministic offline fallback script generator if the Groq API key is expired or unavailable.

3. **High-Fidelity Narration via Deepgram Aura**:
   - Spoken narration synthesized with Deepgram Aura (`aura-asteria-en`, `aura-orion-en`).
   - Consistent single voice across all scenes in a video.
   - Exact microsecond audio duration measurement with `ffprobe` (bypassing slow third-party Python wrappers).
   - Deterministic SHA-256 caching: identical sentences are never re-synthesized.
   - Configurable fallback to Microsoft Edge TTS when enabled.

4. **Multi-Tier Visual Retrieval Hierarchy**:
   - Primary: **Pexels Video** (conformed and scaled to 1080x1920 portrait).
   - Secondary: **Pixabay Video** (when Pexels returns no scene results).
   - Tertiary: **Pexels & Pixabay Photos** (converted to animated video clips with smooth pan/zoom).
   - Quaternary: **Infographic Cards** (high-contrast educational summary cards generated via Pillow).
   - Every downloaded clip is verified with `ffprobe` before assembly.

5. **Local Curated Music Library (YouTube Audio Library)**:
   - Eliminates copyright strikes and ContentID surprises.
   - Background tracks are selected from a locally curated collection organized in `assets/music/` and tracked in `assets/music/manifest.json`.
   - Category-aware selection (`science/`, `technology/`, `space/`, `history/`, `nature/`, `general/`).
   - Automatic attribution detection: if a track requires attribution, it is automatically appended to the YouTube video description.
   - Narration-aware audio mixing: background music is volume-ducked (`0.16` by default), faded in smoothly (1.5s), and faded out (2.0s) as narration concludes.
   - If no verified track is available, the system cleanly renders narration without music.

6. **Native FFmpeg Assembly**:
   - Replaces heavy, fragile MoviePy dependencies with direct FFmpeg subprocess calls.
   - Burns in styled ASS subtitles placed above Shorts UI overlays (safe bottom margin 320px).
   - Outputs web-optimized MP4 with H.264 High Profile, AAC stereo audio, and `+faststart` moov atom.

7. **FFprobe Quality Validation**:
   - Automated post-render checks ensure the MP4 meets delivery specs: 1080x1920, 30 FPS, H.264 video, AAC audio, and non-empty streams.

8. **Secure YouTube Upload Integration**:
   - Uploads are **disabled by default** to avoid unexpected publishing.
   - Defaults to `private` privacy status during testing.
   - Full dry-run mode for CI/CD and local development (`--dry-run`).

---

## Installation

### Prerequisites
- Python 3.10+
- FFmpeg and FFprobe installed and available in system `PATH`
  - Windows: `winget install Gyan.FFmpeg` or download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/)
  - Linux (Ubuntu/Debian): `sudo apt-get install -y ffmpeg fonts-noto fonts-dejavu-core`
  - macOS: `brew install ffmpeg`

### Setup

```bash
# 1. Clone repository
git clone https://github.com/saikumarnukala/quote_generator.git
cd quote_generator

# 2. Create virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env` and supply your credentials:

```bash
cp .env.example .env
```

### Environment Variables

| Variable | Description | Default | Required |
|---|---|---|---|
| `GROQ_API_KEY` | Groq API Key for script and scene generation | None | Recommended |
| `DEEPGRAM_API_KEY` | Deepgram API Key for Aura TTS voiceover | None | Yes |
| `PEXELS_API_KEY` | Pexels API Key for stock videos and photos | None | Yes |
| `PIXABAY_API_KEY` | Pixabay API Key for fallback media | None | Optional |
| `DEEPGRAM_VOICE` | Voice model for narration | `aura-asteria-en` | No |
| `EDGE_TTS_VOICE` | Voice model for optional fallback | `en-US-ChristopherNeural` | No |
| `FALLBACK_TO_EDGE_TTS` | Enable Edge TTS if Deepgram fails | `false` | No |
| `YOUTUBE_UPLOAD_ENABLED` | Global toggle for YouTube uploading | `false` | No |
| `YOUTUBE_PRIVACY_STATUS` | Visibility for uploaded videos | `private` | No |
| `YT_CLIENT_ID` | Google OAuth2 Client ID | None | Only for upload |
| `YT_CLIENT_SECRET` | Google OAuth2 Client Secret | None | Only for upload |
| `YT_REFRESH_TOKEN` | Google OAuth2 Refresh Token | None | Only for upload |

---

## Curated Music Library Setup

Background music is selected exclusively from the local curated music collection located in `assets/music/`.

> [!IMPORTANT]
> The YouTube Audio Library does not offer a public automated download API. Tracks must be downloaded manually from the [YouTube Audio Library](https://www.youtube.com/audiolibrary) and placed into `assets/music/`.

### Directory Structure

```
assets/
└── music/
    ├── manifest.json
    ├── science/
    │   └── quantum_curiosity.wav
    ├── space/
    │   └── stellar_drift.wav
    ├── history/
    │   └── ancient_echos.wav
    └── general/
        └── cinematic_pulse.wav
```

### Manifest Schema (`assets/music/manifest.json`)

```json
[
  {
    "filename": "science/quantum_curiosity.wav",
    "title": "Quantum Curiosity",
    "artist": "Curated YouTube Audio Library",
    "source": "YouTube Audio Library",
    "license": "YouTube Audio Library License",
    "attribution_required": false,
    "attribution_text": "",
    "permitted_usage_notes": "Free to use in YouTube videos and monetize.",
    "categories": ["science", "technology", "ai"],
    "moods": ["curious", "inspirational"],
    "verified": true
  }
]
```

---

## Local Execution

### 1. Automatic Topic Selection from Pool
```bash
python main.py
```

### 2. Specific Topic
```bash
python main.py "Why Does Ice Float on Water?" --category everyday_science
```

### 3. Topic from Specific Category
```bash
python main.py --category space --scenes 4
```

### 4. Customizing Voice and Music
```bash
# Custom Deepgram voice
python main.py "How Do Microprocessors Work?" --voice aura-orion-en

# Voiceover-only without background music
python main.py "The Great Wall of China" --category history --no-music

# Custom music file
python main.py "Black Holes" --music assets/music/space/stellar_drift.wav
```

### 5. Dry-Run Simulation (No Quota Consumption)
```bash
python main.py "The Boötes Void" --dry-run
```

### 6. Upload to YouTube & Instagram
Uploads are disabled by default to prevent accidental publishing.

```bash
# Upload to YouTube only (private by default)
python main.py "How CRISPR Works" --category science --upload --privacy private

# Upload to Instagram Reels only
python main.py "How CRISPR Works" --category science --upload-instagram

# Upload to both platforms simultaneously
python main.py "How CRISPR Works" --category science --upload-all
```

### 7. Refreshing API & OAuth Credentials
If uploads fail with `invalid_grant` (YouTube) or `OAuthException 190` (Instagram), refresh your tokens:

- **YouTube Refresh Token**:
  Run the local OAuth helper script and authenticate in your browser:
  ```bash
  python scripts/get_youtube_token.py --json-file client_secret_*.json
  ```
  Copy the printed `refresh_token` into your `.env` as `YT_REFRESH_TOKEN` and update your GitHub secret `YT_REFRESH_TOKEN`.
- **Instagram Access Token**:
  1. Open [Meta Graph API Explorer](https://developers.facebook.com/tools/explorer/).
  2. Select your Meta App and generate a User Token with permissions: `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`, `pages_show_list`.
  3. Exchange it for a long-lived 60-day token via Access Token Tool or Graph API.
  4. Update `INSTAGRAM_ACCESS_TOKEN` in your `.env` and GitHub secret `INSTAGRAM_ACCESS_TOKEN`.

---

## Output Files

Every run outputs organized assets into `output/`:
- `output/{topic}_{timestamp}.mp4` — Final 1080x1920 9:16 vertical video.
- `output/{topic}_{timestamp}_thumb.jpg` — 1080x1920 high-contrast thumbnail.
- `output/{topic}_{timestamp}_metadata.json` — SEO title, description, sources, and tags.
- `data/history.json` — Persistent log of topics, visual assets, and YouTube video IDs.

---

## Running Automated Tests

Run the full automated test suite (uses mocked responses, zero API credits consumed):

```bash
python -m unittest discover tests
```

---

## GitHub Actions CI/CD

The workflow in `.github/workflows/generate.yml` supports manual execution via GitHub's `workflow_dispatch` interface:

1. Navigate to **Actions > Infotainment Video Automation**.
2. Click **Run workflow**.
3. Configure:
   - `topic`: (Optional custom topic)
   - `category`: (e.g. `science`, `space`, `technology`, `history`)
   - `scenes`: Number of scenes (default: 4)
   - `dry_run`: `true` or `false`
   - `upload`: `true` or `false`
4. Download the generated MP4, thumbnail, and metadata directly from the **Artifacts** section.

---

## Licensing & Compliance Notice

- Stock footage and photography are sourced under the **Pexels License** and **Pixabay License** (royalty-free for commercial and online use).
- Background music must be sourced under the **YouTube Audio Library License** or approved Creative Commons licenses. Required attributions are automatically formatted in the video description.
- Automated code validations check metadata and file formats; they do not constitute legal advice.

---

## License

[MIT License](LICENSE) — Sai Kumar Nukala
