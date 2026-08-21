from abc import ABC,abstractmethod
from typing import List,Dict,Any
from pydantic import BaseModel,Field,ConfigDict

class MemoryTurn(BaseModel):
    user_query:str
    successful_code:str
    execution_output:str
    summary:str

class SessionState(BaseModel):
    session_id : str =""
    history:List[MemoryTurn]=Field(default_factory=list)
    sandbox_state:Dict[str,Any]=Field(default_factory=dict)

    model_config=ConfigDict(arbitrary_types_allowed=True)


class BaseSessionStore(ABC):
    @abstractmethod
    def get_session(self,session_id:str) -> SessionState:
        pass

    @abstractmethod
    def add_turn(self,session:SessionState,turn:MemoryTurn) -> None:
        pass

    @abstractmethod
    def update_sandbox_state(self, session_id: str, key: str, value: Any) -> None:
        pass

class InMemorySessionStore(BaseSessionStore):

    def __init__(self,max_turns:int=5):
        self._storage:Dict[str,SessionState]={}
        self.max_turns=max_turns

    def get_session(self, session_id:str) -> SessionState:
        if session_id not in self._storage:
            self._storage[session_id]=SessionState(session_id=session_id)
        return self._storage[session_id]
    
    def add_turn(self, session:SessionState, turn:MemoryTurn) -> None:
        
        session=self.get_session(session.session_id)
        session.history.append(turn)

        # Enforce our context budget boundary (FIFO eviction)
        if len(session.history)>self.max_turns:
            session.history.pop(0)

    def update_sandbox_state(self, session_id, key, value):
        session=self.get_session(session_id)
        session.sandbox_state[key]=value