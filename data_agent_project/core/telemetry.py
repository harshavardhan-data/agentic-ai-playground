from functools import wraps
import time
from core.logger import get_logger

logger=get_logger(__name__)

def log_call(func):

    @wraps(func)
    def wrapper(*args,**kwargs):
        start=time.perf_counter()
        try:
            result=func(*args,**kwargs)
            elapsed_ms=round((time.perf_counter() - start)*1000,2)
            logger.info(f"{func.__qualname__} succeeded",extra={"extra_data":{"duration_ms":elapsed_ms}})
            return result
        except Exception as e:
            elapsed_ms=round((time.perf_counter() - start)*1000,2)
            logger.warning(f"{func.__qualname__} raised",extra={"extra_data":{"duration_ms":elapsed_ms,"error":str(e)}})
            raise
    return wrapper
    


def _extract_gemini_usage(response) -> dict:
    """Gemini-specific: knows exactly where Gemini hides its token counts."""
    usage = getattr(response, "usage_metadata", None)
    if not usage:
        return {}
    return {
        "prompt_tokens": getattr(usage, "prompt_token_count", 0),
        "output_tokens": getattr(usage, "candidates_token_count", 0),
        "total_tokens": getattr(usage, "total_token_count", 0),
    }



def log_token_usage(response,agent_name:str,provider:str="gemini") -> None:
    """
    The ONE function every agent calls. It doesn't care which provider —
    it just picks the right extractor and logs a consistent shape.
    """
    extractors = {
        "gemini": _extract_gemini_usage,
        # "openai": _extract_openai_usage,   
    }
    extractor = extractors.get(provider)
    if not extractor:
        return

    usage = extractor(response)
    if not usage:
        return

    logger.info(f"{agent_name} token usage", extra={"extra_data": {**usage, "provider": provider}})