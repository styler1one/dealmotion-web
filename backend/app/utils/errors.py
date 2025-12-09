"""
Centralized error handling utilities for DealMotion API.

This module provides consistent error responses and logging across all routers.
"""

import logging
from typing import Optional, Dict, Any
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base application error with structured data."""
    
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


# Common error codes
class ErrorCodes:
    """Standard error codes for API responses."""
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    RATE_LIMITED = "RATE_LIMITED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    PROCESSING_FAILED = "PROCESSING_FAILED"
    UPLOAD_FAILED = "UPLOAD_FAILED"
    DATABASE_ERROR = "DATABASE_ERROR"


def handle_exception(
    error: Exception,
    operation: str,
    *,
    user_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    log_level: str = "error"
) -> HTTPException:
    """
    Handle exceptions and return appropriate HTTPException.
    
    This function:
    1. Logs the error with context for debugging
    2. Returns a user-friendly error message (not exposing internals)
    3. Preserves original HTTPExceptions
    
    Args:
        error: The caught exception
        operation: Description of what operation failed (e.g., "followup_upload")
        user_id: Optional user ID for context
        organization_id: Optional org ID for context
        resource_id: Optional resource ID for context
        log_level: Logging level ("error", "warning", "info")
    
    Returns:
        HTTPException with appropriate status code and message
    
    Example:
        try:
            # ... operation
        except HTTPException:
            raise
        except Exception as e:
            raise handle_exception(e, "research_start", user_id=user_id)
    """
    # Build context for logging
    context = {
        "operation": operation,
        "error_type": type(error).__name__,
        "error_message": str(error),
    }
    if user_id:
        context["user_id"] = user_id
    if organization_id:
        context["organization_id"] = organization_id
    if resource_id:
        context["resource_id"] = resource_id
    
    # Log the full error with context
    log_message = f"Error in {operation}: {error}"
    if log_level == "warning":
        logger.warning(log_message, extra=context, exc_info=True)
    elif log_level == "info":
        logger.info(log_message, extra=context)
    else:
        logger.error(log_message, extra=context, exc_info=True)
    
    # If it's already an HTTPException, preserve it
    if isinstance(error, HTTPException):
        return error
    
    # If it's an AppError, use its details
    if isinstance(error, AppError):
        return HTTPException(
            status_code=error.status_code,
            detail={
                "error": error.code,
                "message": error.message,
                "details": error.details
            }
        )
    
    # Map common exception types to appropriate responses
    error_mapping = _get_error_mapping(error, operation)
    
    return HTTPException(
        status_code=error_mapping["status_code"],
        detail={
            "error": error_mapping["code"],
            "message": error_mapping["message"]
        }
    )


def _get_error_mapping(error: Exception, operation: str) -> Dict[str, Any]:
    """Map exception types to user-friendly error responses."""
    error_type = type(error).__name__
    error_str = str(error).lower()
    
    # Database/connection errors
    if "connection" in error_str or "timeout" in error_str:
        return {
            "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
            "code": ErrorCodes.SERVICE_UNAVAILABLE,
            "message": "Service temporarily unavailable. Please try again."
        }
    
    # Not found errors
    if "not found" in error_str or "does not exist" in error_str:
        return {
            "status_code": status.HTTP_404_NOT_FOUND,
            "code": ErrorCodes.NOT_FOUND,
            "message": "The requested resource was not found."
        }
    
    # Validation errors
    if error_type in ("ValidationError", "ValueError", "TypeError"):
        return {
            "status_code": status.HTTP_400_BAD_REQUEST,
            "code": ErrorCodes.VALIDATION_ERROR,
            "message": "Invalid request data. Please check your input."
        }
    
    # File/upload errors
    if "upload" in operation or "file" in error_str:
        return {
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "code": ErrorCodes.UPLOAD_FAILED,
            "message": "File upload failed. Please try again."
        }
    
    # Processing errors
    if any(x in operation for x in ["process", "generate", "transcribe", "research"]):
        return {
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "code": ErrorCodes.PROCESSING_FAILED,
            "message": "Processing failed. Please try again or contact support."
        }
    
    # Default internal error
    return {
        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "code": ErrorCodes.INTERNAL_ERROR,
        "message": "An unexpected error occurred. Please try again."
    }


def raise_not_found(resource: str, resource_id: Optional[str] = None) -> HTTPException:
    """
    Raise a standardized 404 Not Found error.
    
    Args:
        resource: Name of the resource (e.g., "Research brief", "Prospect")
        resource_id: Optional ID for logging
    
    Returns:
        HTTPException with 404 status
    
    Example:
        if not result.data:
            raise raise_not_found("Research brief", research_id)
    """
    message = f"{resource} not found"
    if resource_id:
        logger.warning(f"{resource} not found: {resource_id}")
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": ErrorCodes.NOT_FOUND,
            "message": message
        }
    )


def raise_forbidden(message: str = "You don't have permission to perform this action") -> HTTPException:
    """Raise a standardized 403 Forbidden error."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": ErrorCodes.FORBIDDEN,
            "message": message
        }
    )


def raise_validation_error(message: str, field: Optional[str] = None) -> HTTPException:
    """Raise a standardized 400 Validation error."""
    detail = {
        "error": ErrorCodes.VALIDATION_ERROR,
        "message": message
    }
    if field:
        detail["field"] = field
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail
    )

