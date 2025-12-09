"""
Timeout utilities for AI service calls.

Prevents AI calls from hanging indefinitely and affecting user experience.
"""

import asyncio
import logging
from typing import TypeVar, Callable, Any
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')

# Default timeout for AI operations (in seconds)
DEFAULT_AI_TIMEOUT = 120  # 2 minutes


class AITimeoutError(Exception):
    """Raised when an AI operation times out."""
    
    def __init__(self, operation: str, timeout: int):
        self.operation = operation
        self.timeout = timeout
        super().__init__(f"AI operation '{operation}' timed out after {timeout}s")


async def with_timeout(
    coro,
    timeout_seconds: int = DEFAULT_AI_TIMEOUT,
    operation_name: str = "AI operation"
) -> Any:
    """
    Execute an async coroutine with a timeout.
    
    Args:
        coro: The coroutine to execute
        timeout_seconds: Maximum time to wait (default: 120s)
        operation_name: Name of the operation for logging
        
    Returns:
        The result of the coroutine
        
    Raises:
        AITimeoutError: If the operation times out
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.error(f"Timeout: {operation_name} exceeded {timeout_seconds}s limit")
        raise AITimeoutError(operation_name, timeout_seconds)


def timeout_decorator(timeout_seconds: int = DEFAULT_AI_TIMEOUT, operation_name: str = None):
    """
    Decorator to add timeout to async functions.
    
    Usage:
        @timeout_decorator(60, "Research completion")
        async def complete_research():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            return await with_timeout(
                func(*args, **kwargs),
                timeout_seconds=timeout_seconds,
                operation_name=op_name
            )
        return wrapper
    return decorator


# Convenience functions for common AI operations
async def claude_with_timeout(coro, timeout: int = 60):
    """Execute Claude API call with timeout."""
    return await with_timeout(coro, timeout, "Claude API call")


async def gemini_with_timeout(coro, timeout: int = 60):
    """Execute Gemini API call with timeout."""
    return await with_timeout(coro, timeout, "Gemini API call")


async def research_with_timeout(coro, timeout: int = 180):
    """Execute research operation with timeout (3 min max)."""
    return await with_timeout(coro, timeout, "Research generation")


async def transcription_with_timeout(coro, timeout: int = 300):
    """Execute transcription with timeout (5 min max for long audio)."""
    return await with_timeout(coro, timeout, "Audio transcription")

