"""
Cleanup service for removing orphan test projects.

Orphan projects are identified by checking the project name in projects.json.
Real projects have names ending with video extensions (e.g., "video.mp4").
Test scripts create projects with names like "Test Project", "Upload Test".
"""

import json
from datetime import datetime, timezone
import os
import shutil
import logging
from typing import List
from filelock import FileLock
from app.core.config import settings

logger = logging.getLogger(__name__)

# Video file extensions that indicate a real project
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v"}


def is_test_project_name(name: str) -> bool:
    """
    Check if a project name indicates a test project (not a video file).

    Args:
        name: The project name from projects.json.

    Returns:
        True if the name does NOT end with a video extension (test project).
    """
    if not name:
        return True

    _, ext = os.path.splitext(name.lower())
    return ext not in VIDEO_EXTENSIONS


def get_orphan_project_ids() -> List[str]:
    """
    Read projects.json and identify orphan test projects by name.

    Returns:
        List of project_ids that are test/orphan projects.
    """
    orphans = []

    if not os.path.exists(settings.PROJECTS_INDEX):
        return orphans

    try:
        with open(settings.PROJECTS_INDEX, "r") as f:
            index = json.load(f)
    except (json.JSONDecodeError, IOError):
        return orphans

    for project_id, project_data in index.items():
        name = project_data.get("name", "")
        if is_test_project_name(name):
            orphans.append(project_id)

    return orphans


def reset_stale_operations() -> int:
    """
    Reset operations that were left in 'running' state due to server restart.

    Returns:
        Number of operations reset.
    """
    reset_count = 0
    lock = FileLock(settings.LOCK_FILE)

    with lock:
        if not os.path.exists(settings.PROJECTS_INDEX):
            return 0

        try:
            with open(settings.PROJECTS_INDEX, "r") as f:
                index = json.load(f)
        except (json.JSONDecodeError, IOError):
            return 0

        modified = False
        for project_id, project in index.items():
            op = project.get("active_operation")
            if op and op.get("status") in ["running", "pending"]:
                # Mark operation as failed
                project["active_operation"] = {
                    "type": op.get("type"),
                    "status": "failed",
                    "progress": op.get("progress", 0),
                    "message": "Operation interrupted by server restart",
                }
                # Also update main project status if it looks like it was busy
                if project.get("status") in [
                    "uploading",
                    "transcribing",
                    "analyzing",
                    "compressing",
                ]:
                    project["status"] = "error"
                    project["error"] = "Operation interrupted by server restart"

                reset_count += 1
                modified = True
                logger.info(f"Reset stale operation for project {project_id}")

        if modified:
            try:
                with open(settings.PROJECTS_INDEX, "w") as f:
                    json.dump(index, f, indent=4)
            except IOError as e:
                logger.error(f"Failed to save index after resetting operations: {e}")

    return reset_count


def cleanup_orphan_projects() -> int:
    """
    Remove all orphan test projects from the filesystem and projects index.

    This function is designed to run at application startup to clean up
    test artifacts. Orphan projects are identified by checking if the
    project name ends with a video extension - test scripts typically
    use names like "Test Project" while real uploads have names like "video.mp4".

    Returns:
        Number of orphan projects removed.
    """
    orphan_ids = get_orphan_project_ids()

    if not orphan_ids:
        logger.info("No orphan projects found during cleanup.")
        return 0

    removed_count = 0
    lock = FileLock(settings.LOCK_FILE)

    with lock:
        # Load index
        index = {}
        if os.path.exists(settings.PROJECTS_INDEX):
            try:
                with open(settings.PROJECTS_INDEX, "r") as f:
                    index = json.load(f)
            except (json.JSONDecodeError, IOError):
                index = {}

        for project_id in orphan_ids:
            try:
                # Remove directory if exists
                project_path = os.path.join(settings.PROJECTS_DIR, project_id)
                if os.path.exists(project_path):
                    shutil.rmtree(project_path)
                    logger.info(f"Removed orphan project directory: {project_id}")

                # Remove from index
                if project_id in index:
                    project_name = index[project_id].get("name", "unknown")
                    del index[project_id]
                    logger.info(
                        f"Removed orphan project from index: {project_id} "
                        f"(name: {project_name})"
                    )

                removed_count += 1
            except Exception as e:
                logger.error(f"Failed to remove orphan project {project_id}: {e}")

        # Save updated index
        if removed_count > 0:
            try:
                with open(settings.PROJECTS_INDEX, "w") as f:
                    json.dump(index, f, indent=4)
            except IOError as e:
                logger.error(f"Failed to save projects index after cleanup: {e}")

    logger.info(f"Cleanup complete. Removed {removed_count} orphan project(s).")
    return removed_count

def cleanup_expired_projects() -> int:
    """
    Remove projects older than settings.PROJECT_EXPIRY_DAYS if settings.HOSTING is enabled.
    """
    if not settings.HOSTING:
        return 0

    expired_count = 0
    now = datetime.now(timezone.utc)

    lock = FileLock(settings.LOCK_FILE)
    with lock:
        if not os.path.exists(settings.PROJECTS_INDEX):
            return 0

        try:
            with open(settings.PROJECTS_INDEX, "r") as f:
                index = json.load(f)
        except (json.JSONDecodeError, IOError):
            return 0

        modified = False
        to_delete = []

        for project_id, project in index.items():
            created_at_str = project.get("created_at")
            if not created_at_str:
                continue

            try:
                created_at = datetime.fromisoformat(created_at_str)
                age = now - created_at
                if age.days >= settings.PROJECT_EXPIRY_DAYS:
                    to_delete.append(project_id)
            except ValueError:
                # Skip projects with non-ISO timestamps (old format)
                continue

        for project_id in to_delete:
            try:
                project_path = os.path.join(settings.PROJECTS_DIR, project_id)
                if os.path.exists(project_path):
                    shutil.rmtree(project_path)
                del index[project_id]
                expired_count += 1
                modified = True
                logger.info(f"Cleaned up expired project: {project_id}")
            except Exception as e:
                logger.error(f"Failed to cleanup expired project {project_id}: {e}")

        if modified:
            try:
                with open(settings.PROJECTS_INDEX, "w") as f:
                    json.dump(index, f, indent=4)
            except IOError as e:
                logger.error(f"Failed to save index after cleanup: {e}")

    return expired_count