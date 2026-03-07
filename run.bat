@echo off
echo Starting AI-clip Finder API...

REM Check if uv is installed
where uv >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Error: 'uv' is not installed. Please install uv to proceed.
    echo Visit https://github.com/astral-sh/uv for installation instructions.
    pause
    exit /b 1
)

REM Create venv if it doesn't exist
if not exist .venv (
    echo Creating virtual environment...
    uv venv
)

REM Install/Sync dependencies
echo Syncing dependencies...
uv pip install -r requirements.txt

REM Run the application
echo Starting uvicorn...
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

echo.
echo Application stopped.
pause
