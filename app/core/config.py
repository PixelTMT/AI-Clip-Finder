import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Settings:
    DATA_DIR = "data"
    PROJECTS_DIR = os.path.join(DATA_DIR, "projects")
    PROJECTS_INDEX = os.path.join(DATA_DIR, "projects.json")
    LOCK_FILE = os.path.join(DATA_DIR, "projects.json.lock")
    
    # LLM Settings
    LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://gen.pollinations.ai/v1")
    LLM_MODEL = os.environ.get("LLM_MODEL", "openai")
    # Server-side LLM credentials. When present, BYOP is disabled: the server
    # authenticates the calls and the operator pays.
    LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
    POLLINATIONS_APP_KEY = os.environ.get("POLLINATIONS_APP_KEY", "")
    # Hosting & Limits
    HOSTING = os.environ.get("HOSTING", "false").lower() == "true"
    # BYOP (Bring Your Own Pollen) is only active for multi-tenant deployments
    # that have no server-side LLM credentials to fall back on.
    BYOP = HOSTING and not LLM_API_KEY
    MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
    PROJECT_EXPIRY_DAYS = 30
    USER_ID_COOKIE = "user_id"
    def __init__(self):
        os.makedirs(self.PROJECTS_DIR, exist_ok=True)
        if not self.BYOP and not self.LLM_API_KEY:
            logger.warning(
                "BYOP disabled and LLM_API_KEY is not set: AI calls will fail "
                "with 401. Set LLM_API_KEY or enable HOSTING=true."
            )

settings = Settings()
