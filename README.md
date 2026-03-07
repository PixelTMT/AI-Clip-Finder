# AI-clip Finder API

[![Built With pollinations.ai](https://img.shields.io/badge/Built%20with-Pollinations-8a2be2?style=for-the-badge&logo=data:image/png;base64,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&logoColor=white&labelColor=6a0dad)](https://pollinations.ai/)


AI-clip Finder is a high-performance FastAPI backend designed for automated video clipping and social media content creation. It transcribes long-form videos, uses LLMs to identify high-impact moments, and renders them into viral-ready vertical (9:16) clips with animated subtitles.

## 🚀 Key Features

- **Automated Clipping**: Uses LLMs (OpenAI/Pollinations) to analyze transcripts and identify segments with high "viral potential."
- **BYOP Transcription**: Users connect their own Pollinations account for AI-powered transcription and analysis — zero server AI costs.
- **Vertical Transformation**: Automatically crops horizontal videos to **9:16 aspect ratio**, optimized for TikTok, Reels, and YouTube Shorts.
- **Animated Subtitles**: Generates and burns in dynamic, "karaoke-style" animated subtitles using the ASS format.
- **Hosting Mode**:
  - **User Isolation**: Cookie-based session management for multi-tenant deployments.
  - **Resource Limits**: Configurable file size limits and project expiry.
  - **Lifecycle Management**: Background tasks for periodic cleanup of expired and orphan projects.
- **Async Processing**: Robust background task management for heavy media operations (compression, transcription, rendering).

## 🛠 Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+)
- **Package Manager**: [uv](https://github.com/astral-sh/uv)
- **Media Engine**: [FFmpeg](https://ffmpeg.org/) & [FFprobe](https://ffmpeg.org/ffprobe.html)
- **AI Services**:
  - **Transcription**: Pollinations Whisper / Scribe (user-provided key)
  - **Analysis**: Pollinations LLMs (user-provided key)
- **Frontend**: Vanilla JavaScript / HTML5 / CSS3

## 📂 Project Structure

```text
AI-clip/
├── app/
│   ├── api/            # API Endpoints & Pydantic Models
│   ├── core/           # Configuration & Settings
│   ├── services/       # Core Business Logic (Media, LLM, Transcription)
│   ├── static/         # Frontend SPA (HTML/JS/CSS)
│   ├── main.py         # Application Entry Point
│   └── middleware.py   # Hosting & Security Middleware
├── data/               # Local Storage (Projects, Index, Locks)
├── tests/              # Comprehensive Test Suite
├── requirements.txt    # Python Dependencies
├── .env                # Environment Variables (Secrets)
└── run.bat             # One-click Start (Windows)
```

## ⚡ Getting Started

### Prerequisites

- **Python 3.10+**
- **FFmpeg**: Must be installed and available in your system `PATH`.
- **uv**: Recommended for fast dependency management.

### Installation & Run

#### Windows (Recommended)

Simply run the provided batch file:

```cmd
run.bat
```

#### Manual Setup

1. **Initialize Environment**:

   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install Dependencies**:

   ```bash
   uv pip install -r requirements.txt
   ```

3. **Configure Environment**:
   Create a `.env` file in the root directory:

   ```env
   POLLINATIONS_APP_KEY=pk_your_app_key_here
   HOSTING=false             # Set to true for multi-user mode
   ```

4. **Start the Server**:
   ```bash
   uv run uvicorn app.main:app --reload
   ```

## 🔑 BYOP (Bring Your Own Pollen)

This app uses a **Bring Your Own Pollen** model — users connect their own Pollinations account to enable AI features. Server AI cost: **$0**.

- Click **"Connect with Pollinations"** in the app header
- You'll be redirected to [enter.pollinations.ai](https://enter.pollinations.ai) to authorize
- Your personal API key is stored in your browser (localStorage) and sent per-request
- Keys expire after 30 days — simply reconnect to refresh
- All AI costs (transcription, clip analysis) are billed to your Pollinations account

## 📡 API Overview

### Projects

- `POST /projects`: Create a new clipping project.
- `GET /projects`: List all projects (filtered by user if `HOSTING=true`).
- `POST /projects/{id}/upload`: Upload video file (triggers compression).
- `POST /projects/{id}/transcribe`: Extract audio and generate transcript via Pollinations.
- `POST /projects/{id}/analyze`: Discover clips using LLM.
- `GET /projects/{id}/status`: Check progress of background operations.

### Clips & Rendering

- `POST /api/clips/render-preview`: Quick render of a clip for review.
- `POST /api/clips/render-final`: High-quality render of the final clip.
- `GET /api/clips/render-status/{task_id}`: Track rendering progress.
- `GET /api/clips/download/{task_id}`: Download the rendered MP4.

## ⚙️ Configuration

| Variable              | Default        | Description                             |
| --------------------- | -------------- | --------------------------------------- |
| `HOSTING`             | `false`        | Enables user isolation and size limits. |
| `MAX_FILE_SIZE`       | `100MB`        | Max upload size in hosting mode.        |
| `PROJECT_EXPIRY_DAYS` | `30`           | Days until project is auto-deleted.     |
| `LLM_MODEL`           | `openai-large` | Model used for clip discovery.          |
| `LLM_BASE_URL`        | `Pollinations` | API endpoint for LLM analysis.          |
| `POLLINATIONS_APP_KEY` | (empty) | Publishable key for Pollinations auth redirect |

## 🧪 Testing

The project includes a comprehensive test suite using `pytest`.

```bash
uv run pytest
```

---

_Built with ❤️ by the AI-clip Team._
