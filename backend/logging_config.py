"""Logging configuration for jamr.io backend.

This module configures Python logging with JSON formatting for structured logging.
All logs are written to stdout for container-friendly deployment.
"""

import logging
import json
import sys
import traceback
from datetime import datetime
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    
    Formats log records as JSON objects with timestamp, level, message,
    stack trace (for errors), and additional context.
    
    **Validates: Requirements 14.6**
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record as a JSON string.
        
        Args:
            record: The log record to format
            
        Returns:
            str: JSON-formatted log entry
        """
        # Build base log entry
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "stack_trace": self.formatException(record.exc_info)
            }
        
        # Add extra context fields if present
        # These are added via the 'extra' parameter in logging calls
        if hasattr(record, 'request_path'):
            log_entry["request_path"] = record.request_path
        
        if hasattr(record, 'request_method'):
            log_entry["request_method"] = record.request_method
        
        if hasattr(record, 'user_id'):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, 'room_id'):
            log_entry["room_id"] = record.room_id
        
        if hasattr(record, 'client_host'):
            log_entry["client_host"] = record.client_host
        
        if hasattr(record, 'exception_type'):
            log_entry["exception_type"] = record.exception_type
        
        if hasattr(record, 'exception_message'):
            log_entry["exception_message"] = record.exception_message
        
        # Add any other extra fields
        for key, value in record.__dict__.items():
            if key not in [
                'name', 'msg', 'args', 'created', 'filename', 'funcName',
                'levelname', 'levelno', 'lineno', 'module', 'msecs',
                'message', 'pathname', 'process', 'processName', 'relativeCreated',
                'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info',
                'request_path', 'request_method', 'user_id', 'room_id',
                'client_host', 'exception_type', 'exception_message'
            ]:
                # Add any custom extra fields
                if not key.startswith('_'):
                    log_entry[key] = value
        
        # Add source location for debugging
        log_entry["source"] = {
            "file": record.pathname,
            "line": record.lineno,
            "function": record.funcName
        }
        
        # Convert to JSON string
        return json.dumps(log_entry, default=str)


def configure_logging(level: str = "INFO") -> None:
    """
    Configure application logging with JSON formatting.
    
    Sets up the root logger to output JSON-formatted logs to stdout.
    This is ideal for container environments where logs are collected
    from stdout/stderr.
    
    **Validates: Requirements 14.6**
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
               Defaults to INFO, can be overridden by LOG_LEVEL env var
    """
    import os
    
    # Get log level from environment or use default
    log_level = os.getenv("LOG_LEVEL", level).upper()
    
    # Validate log level
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if log_level not in valid_levels:
        log_level = "INFO"
    
    # Get the root logger
    root_logger = logging.getLogger()
    
    # Set log level
    root_logger.setLevel(getattr(logging, log_level))
    
    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create stdout handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(getattr(logging, log_level))
    
    # Set JSON formatter
    json_formatter = JSONFormatter()
    stdout_handler.setFormatter(json_formatter)
    
    # Add handler to root logger
    root_logger.addHandler(stdout_handler)
    
    # Configure specific loggers
    
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    # Set application loggers to configured level
    logging.getLogger("backend").setLevel(getattr(logging, log_level))
    
    # Log configuration complete
    root_logger.info(
        f"Logging configured with level {log_level}",
        extra={"log_level": log_level}
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Logger name (typically __name__ of the module)
        
    Returns:
        logging.Logger: Configured logger instance
        
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Application started")
        >>> logger.error("An error occurred", extra={"user_id": 123})
    """
    return logging.getLogger(name)


def log_error(
    logger: logging.Logger,
    message: str,
    exc: Exception = None,
    **context
) -> None:
    """
    Log an error with context and optional exception.
    
    Convenience function for logging errors with consistent formatting.
    
    **Validates: Requirements 14.6**
    
    Args:
        logger: Logger instance to use
        message: Error message
        exc: Optional exception to include
        **context: Additional context fields (user_id, room_id, etc.)
        
    Example:
        >>> log_error(
        ...     logger,
        ...     "Failed to create room",
        ...     exc=exception,
        ...     user_id=123,
        ...     room_name="My Room"
        ... )
    """
    extra = {}
    
    # Add context fields
    for key, value in context.items():
        extra[key] = value
    
    # Add exception info if provided
    if exc:
        extra["exception_type"] = type(exc).__name__
        extra["exception_message"] = str(exc)
    
    # Log the error
    logger.error(message, extra=extra, exc_info=exc is not None)


def log_warning(
    logger: logging.Logger,
    message: str,
    **context
) -> None:
    """
    Log a warning with context.
    
    Convenience function for logging warnings with consistent formatting.
    
    Args:
        logger: Logger instance to use
        message: Warning message
        **context: Additional context fields
        
    Example:
        >>> log_warning(
        ...     logger,
        ...     "Rate limit approaching",
        ...     user_id=123,
        ...     request_count=95
        ... )
    """
    extra = {}
    
    # Add context fields
    for key, value in context.items():
        extra[key] = value
    
    # Log the warning
    logger.warning(message, extra=extra)


def log_info(
    logger: logging.Logger,
    message: str,
    **context
) -> None:
    """
    Log an info message with context.
    
    Convenience function for logging info messages with consistent formatting.
    
    Args:
        logger: Logger instance to use
        message: Info message
        **context: Additional context fields
        
    Example:
        >>> log_info(
        ...     logger,
        ...     "User joined room",
        ...     user_id=123,
        ...     room_id=456
        ... )
    """
    extra = {}
    
    # Add context fields
    for key, value in context.items():
        extra[key] = value
    
    # Log the info message
    logger.info(message, extra=extra)
