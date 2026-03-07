from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from filelock import FileLock
from fastapi.responses import FileResponse
from typing import Dict
import uuid
import os

from app.api.models import ClipExportRequest, ClipExportResponse, SubtitleWord
from app.services.subtitle_service import SubtitleService
from app.services.clip_render_service import ClipRenderService
from app.core.config import settings
from app.services import storage

router = APIRouter(prefix="/api/clips", tags=["clips"])

# In-memory store
render_tasks: Dict[str, ClipExportResponse] = {}

subtitle_service = SubtitleService()
clip_render_service = ClipRenderService()


def run_render_task(task_id: str, request: ClipExportRequest, is_preview: bool):
    try:
        render_tasks[task_id].status = "processing"
        render_tasks[task_id].progress = 0.1

        # 1. Get Project & Paths
        project_path = os.path.join(settings.PROJECTS_DIR, request.project_id)
        if not os.path.exists(project_path):
            raise FileNotFoundError("Project not found")

        # Source video
        input_filename = "processed.mp4" if is_preview else "original.mp4"
        input_path = os.path.join(project_path, input_filename)

        # Output filename
        output_filename = f"clip_{request.clip_index}_{task_id}_{'preview' if is_preview else 'final'}.mp4"
        output_path = os.path.join(project_path, output_filename)

        # 2. Get Subtitles
        transcript_path = os.path.join(project_path, "audio.mp3_raw.json")
        all_words = subtitle_service.load_raw_transcript(transcript_path)

        # 3. Determine Time Range
        projects = storage.get_projects_index()
        project_data = projects.get(request.project_id)
        if not project_data or "clips" not in project_data:
            raise ValueError("Project or clips not found")

        clips = project_data.get("clips", [])
        if request.clip_index < 0 or request.clip_index >= len(clips):
            raise ValueError("Invalid clip index")

        clip = clips[request.clip_index]
        base_start = clip.get("start_time", 0.0)
        base_end = clip.get("end_time", 0.0)

        final_start = max(0.0, base_start + request.start_offset)
        final_end = max(
            final_start + 0.5, base_end + request.end_offset
        )  # Min duration 0.5s

        # 4. Filter Words & Generate ASS
        render_tasks[task_id].progress = 0.3
        clip_words = subtitle_service.filter_by_timerange(
            all_words, final_start, final_end
        )

        # Shift timestamps relative to clip start
        shifted_words = []
        for w in clip_words:
            shifted_words.append(
                SubtitleWord(
                    word=w.word, start=w.start - final_start, end=w.end - final_start
                )
            )

        ass_path = output_path + ".ass"
        clip_render_service.generate_ass_file(shifted_words, request, ass_path)

        # 5. Render
        render_tasks[task_id].progress = 0.5
        clip_render_service.render_video(
            input_path, output_path, ass_path, final_start, final_end
        )

        # Cleanup ASS
        if os.path.exists(ass_path):
            os.remove(ass_path)

        # Complete
        render_tasks[task_id].progress = 1.0
        render_tasks[task_id].status = "completed"
        render_tasks[task_id].output_path = output_path
        render_tasks[task_id].download_url = f"/api/clips/download/{task_id}"

    except Exception as e:
        render_tasks[task_id].status = "failed"
        render_tasks[task_id].progress = 0.0
        # Log error in real app


@router.post("/render-preview", status_code=202)
async def render_preview(request: ClipExportRequest, background_tasks: BackgroundTasks, req: Request):
    user_id = getattr(req.state, "user_id", None)
    lock = FileLock(settings.LOCK_FILE)
    with lock:
        index = storage.get_projects_index()
        project = index.get(request.project_id)
        if not project:
             raise HTTPException(status_code=404, detail="Project not found")
        if settings.HOSTING and project.get("user_id") != user_id:
             raise HTTPException(status_code=403, detail="Forbidden")
    
    task_id = str(uuid.uuid4())
    render_tasks[task_id] = ClipExportResponse(status="queued", progress=0.0)
    # Store user_id in task metadata if needed, or just rely on project check in task
    background_tasks.add_task(run_render_task, task_id, request, is_preview=True)
    return {"task_id": task_id}


@router.post("/render-final", status_code=202)
async def render_final(request: ClipExportRequest, background_tasks: BackgroundTasks, req: Request):
    user_id = getattr(req.state, "user_id", None)
    lock = FileLock(settings.LOCK_FILE)
    with lock:
        index = storage.get_projects_index()
        project = index.get(request.project_id)
        if not project:
             raise HTTPException(status_code=404, detail="Project not found")
        if settings.HOSTING and project.get("user_id") != user_id:
             raise HTTPException(status_code=403, detail="Forbidden")
    
    task_id = str(uuid.uuid4())
    render_tasks[task_id] = ClipExportResponse(status="queued", progress=0.0)
    background_tasks.add_task(run_render_task, task_id, request, is_preview=False)
    return {"task_id": task_id}


@router.get("/render-status/{task_id}", response_model=ClipExportResponse)
async def get_render_status(task_id: str):
    task = render_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/download/{task_id}")
async def download_clip(task_id: str):
    task = render_tasks.get(task_id)
    if not task or task.status != "completed" or not task.output_path:
        raise HTTPException(status_code=404, detail="Clip not ready or found")
    return FileResponse(task.output_path, filename=os.path.basename(task.output_path))
