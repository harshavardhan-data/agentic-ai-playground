from dataclasses import dataclass
from core.memory import SessionState,BaseSessionStore
from google import genai

@dataclass
class ToolContext:
    session:SessionState
    memory: BaseSessionStore
    client: genai.Client = None