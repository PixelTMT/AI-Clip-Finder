import os
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Query, Request
from filelock import FileLock

from app.api.models import (
    Project,
    ProjectCreate,
    OperationType,
    OperationStatus,
    ASSOptions,
)
from app.core.config import settings
from app.services import storage, media, transcription, llm
from app.services.subtitle_service import SubtitleService
from openai import AuthenticationError, APIStatusError

router = APIRouter()

# Simple in-memory progress tracker (kept for backward compatibility/polling)
progress_store = {}

def get_user_project(index: dict, project_id: str, user_id: str = None) -> Optional[dict]:
    """Helper to get project and verify user ownership if HOSTING is true."""
    project = index.get(project_id)
    if not project:
        return None
    
    if settings.HOSTING and project.get("user_id") != user_id:
        return None
        
    return project

def get_api_key(request: Request) -> str:
    """Extract API key from Authorization or X-Pollinations-Key header.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The extracted API key string.

    Raises:
        HTTPException: 401 if no API key is found.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    key = request.headers.get("X-Pollinations-Key", "")
    if key:
        return key
    raise HTTPException(status_code=401, detail="api_key_missing")

@router.get("/")
async def get_index():
    from fastapi.responses import FileResponse

    return FileResponse("app/static/index.html")


@router.get("/editor")
async def get_editor():
    from fastapi.responses import FileResponse

    return FileResponse("app/static/editor.html")

@router.get("/config/pollinations")
async def get_pollinations_config():
    """Return Pollinations configuration for client-side BYOP auth."""
    return {
        "app_key": settings.POLLINATIONS_APP_KEY,
        "auth_url": "https://enter.pollinations.ai/authorize",
    }


@router.get("/projects/active-operations")
async def get_active_operations(request: Request):
    user_id = getattr(request.state, "user_id", None)
    lock = FileLock(settings.LOCK_FILE)
    with lock:
        index = storage.get_projects_index()

    active_projects = []
    for project in index.values():
        if project.get("active_operation"):
            # Filter by user_id if hosting is true
            if settings.HOSTING and project.get("user_id") != user_id:
                continue
            active_projects.append(project)

    return active_projects

@router.get("/projects/{project_id}/status")
async def get_project_status(project_id: str, request: Request):
    user_id = getattr(request.state, "user_id", None)
    # Fetch real status from storage
    lock = FileLock(settings.LOCK_FILE)
    with lock:
        index = storage.get_projects_index()
        project = get_user_project(index, project_id, user_id)
        if project:
            return {
                "status": project.get("status", "unknown"),
                "progress": progress_store.get(project_id, ""),
                "active_operation": project.get("active_operation"),
            }
    return {"status": "not_found"}

@router.post("/projects", response_model=Project, status_code=201)
async def create_project(project_in: ProjectCreate, request: Request):
    user_id = getattr(request.state, "user_id", None)
    new_project = storage.create_project_entry(project_in.name, user_id=user_id)
    return Project(**new_project)

@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, request: Request):
    user_id = getattr(request.state, "user_id", None)
    lock = FileLock(settings.LOCK_FILE)
    with lock:
        index = storage.get_projects_index()
        project = get_user_project(index, project_id, user_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
    
    storage.delete_project_entry(project_id)
    return {"message": "Project deleted"}

@router.get("/projects")
async def list_projects(request: Request):
    user_id = getattr(request.state, "user_id", None)
    lock = FileLock(settings.LOCK_FILE)
    with lock:
        index = storage.get_projects_index()
    
    # Filter by user_id if hosting is enabled
    projects = list(index.values())
    if settings.HOSTING:
        projects = [p for p in projects if p.get("user_id") == user_id]
        
    # Sort by creation time desc (if possible, but dict is insertion ordered in recent python)
    return list(reversed(projects))

def process_upload_background(project_id: str, original_path: str, processed_path: str):
    try:
        storage.update_project_status(project_id, "compressing")
        storage.set_active_operation(
            project_id,
            type=OperationType.UPLOAD,
            status=OperationStatus.RUNNING,
            message="Compressing video...",
        )
        media.compress_video(original_path, processed_path)
        storage.update_project_status(project_id, "uploaded")
        storage.clear_active_operation(project_id)
    except Exception as e:
        storage.update_project_status(project_id, "error", str(e))
        storage.set_active_operation(
            project_id,
            type=OperationType.UPLOAD,
            status=OperationStatus.FAILED,
            message=str(e),
        )


def check_project_lock(project_id: str):
    lock = FileLock(settings.LOCK_FILE)
    with lock:
        index = storage.get_projects_index()
        project = index.get(project_id)
        if project and project.get("active_operation"):
            op = project["active_operation"]
            # Check if status is running/pending. Since active_operation should be cleared on completion,
            # existence usually implies it's active. But let's be safe.
            if op["status"] in [OperationStatus.PENDING, OperationStatus.RUNNING]:
                raise HTTPException(
                    status_code=409,
                    detail={"message": "Operation in progress", "active_operation": op},
                )


@router.post("/projects/{project_id}/upload")
async def upload_video(
    project_id: str,
    request: Request,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
):
    user_id = getattr(request.state, "user_id", None)
    lock = FileLock(settings.LOCK_FILE)
    with lock:
        index = storage.get_projects_index()
        project = get_user_project(index, project_id, user_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
    
    check_project_lock(project_id)

    project_path = os.path.join(settings.PROJECTS_DIR, project_id)
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="Project not found")

    original_path = os.path.join(project_path, "original.mp4")
    processed_path = os.path.join(project_path, "processed.mp4")

    storage.update_project_status(project_id, "uploading")
    storage.set_active_operation(
        project_id,
        type=OperationType.UPLOAD,
        status=OperationStatus.RUNNING,
        message="Uploading and processing...",
    )

    try:
        with open(original_path, "wb") as f:
            f.write(await file.read())

        if background_tasks:
            background_tasks.add_task(
                process_upload_background, project_id, original_path, processed_path
            )
        else:
            # Fallback if no background tasks (shouldn't happen with FastAPI)
            process_upload_background(project_id, original_path, processed_path)

    except Exception as e:
        storage.update_project_status(project_id, "error", str(e))
        storage.set_active_operation(
            project_id,
            type=OperationType.UPLOAD,
            status=OperationStatus.FAILED,
            message=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))

    return {"message": "Upload successful", "project_id": project_id}


def process_transcribe_background(project_id: str, video_path: str, audio_path: str, api_key: str):
    try:
        storage.update_project_status(project_id, "transcribing")
        progress_store[project_id] = "Extracting audio..."
        storage.set_active_operation(
            project_id,
            type=OperationType.TRANSCRIBE,
            status=OperationStatus.RUNNING,
            message="Extracting audio...",
        )
        media.extract_audio(video_path, audio_path)

        progress_store[project_id] = "Transcribing..."
        storage.set_active_operation(
            project_id,
            type=OperationType.TRANSCRIBE,
            status=OperationStatus.RUNNING,
            message="Transcribing audio...",
        )
        transcript = transcription.transcribe_audio(audio_path, api_key=api_key)

        lock = FileLock(settings.LOCK_FILE)
        with lock:
            index = storage.get_projects_index()
            if project_id in index:
                index[project_id]["transcript"] = transcript
                storage.save_projects_index(index)

        storage.update_project_status(project_id, "transcribed")
        storage.clear_active_operation(project_id)

    except AuthenticationError as e:
        storage.update_project_status(project_id, "error", str(e))
        storage.set_active_operation(
            project_id,
            type=OperationType.TRANSCRIBE,
            status=OperationStatus.FAILED,
            message="auth_expired",
        )
    except APIStatusError as e:
        if e.status_code == 402:
            storage.update_project_status(project_id, "error", str(e))
            storage.set_active_operation(
                project_id,
                type=OperationType.TRANSCRIBE,
                status=OperationStatus.FAILED,
                message="insufficient_balance",
            )
        else:
            storage.update_project_status(project_id, "error", str(e))
            storage.set_active_operation(
                project_id,
                type=OperationType.TRANSCRIBE,
                status=OperationStatus.FAILED,
                message=str(e),
            )
    except Exception as e:
        storage.update_project_status(project_id, "error", str(e))
        storage.set_active_operation(
            project_id,
            type=OperationType.TRANSCRIBE,
            status=OperationStatus.FAILED,
            message=str(e),
        )


@router.post("/projects/{project_id}/transcribe")
async def transcribe_project(project_id: str, request: Request, background_tasks: BackgroundTasks = None):
    user_id = getattr(request.state, "user_id", None)
    lock = FileLock(settings.LOCK_FILE)
    with lock:
        index = storage.get_projects_index()
        project = get_user_project(index, project_id, user_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
    
    check_project_lock(project_id)

    project_path = os.path.join(settings.PROJECTS_DIR, project_id)
    video_path = os.path.join(
        project_path, "original.mp4"
    )  # use original.mp4 for transcribe quality
    audio_path = os.path.join(project_path, "audio.mp3")

    if not os.path.exists(video_path):
        raise HTTPException(status_code=400, detail="Video not uploaded yet")

    storage.update_project_status(project_id, "transcribing")
    storage.set_active_operation(
        project_id,
        type=OperationType.TRANSCRIBE,
        status=OperationStatus.RUNNING,
        message="Transcribing audio...",
    )

    api_key = get_api_key(request)

    if background_tasks:
        background_tasks.add_task(
            process_transcribe_background, project_id, video_path, audio_path, api_key
        )
    else:
        process_transcribe_background(project_id, video_path, audio_path, api_key)

    return {"message": "Transcription started", "project_id": project_id}

def process_analyze_background(
    project_id: str,
    project_path: str,
    video_path: str,
    transcript: dict,
    custom_prompt: Optional[str],
    clip_count: Optional[int],
    api_key: str,
):
    try:
        storage.update_project_status(project_id, "analyzing")
        progress_store[project_id] = "Analyzing with LLM..."
        storage.set_active_operation(
            project_id,
            type=OperationType.FIND_CLIPS,
            status=OperationStatus.RUNNING,
            message="Analyzing with LLM...",
        )
        clips = llm.analyze_transcript(
            transcript, custom_instructions=custom_prompt, clip_count=clip_count, api_key=api_key
        )

        progress_store[project_id] = "Generating thumbnails..."
        storage.set_active_operation(
            project_id,
            type=OperationType.FIND_CLIPS,
            status=OperationStatus.RUNNING,
            message="Generating thumbnails...",
        )
        thumb_dir = os.path.join(project_path, "thumbnails")
        os.makedirs(thumb_dir, exist_ok=True)

        for clip in clips:
            start_time = clip.get("start_time", 0)
            thumb_path = os.path.join(thumb_dir, f"{start_time:.1f}.jpg")
            media.extract_frame(video_path, start_time, thumb_path)

        lock = FileLock(settings.LOCK_FILE)
        with lock:
            index = storage.get_projects_index()
            if project_id in index:
                index[project_id]["clips"] = clips
                index[project_id]["custom_prompt"] = custom_prompt
                index[project_id]["clip_count"] = clip_count
                storage.save_projects_index(index)

        storage.update_project_status(project_id, "completed")
        storage.clear_active_operation(project_id)

    except AuthenticationError as e:
        storage.update_project_status(project_id, "error", str(e))
        storage.set_active_operation(
            project_id,
            type=OperationType.FIND_CLIPS,
            status=OperationStatus.FAILED,
            message="auth_expired",
        )
    except APIStatusError as e:
        if e.status_code == 402:
            storage.update_project_status(project_id, "error", str(e))
            storage.set_active_operation(
                project_id,
                type=OperationType.FIND_CLIPS,
                status=OperationStatus.FAILED,
                message="insufficient_balance",
            )
        else:
            storage.update_project_status(project_id, "error", str(e))
            storage.set_active_operation(
                project_id,
                type=OperationType.FIND_CLIPS,
                status=OperationStatus.FAILED,
                message=str(e),
            )
    except Exception as e:
        storage.update_project_status(project_id, "error", str(e))
        storage.set_active_operation(
            project_id,
            type=OperationType.FIND_CLIPS,
            status=OperationStatus.FAILED,
            message=str(e),
        )


@router.post("/projects/{project_id}/analyze")
async def analyze_project(
    project_id: str,
    request: Request,
    custom_prompt: Optional[str] = Query(None),
    clip_count: Optional[int] = Query(None, ge=0),
    background_tasks: BackgroundTasks = None,
):
    user_id = getattr(request.state, "user_id", None)
    check_project_lock(project_id)

    project_path = os.path.join(settings.PROJECTS_DIR, project_id)
    video_path = os.path.join(project_path, "processed.mp4")

    # Get transcript from storage
    lock = FileLock(settings.LOCK_FILE)
    with lock:
        index = storage.get_projects_index()
        project = get_user_project(index, project_id, user_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        if "transcript" not in project:
            raise HTTPException(status_code=400, detail="Transcript not found")
        transcript = project["transcript"]

    storage.update_project_status(project_id, "analyzing")
    storage.set_active_operation(
        project_id,
        type=OperationType.FIND_CLIPS,
        status=OperationStatus.RUNNING,
        message="Analyzing clips...",
    )

    api_key = get_api_key(request)

    if background_tasks:
        background_tasks.add_task(
            process_analyze_background,
            project_id,
            project_path,
            video_path,
            transcript,
            custom_prompt,
            clip_count,
            api_key,
        )
    else:
        process_analyze_background(
            project_id, project_path, video_path, transcript, custom_prompt, clip_count, api_key
        )

    return {"message": "Analysis started", "project_id": project_id}

@router.post("/projects/{project_id}/process")
async def process_project(project_id: str, request: Request):
    # Sequential execution wrapper
    await transcribe_project(project_id, request)
    return await analyze_project(project_id, request)

@router.post("/projects/{project_id}/generate-ass")
async def generate_ass(project_id: str, options: ASSOptions, request: Request):
    user_id = getattr(request.state, "user_id", None)
    lock = FileLock(settings.LOCK_FILE)
    with lock:
        index = storage.get_projects_index()
        project = get_user_project(index, project_id, user_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
            
    project_path = os.path.join(settings.PROJECTS_DIR, project_id)
    raw_transcript_path = os.path.join(project_path, "audio.mp3_raw.json")

    service = SubtitleService()
    words = service.load_raw_transcript(raw_transcript_path)

    if not words:
        # Fallback to index.json if raw is missing
        lock = FileLock(settings.LOCK_FILE)
        with lock:
            index = storage.get_projects_index()
            project = get_user_project(index, project_id, user_id)
            if project and "transcript" in project:
                from app.api.models import SubtitleWord

                words = [
                    SubtitleWord(**w) for w in project["transcript"].get("words", [])
                ]

    if not words:
        raise HTTPException(
            status_code=400, detail="Transcript words not found in project"
        )

    ass_content = service.generate_animated_ass(words, options.model_dump())

    from fastapi.responses import Response

    return Response(
        content=ass_content,
        media_type="text/x-ssa",
        headers={
            "Content-Disposition": f"attachment; filename=subtitles_{project_id}.ass"
        },
    )
