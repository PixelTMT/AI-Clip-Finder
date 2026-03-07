import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DATA_DIR = "data"
    PROJECTS_DIR = os.path.join(DATA_DIR, "projects")
    PROJECTS_INDEX = os.path.join(DATA_DIR, "projects.json")
    LOCK_FILE = os.path.join(DATA_DIR, "projects.json.lock")
    
    # LLM Settings
    LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://gen.pollinations.ai/v1")
    LLM_MODEL = os.environ.get("LLM_MODEL", "openai-large")
    LLM_API_KEY = os.environ.get("LLM_API_KEY", "dummy") # Pollinations doesn't check keys but client needs one
    # Hosting & Limits
    HOSTING = os.environ.get("HOSTING", "false").lower() == "true"
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    PROJECT_EXPIRY_DAYS = 30
    USER_ID_COOKIE = "user_id"
    def __init__(self):
        os.makedirs(self.PROJECTS_DIR, exist_ok=True)

settings = Settings()
