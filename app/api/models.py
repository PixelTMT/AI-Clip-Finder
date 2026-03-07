from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from enum import Enum


class OperationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class OperationType(str, Enum):
    UPLOAD = "upload"
    TRANSCRIBE = "transcribe"
    FIND_CLIPS = "find_clips"


class OperationDetails(BaseModel):
    type: OperationType
    status: OperationStatus
    progress: float = 0.0
    message: Optional[str] = None


class ProjectCreate(BaseModel):
    name: str


class Project(BaseModel):
    project_id: str
    name: str
    user_id: Optional[str] = None
    created_at: Optional[str] = None
    status: str = "created"
    error: Optional[str] = None
    clips: Optional[List[Dict[str, Any]]] = None
    transcript: Optional[Dict[str, Any]] = None
    custom_prompt: Optional[str] = None
    clip_count: Optional[int] = None
    active_operation: Optional[OperationDetails] = None


class SubtitleWord(BaseModel):
    word: str
    start: float
    end: float


class ClipExportRequest(BaseModel):
    project_id: str
    clip_index: int
    start_offset: float = 0.0
    end_offset: float = 0.0
    font_family: str = "Inter"
    font_size: str = "Medium"
    font_color: str = "#FFFFFF"
    text_style: str = "Outline"
    subtitle_position: str = "Bottom"


class ClipExportResponse(BaseModel):
    status: str
    progress: float
    output_path: Optional[str] = None
    download_url: Optional[str] = None


class ASSOptions(BaseModel):
    bg_color: str = "&H000000FF"
    text_color: str = "&H00FFFFFF"
    font_size: int = 48
    pulse_scale: float = 1.2
    alignment: int = 2
