"""Error handling and response formatting for jamr.io API.

This module provides consistent error response formatting and FastAPI exception handlers
for validation errors, authentication errors, database errors, and rate limiting.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from pydantic import ValidationError

# Configure logger
logger = logging.getLogger(__name__)


def format_error_response(
    code: str,
    message: str,
    field: Optional[str] = None
) -> Dict[str, Any]:
    """
    Format error response with consistent structure.
    
    **Validates: Requirements 14.2, 14.3**
    
    Args:
        code: Error code (e.g., "VALIDATION_ERROR", "AUTH_ERROR")
        message: Human-readable error message
        field: Optional field name that caused the error
        
    Returns:
        dict: Formatted error response
        {
            "error": {
                "code": str,
                "message": str,
                "field": str (optional)
            }
        }
    """
    error_dict = {
        "error": {
            "code": code,
            "message": message
        }
    }
    
    if field:
        error_dict["error"]["field"] = field
    
    return error_dict


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """
    Handle FastAPI validation errors (422 Unprocessable Entity).
    
    Converts Pydantic validation errors into consistent error response format.
    Returns 400 Bad Request with detailed validation error messages.
    
    **Validates: Requirements 14.5**
    
    Args:
        request: The FastAPI request object
        exc: The validation error exception
        
    Returns:
        JSONResponse: Formatted error response with 400 status code
    """
    # Extract first validation error for simplicity
    errors = exc.errors()
    
    if errors:
        first_error = errors[0]
        field = ".".join(str(loc) for loc in first_error["loc"] if loc != "body")
        message = first_error["msg"]
        
        # Make message more user-friendly
        if "field required" in message.lower():
            message = f"Field '{field}' is required"
        elif "string type expected" in message.lower():
            message = f"Field '{field}' must be a string"
        elif "value is not a valid" in message.lower():
            message = f"Field '{field}' has an invalid value"
        
        error_response = format_error_response(
            code="VALIDATION_ERROR",
            message=message,
            field=field
        )
    else:
        error_response = format_error_response(
            code="VALIDATION_ERROR",
            message="Request validation failed"
        )
    
    # Log validation error
    logger.warning(
        f"Validation error on {request.method} {request.url.path}: {error_response}",
        extra={
            "request_path": str(request.url.path),
            "request_method": request.method,
            "errors": errors
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=error_response
    )


async def database_exception_handler(
    request: Request,
    exc: SQLAlchemyError
) -> JSONResponse:
    """
    Handle database errors (SQLAlchemy exceptions).
    
    Returns appropriate HTTP status codes based on the type of database error:
    - IntegrityError: 400 Bad Request (constraint violation)
    - OperationalError: 503 Service Unavailable (connection/timeout issues)
    - Other SQLAlchemyError: 500 Internal Server Error
    
    **Validates: Requirements 14.3**
    
    Args:
        request: The FastAPI request object
        exc: The SQLAlchemy exception
        
    Returns:
        JSONResponse: Formatted error response with appropriate status code
    """
    # Determine status code and error message based on exception type
    if isinstance(exc, IntegrityError):
        status_code = status.HTTP_400_BAD_REQUEST
        code = "DATABASE_CONSTRAINT_ERROR"
        message = "Database constraint violation. The operation conflicts with existing data."
        
        # Try to extract more specific information from the error
        error_str = str(exc.orig) if hasattr(exc, 'orig') else str(exc)
        if "unique constraint" in error_str.lower():
            message = "A record with this value already exists"
        elif "foreign key constraint" in error_str.lower():
            message = "Referenced record does not exist"
        elif "not null constraint" in error_str.lower():
            message = "Required field is missing"
    
    elif isinstance(exc, OperationalError):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        code = "DATABASE_UNAVAILABLE"
        message = "Database service is temporarily unavailable. Please try again later."
    
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        code = "DATABASE_ERROR"
        message = "A database error occurred while processing your request"
    
    error_response = format_error_response(
        code=code,
        message=message
    )
    
    # Log database error with full details
    logger.error(
        f"Database error on {request.method} {request.url.path}: {str(exc)}",
        extra={
            "request_path": str(request.url.path),
            "request_method": request.method,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc)
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status_code,
        content=error_response
    )


async def rate_limit_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """
    Handle rate limiting errors (429 Too Many Requests).
    
    Returns a consistent error response when a user exceeds the rate limit.
    
    **Validates: Requirements 15.6**
    
    Args:
        request: The FastAPI request object
        exc: The rate limit exception
        
    Returns:
        JSONResponse: Formatted error response with 429 status code
    """
    error_response = format_error_response(
        code="RATE_LIMIT_EXCEEDED",
        message="Too many requests. Please slow down and try again later."
    )
    
    # Log rate limit violation
    logger.warning(
        f"Rate limit exceeded on {request.method} {request.url.path}",
        extra={
            "request_path": str(request.url.path),
            "request_method": request.method,
            "client_host": request.client.host if request.client else None
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=error_response,
        headers={"Retry-After": "60"}  # Suggest retry after 60 seconds
    )


async def authentication_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """
    Handle authentication errors (401 Unauthorized).
    
    Returns a consistent error response for authentication failures.
    
    **Validates: Requirements 14.2**
    
    Args:
        request: The FastAPI request object
        exc: The authentication exception
        
    Returns:
        JSONResponse: Formatted error response with 401 status code
    """
    # Extract error details from exception if available
    error_detail = getattr(exc, 'detail', None)
    
    if isinstance(error_detail, dict) and 'error' in error_detail:
        # Exception already has formatted error response
        error_response = error_detail
    else:
        # Create default authentication error response
        message = str(error_detail) if error_detail else "Authentication required"
        error_response = format_error_response(
            code="AUTHENTICATION_ERROR",
            message=message
        )
    
    # Log authentication error
    logger.warning(
        f"Authentication error on {request.method} {request.url.path}",
        extra={
            "request_path": str(request.url.path),
            "request_method": request.method,
            "client_host": request.client.host if request.client else None
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=error_response
    )


async def authorization_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """
    Handle authorization errors (403 Forbidden).
    
    Returns a consistent error response for authorization failures.
    
    **Validates: Requirements 14.2**
    
    Args:
        request: The FastAPI request object
        exc: The authorization exception
        
    Returns:
        JSONResponse: Formatted error response with 403 status code
    """
    # Extract error details from exception if available
    error_detail = getattr(exc, 'detail', None)
    
    if isinstance(error_detail, dict) and 'error' in error_detail:
        # Exception already has formatted error response
        error_response = error_detail
    else:
        # Create default authorization error response
        message = str(error_detail) if error_detail else "You do not have permission to perform this action"
        error_response = format_error_response(
            code="AUTHORIZATION_ERROR",
            message=message
        )
    
    # Log authorization error
    logger.warning(
        f"Authorization error on {request.method} {request.url.path}",
        extra={
            "request_path": str(request.url.path),
            "request_method": request.method,
            "client_host": request.client.host if request.client else None
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content=error_response
    )


async def not_found_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """
    Handle not found errors (404 Not Found).
    
    Returns a consistent error response for resource not found errors.
    
    **Validates: Requirements 14.2**
    
    Args:
        request: The FastAPI request object
        exc: The not found exception
        
    Returns:
        JSONResponse: Formatted error response with 404 status code
    """
    # Extract error details from exception if available
    error_detail = getattr(exc, 'detail', None)
    
    if isinstance(error_detail, dict) and 'error' in error_detail:
        # Exception already has formatted error response
        error_response = error_detail
    else:
        # Create default not found error response
        message = str(error_detail) if error_detail else "The requested resource was not found"
        error_response = format_error_response(
            code="NOT_FOUND",
            message=message
        )
    
    # Log not found error
    logger.info(
        f"Resource not found on {request.method} {request.url.path}",
        extra={
            "request_path": str(request.url.path),
            "request_method": request.method
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=error_response
    )


async def internal_server_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """
    Handle internal server errors (500 Internal Server Error).
    
    Returns a generic error response for unexpected server errors.
    Logs the full exception details for debugging.
    
    **Validates: Requirements 14.2**
    
    Args:
        request: The FastAPI request object
        exc: The exception
        
    Returns:
        JSONResponse: Formatted error response with 500 status code
    """
    error_response = format_error_response(
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred. Please try again later."
    )
    
    # Log internal server error with full stack trace
    logger.error(
        f"Internal server error on {request.method} {request.url.path}: {str(exc)}",
        extra={
            "request_path": str(request.url.path),
            "request_method": request.method,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc)
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response
    )


def register_exception_handlers(app):
    """
    Register all exception handlers with the FastAPI application.
    
    This function should be called during application startup to register
    custom exception handlers for various error types.
    
    Args:
        app: The FastAPI application instance
    """
    from fastapi import HTTPException
    
    # Register validation error handler
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    
    # Register database error handler
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)
    
    # Register HTTP exception handlers by status code
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTPException based on status code."""
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return await authentication_exception_handler(request, exc)
        elif exc.status_code == status.HTTP_403_FORBIDDEN:
            return await authorization_exception_handler(request, exc)
        elif exc.status_code == status.HTTP_404_NOT_FOUND:
            return await not_found_exception_handler(request, exc)
        elif exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            return await rate_limit_exception_handler(request, exc)
        else:
            # For other HTTP exceptions, return the detail as-is
            error_detail = exc.detail
            if isinstance(error_detail, dict) and 'error' in error_detail:
                error_response = error_detail
            else:
                error_response = format_error_response(
                    code="HTTP_ERROR",
                    message=str(error_detail) if error_detail else "An error occurred"
                )
            
            return JSONResponse(
                status_code=exc.status_code,
                content=error_response
            )
    
    # Register catch-all exception handler for unexpected errors
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle all other unexpected exceptions."""
        return await internal_server_exception_handler(request, exc)
