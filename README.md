# AI-clip Finder API

AI-clip Finder is a high-performance FastAPI backend designed for automated video clipping and social media content creation. It transcribes long-form videos, uses LLMs to identify high-impact moments, and renders them into viral-ready vertical (9:16) clips with animated subtitles.

## 🚀 Key Features

- **Automated Clipping**: Uses LLMs (OpenAI/Pollinations) to analyze transcripts and identify segments with high "viral potential."
- **High-Speed Transcription**: Integrates with **Groq (Whisper-v3)** for near-instant audio-to-text conversion.
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
  - **Transcription**: Groq (Whisper-large-v3)
  - **Analysis**: OpenAI-compatible LLMs (defaulting to Pollinations AI)
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
   GROQ_API_KEY=your_groq_key
   LLM_API_KEY=your_llm_key  # Optional for some providers
   HOSTING=false             # Set to true for multi-user mode
   ```

4. **Start the Server**:
   ```bash
   uv run uvicorn app.main:app --reload
   ```

## 📡 API Overview

### Projects

- `POST /projects`: Create a new clipping project.
- `GET /projects`: List all projects (filtered by user if `HOSTING=true`).
- `POST /projects/{id}/upload`: Upload video file (triggers compression).
- `POST /projects/{id}/transcribe`: Extract audio and generate transcript via Groq.
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

## 🧪 Testing

The project includes a comprehensive test suite using `pytest`.

```bash
uv run pytest
```

---

_Built with ❤️ by the AI-clip Team._
