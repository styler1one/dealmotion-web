"""
Utility modules for the DealMotion backend.
"""

from .timeout import (
    with_timeout,
    timeout_decorator,
    claude_with_timeout,
    gemini_with_timeout,
    research_with_timeout,
    transcription_with_timeout,
    AITimeoutError,
    DEFAULT_AI_TIMEOUT,
)

from .errors import (
    handle_exception,
    raise_not_found,
    raise_forbidden,
    raise_validation_error,
    AppError,
    ErrorCodes,
)

__all__ = [
    # Timeout utilities
    "with_timeout",
    "timeout_decorator",
    "claude_with_timeout",
    "gemini_with_timeout",
    "research_with_timeout",
    "transcription_with_timeout",
    "AITimeoutError",
    "DEFAULT_AI_TIMEOUT",
    # Error handling utilities
    "handle_exception",
    "raise_not_found",
    "raise_forbidden",
    "raise_validation_error",
    "AppError",
    "ErrorCodes",
]

