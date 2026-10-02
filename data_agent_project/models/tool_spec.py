from dataclasses import dataclass
from typing import Callable, Type
from pydantic import BaseModel

@dataclass
class ToolSpec:
    name: str
    scope: str
    function: Callable
    input_schema: Type[BaseModel]
    target: Callable
