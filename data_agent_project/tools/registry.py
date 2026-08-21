from core.logger import get_logger
from typing import Callable,Any,Dict,List
import inspect
import functools
from models.execution_results import ToolExecutionResult

logger=get_logger(__name__)


class ToolRegistry:
    """
    A central switchboard for AI tools. 
    It holds Python functions and executes them dynamically when the LLM requests them.
    """
    def __init__(self):
        # Stores tools mapped by scope: {"global": [func1, func2], "sql": [func3]}
        self.tools_by_scope: Dict[str, List[Callable]] = {}
        # Stores the original functions by name so we can execute them later
        self.tool_functions: Dict[str, Callable] = {}

    def register(self, scope: str = "global"):
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
                return func(*args, **kwargs)

            # Assign masked signature so genai SDK reflection ignores '__' parameters
            wrapper.__signature__ = public_sig

            if scope not in self.   tools_by_scope:
                self.tools_by_scope[scope] = []

            self.tools_by_scope[scope].append(wrapper)
            self.tool_functions[tool_name] = func

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
                tools.extend(self.tools_by_scope[scope])
        return tools


    def execute_tool(self, tool_name: str, arguments: Dict[str, Any], session_state: Any = None,memory:Any=None) -> ToolExecutionResult:
        """
        Executes a registered tool by name. Injects session_state if '__session' is required.
        """
        if tool_name not in self.tool_functions:
            error_msg = f"Tool '{tool_name}' is not registered."
            logger.error(error_msg)
            return ToolExecutionResult.failure(tool_name="No tool Found",error_msg=str(e))
            

        func = self.tool_functions[tool_name]
        kwargs = dict(arguments) if arguments else {}

        # Inspect raw target function for hidden context injection
        sig = inspect.signature(func)
        if "__session" in sig.parameters:
            kwargs["__session"] = session_state

        if "__memory" in sig.parameters:
            kwargs["__memory"] = memory

        try:
            logger.info(f"Executing tool '{tool_name}' with args: {arguments}")
            result=func(**kwargs)
            return ToolExecutionResult.ok(tool_name=tool_name,output=result)
        except Exception as e:
            logger.error(f"Execution failed for tool '{tool_name}': {str(e)}")
            return ToolExecutionResult.failure(tool_name=tool_name,error_msg=str(e))

    
    def list_tool_names(self,scopes=None):

        if scopes is None:
            scopes=self.tools_by_scope.keys()

        names=[]

        for scope in scopes:
            for tool in self.tools_by_scope.get(scope,[]):
                names.append(tool.__name__)

        return names
            

# We create a single global instance of the registry for the application to share
registry = ToolRegistry()



