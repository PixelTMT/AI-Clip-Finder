from datetime import datetime, timezone
import json
import os
import uuid
from filelock import FileLock
from app.core.config import settings


def get_projects_index():
    if not os.path.exists(settings.PROJECTS_INDEX):
        return {}
    with open(settings.PROJECTS_INDEX, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_projects_index(index):
    with open(settings.PROJECTS_INDEX, "w") as f:
        json.dump(index, f, indent=4)


def create_project_entry(name: str, user_id: str = None) -> dict:
    project_id = str(uuid.uuid4())
    project_path = os.path.join(settings.PROJECTS_DIR, project_id)
    os.makedirs(project_path, exist_ok=True)

    new_project = {
        "project_id": project_id,
        "name": name,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "created",
        "error": None,
    }

    lock = FileLock(settings.LOCK_FILE)
    with lock:
        index = get_projects_index()
        index[project_id] = new_project
        save_projects_index(index)

    return new_project


import shutil


def delete_project_entry(project_id: str):
    lock = FileLock(settings.LOCK_FILE)
    with lock:
        index = get_projects_index()
        if project_id in index:
            del index[project_id]
            save_projects_index(index)

    project_path = os.path.join(settings.PROJECTS_DIR, project_id)
    if os.path.exists(project_path):
        shutil.rmtree(project_path)


def update_project_status(project_id: str, status: str, error: str = None):
    lock = FileLock(settings.LOCK_FILE)
    with lock:
        index = get_projects_index()
        if project_id in index:
            index[project_id]["status"] = status
            index[project_id]["error"] = error
            save_projects_index(index)


def set_active_operation(
    project_id: str, type: str, status: str, progress: float = 0.0, message: str = None
):
    lock = FileLock(settings.LOCK_FILE)
    with lock:
        index = get_projects_index()
        if project_id in index:
            index[project_id]["active_operation"] = {
                "type": type,
                "status": status,
                "progress": progress,
                "message": message,
            }
            save_projects_index(index)


def clear_active_operation(project_id: str):
    lock = FileLock(settings.LOCK_FILE)
    with lock:
        index = get_projects_index()
        if project_id in index:
            index[project_id]["active_operation"] = None
            save_projects_index(index)
