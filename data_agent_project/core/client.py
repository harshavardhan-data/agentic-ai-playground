from dotenv import load_dotenv
from google import genai
import os

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY not found in environment configurations")

client = genai.Client(api_key=api_key)