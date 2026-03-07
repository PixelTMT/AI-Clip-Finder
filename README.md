# AI-clip Finder API

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
