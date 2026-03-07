import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from app.api.endpoints import router
from app.api.clip_endpoints import router as clip_router
from app.core.config import settings
from app.services.cleanup import cleanup_orphan_projects, reset_stale_operations, cleanup_expired_projects
import asyncio
from app.middleware import HostingMiddleware

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
async def periodic_cleanup():
    """Run cleanup tasks periodically."""
    while True:
        try:
            # 3. Cleanup expired projects if hosting is enabled
            expired_count = cleanup_orphan_projects() # Existing cleanup
            if expired_count > 0:
                logger.info(f"Background task: Cleaned up {expired_count} orphan project(s)")
            
            if settings.HOSTING:
                expired_count = cleanup_expired_projects()
                if expired_count > 0:
                    logger.info(f"Background task: Cleaned up {expired_count} expired project(s)")
        except Exception as e:
            logger.error(f"Error in background periodic cleanup: {e}")
        await asyncio.sleep(3600)  # Check every hour



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup: Clean up orphan test projects
    logger.info("Starting application cleanup...")

    # 1. Reset stale operations from previous run
    reset_count = reset_stale_operations()
    if reset_count > 0:
        logger.info(f"Reset {reset_count} stale operations from previous session")

    # 2. Cleanup orphan test projects
    removed_count = cleanup_orphan_projects()
    if removed_count > 0:
        logger.info(f"Cleaned up {removed_count} orphan test project(s)")

    # 3. Start periodic cleanup task in background
    asyncio.create_task(periodic_cleanup())

    yield
    # Shutdown: nothing to do for now


app = FastAPI(title="AI-clip Discovery API", lifespan=lifespan)

# Add hosting middleware
app.add_middleware(HostingMiddleware)

# Mount project data for direct file access (videos, thumbnails)
app.mount("/media", StaticFiles(directory=settings.PROJECTS_DIR), name="media")

# Mount frontend static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(router)
app.include_router(clip_router)
