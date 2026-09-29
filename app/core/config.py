import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    """Reads an integer environment variable.

    Args:
        name: Environment variable name.
        default: Value returned when the variable is unset or unparsable.

    Returns:
        The parsed integer, or ``default`` when the value is invalid.
    """
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.error("Invalid %s=%r (expected int), using %d", name, raw, default)
        return default


class Settings:
    #: Valid values for ``MEDIA_COMPRESS_MODE``.
    MEDIA_COMPRESS_MODES = ("always", "auto", "never")

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

    # Media processing. "always" re-encodes every upload (historical behavior),
    # "auto" re-encodes only when ffprobe reports a non-web-playable file,
    # "never" always passthroughs the uploaded file into processed.mp4.
    MEDIA_COMPRESS_MODE = os.environ.get("MEDIA_COMPRESS_MODE", "always").strip().lower()
    MEDIA_CRF = _env_int("MEDIA_CRF", 32)
    MEDIA_PRESET = os.environ.get("MEDIA_PRESET", "").strip()
    MEDIA_AUDIO_BITRATE = os.environ.get("MEDIA_AUDIO_BITRATE", "128k").strip()

    def __init__(self):
        os.makedirs(self.PROJECTS_DIR, exist_ok=True)
        if self.MEDIA_COMPRESS_MODE not in self.MEDIA_COMPRESS_MODES:
            logger.error(
                "Invalid MEDIA_COMPRESS_MODE=%r (expected one of %s): "
                "falling back to 'always'.",
                self.MEDIA_COMPRESS_MODE,
                ", ".join(self.MEDIA_COMPRESS_MODES),
            )
            self.MEDIA_COMPRESS_MODE = "always"

        if not self.BYOP and not self.LLM_API_KEY:
            logger.warning(
                "BYOP disabled and LLM_API_KEY is not set: AI calls will fail "
                "with 401. Set LLM_API_KEY or enable HOSTING=true."
            )

settings = Settings()
