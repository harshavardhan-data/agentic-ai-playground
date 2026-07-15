from abc import ABC,abstractmethod
from typing import List,Dict,Any
from pydantic import BaseModel

class MemoryTurn(BaseModel):
    user_query:str
    successful_code:str
    execution_output:str

class BaseMemoryManager(ABC):
    @abstractmethod
    def get_history(self,session_id:str) -> List[MemoryTurn]:
        pass

    @abstractmethod
    def add_turn(self,session_id:str,turn:MemoryTurn) -> None:
        pass

class InMemoryMemoryManager(BaseMemoryManager):

    def __init__(self,max_turns:int=5):
        self._storage:Dict[str,List[MemoryTurn]]={}
        self.max_turns=max_turns

    def get_history(self, session_id:str) -> List[MemoryTurn]:
        return self._storage.get(session_id,[])
    
    def add_turn(self, session_id:str, turn:MemoryTurn) -> None:
        if session_id not in self._storage:
            self._storage[session_id]=[]
        
        history=self._storage[session_id]
        history.append(turn)

        # Enforce our context budget boundary (FIFO eviction)
        if len(history)>self.max_turns:
            history.pop(0)