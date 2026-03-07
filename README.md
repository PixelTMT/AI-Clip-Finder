# AI-clip Discovery API

FastAPI-based backend for the AI-clip Discovery platform.

## Prerequisites

-   **Python 3.10+**
-   **uv** (Python package manager)

## Setup & Run

### Windows
Simply run the provided batch file:
```cmd
run.bat
```

### Manual Setup
1.  Create virtual environment:
    ```bash
    uv venv
    ```
2.  Install dependencies:
    ```bash
    uv pip install -r requirements.txt
    ```
3.  Run the application:
    ```bash
    uv run uvicorn app.main:app --reload
    ```

## Project Structure
-   `app/`: Main application code
-   `data/`: Data storage
-   `conductor/`: Orchestration logic

## Hosting Features

If the environment variable `HOSTING=true` is set in your `.env` file, the following features are enabled:
- **User Isolation**: Users are assigned a unique ID in their browser cookies. They can only see and manage their own projects.
- **File size limits**: Uploads are restricted to 100MB.
- **Project Expiry**: Projects are automatically deleted 30 days after creation to save storage space.
- **Periodic Cleanup**: A background task runs every hour to purge expired projects and clean up orphan files.