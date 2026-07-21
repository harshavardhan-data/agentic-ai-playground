import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from core.logger import get_logger

logger = get_logger(__name__)

# Force absolute navigation to the project folder
base_dir = Path(__file__).resolve().parent.parent.parent
env_path = base_dir / ".env"

# SDE Best Practice: use override=True to stamp out any stale or empty background env keys
load_dotenv(dotenv_path=env_path, override=True)

def _initialize_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error(f"Missing GEMINI_API_KEY. Searched path: {env_path.resolve()}")
        raise ValueError(f"GEMINI_API_KEY not found at: {env_path.resolve()}")
        
    logger.info("Gemini API Client successfully initialized.")
    return genai.Client(api_key=api_key)

gemini_client = _initialize_client()