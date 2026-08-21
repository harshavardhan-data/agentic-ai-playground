import uuid
import threading
import pandas as pd
from io import StringIO
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel, Field
from core.router import route_query
from core.memory import InMemorySessionStore
from core.sqlite_memory import SqliteSessionStore

app = FastAPI(title="Data Analyst Agent API")

# One shared store for the entire lifetime of the server process —
# same idea as gemini_client being a singleton, just for session data instead.
memory_store = SqliteSessionStore()

# See explanation below — guards against two requests creating/reading
# a session at the exact same instant.
# _session_lock = threading.Lock()


class DatabaseUploadRequest(BaseModel):
    db_path:str


class QueryRequest(BaseModel):
    session_id: str = Field(..., description="Session id returned by POST /sessions")
    user_query: str = Field(..., description="The user's natural language question")


class QueryResponse(BaseModel):
    result: Optional[str]
    success: bool


class SessionResponse(BaseModel):
    session_id: str




@app.post("/sessions", response_model=SessionResponse)
def create_session():
    """Call this ONCE at the start of a conversation to get a session_id."""
    session_id = str(uuid.uuid4())
    memory_store.get_session(session_id)  
    return SessionResponse(session_id=session_id)


@app.post("/sessions/{session_id}/upload")
async def upload_csv(session_id: str, file: UploadFile = File(...)):
    """Upload the CSV once per session, before the first /query call."""
    raw_bytes = await file.read()
    try:
        df = pd.read_csv(StringIO(raw_bytes.decode("utf-8")))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}")

    memory_store.update_sandbox_state(session_id,"df",df)
    

    return {"status": "ok", "rows": len(df), "columns": list(df.columns)}


@app.post("/sessions/{session_id}/upload-db")
def upload_db(session_id:str,request:DatabaseUploadRequest):
    try:
        memory_store.update_sandbox_state(session_id,"db_path",request.db_path)
        return {"status":"ok"}
    except Exception as e:
        raise HTTPException(status_code=400,detail=str(e))


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    
    session = memory_store.get_session(request.session_id)

    print("SESSION:", session.session_id)
    print("STATE:", session.sandbox_state)

    try:
        result=route_query(
            session=session,
            user_query=request.user_query,
            memory=memory_store
        )
        if result is None:
            return QueryResponse(result=None,success=False)

        return QueryResponse(result=result,success=True)
    
    except ValueError as e:
        raise HTTPException(status_code=400,detail=str(e))

    