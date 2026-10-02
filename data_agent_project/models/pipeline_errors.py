from enum import Enum
from models.execution_results import ToolStatus

class PipelineStage(str,Enum):
    SCHEMA_EXTRACTION = "schema_extraction"
    CODE_GENERATION = "code_generation"
    SANDBOX_EXECUTION = "sandbox_execution"
    CRITIC_EVALUATION = "critic_evaluation"
    SUMMARIZATION = "summarization"
    MEMORY_PERSISTENCE = "memory_persistence"


class BaseToolException(Exception):
    """Base exception for all tools. Forces the tool to declare its failure status."""
    def __init__(self, message: str, status: ToolStatus, **metadata):
        super().__init__(message)
        self.status = status
        self.metadata = metadata  # This catches 'stage', 'query', etc.

class PipelineException(BaseToolException):
    def __init__(self, message: str, stage: PipelineStage, is_fatal: bool = True):
        # Determine the intensity right here in the domain logic
        mapped_status = ToolStatus.FATAL_ERROR if is_fatal else ToolStatus.RECOVERABLE_ERROR
        
        # Pass it up to the base class, attaching the stage as metadata
        super().__init__(message, status=mapped_status, stage=stage)