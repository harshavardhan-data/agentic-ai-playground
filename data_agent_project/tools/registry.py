from core.logger import get_logger
from typing import Callable,Any,Dict,List
import inspect
import functools
from models.execution_results import ToolExecutionResult,ToolStatus
from pydantic import BaseModel,ValidationError
from models.tool_spec import ToolSpec
from models.tool_context import ToolContext
from models.pipeline_errors import BaseToolException


logger=get_logger(__name__)


class ToolRegistry:
    """
    A central switchboard for AI tools. 
    It holds Python functions and executes them dynamically when the LLM requests them.
    """
    def __init__(self):
        # Stores tools mapped by scope: {"global": [func1, func2], "sql": [func3]}
        self.tools_by_scope: Dict[str, List[ToolSpec]] = {}
        # Stores the original functions by name so we can execute them later
        self.tool_specs: Dict[str, ToolSpec] = {}

    def register(self, scope: str ,input_schema:BaseModel):
        """
        Decorator registering a tool under a given scope.
        Masks parameters starting with '__' from the tool's public signature.
        """
        def decorator(func: Callable) -> Callable:
            tool_name = func.__name__
            sig = inspect.signature(func)

            # Strip private parameters (starting with '__') from signature shown to Gemini SDK
            public_params = [
                p for p in sig.parameters.values() 
                if not p.name.startswith("__")
            ]
            public_sig = sig.replace(parameters=public_params)

            
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # return func(*args, **kwargs)      
                return func(*args,**kwargs)

            # Assign masked signature so genai SDK reflection ignores '__' parameters
            wrapper.__signature__ = public_sig

            spec=ToolSpec(name=tool_name,
                          scope=scope,
                          function=wrapper,
                          input_schema=input_schema,
                          target=func
                          )
            
            if scope not in self.tools_by_scope:
                self.tools_by_scope[scope] = []

            self.tools_by_scope.setdefault(scope,[]).append(spec)
            self.tool_specs[tool_name] = spec

            logger.info(f"Registered tool '{tool_name}' under scope '{scope}'")
            return wrapper

        return decorator

    def get_tools_for_scope(self, scopes: List[str]) -> List[Callable]:
        """
        Returns a flat list of functions for the requested scopes (e.g., ["global", "sql"]).
        """
        tools = []
        for scope in scopes:
            if scope in self.tools_by_scope:
                tools.extend(spec.function for spec in self.tools_by_scope[scope])
        return tools


    def execute_tool(self, tool_name: str, arguments: Dict[str, Any],tool_context:ToolContext=None) -> ToolExecutionResult:
        """
        Executes a registered tool by name. Injects session_state if '__session' is required.
        """
        if tool_name not in self.tool_specs:
            error_msg = f"Tool '{tool_name}' is not registered in the environment."
            logger.error(error_msg)
            return ToolExecutionResult.failure(tool_name="No tool Found",error_msg=error_msg,status=ToolStatus.CONFIGURATION_ERROR)
            

        spec = self.tool_specs[tool_name]
    
        
        try:
            logger.info(f"Executing tool '{tool_name}' with args: {arguments}")
            # Validate Gemini's arguments against the tool's input schema
            validated_input=spec.input_schema.model_validate(arguments or {})
            kwargs=validated_input.model_dump()

            logger.info(f"VALIDATED TOOL INPUTS SUCCESSFULLY FOR {spec.target.__name__}")
        except ValidationError as e:
            return ToolExecutionResult.failure(tool_name=tool_name,status=ToolStatus.VALIDATION_ERROR,error_msg=str(e),)



        if "__context" in inspect.signature(spec.target).parameters:
            if not tool_context:
                raise ValueError(f"Tool {tool_name} requires context injection, but none was provided by the orchestrator.")
            kwargs["__context"]=tool_context
            logger.info("Context INJECTION SUCCESFUL!!")

        try:
            result=spec.target(**kwargs)
            logger.info(f"TOOL EXECUTED SUCCESFULLY FOR {spec.target.__name__}")
            if isinstance(result,ToolExecutionResult):
                return result
            return ToolExecutionResult.ok(tool_name=tool_name,output=result,status=ToolStatus.SUCCESS)
        except BaseToolException as e:
            logger.error(
                f"Tool '{tool_name}' failed purposefully.", 
                extra={"error_status": e.status.value, "metadata": e.metadata}
            )
            return ToolExecutionResult.failure(tool_name=tool_name,error_msg=str(e),status=e.status.value)
        except Exception as e:
            # THIS is your true fallback for unhandled bugs (e.g., a TypeError, IndexError)
            logger.error(f"Unexpected crash in tool '{tool_name}'", exc_info=True)
            return ToolExecutionResult.failure(
                tool_name=tool_name, 
                error_msg=f"Internal tool execution failure", 
                status=ToolStatus.INTERNAL_ERROR 
            )
    
    def list_tool_names(self,scopes=None):

        if scopes is None:
            scopes=self.tools_by_scope.keys()

        names=[]

        for scope in scopes:
            for tool_spec in self.tools_by_scope.get(scope,[]):
                names.append(tool_spec.target.__name__)

        return names
            

# We create a single global instance of the registry for the application to share
registry = ToolRegistry()



