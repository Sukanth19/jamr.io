"""Property-based tests for error logging.

This module tests that all errors are logged with proper structure including
timestamp, level, message, stack trace, and context.
"""

import pytest
import json
import logging
from io import StringIO
from hypothesis import given, strategies as st, settings
from datetime import datetime
from backend.logging_config import JSONFormatter, configure_logging, log_error, log_warning, log_info


# Feature: jamr-io-mvp, Property 48: Error Logging
# **Validates: Requirements 14.6**
@given(
    error_message=st.text(min_size=1, max_size=200),
    user_id=st.integers(min_value=1, max_value=1000000),
    room_id=st.integers(min_value=1, max_value=1000000)
)
@settings(max_examples=100)
def test_error_logging_includes_required_fields(error_message, user_id, room_id):
    """
    Property 48: Error Logging
    
    For any error that occurs in the backend, the platform must log the error
    with a timestamp, level, message, and relevant context (user_id, room_id, etc.).
    
    **Validates: Requirements 14.6**
    """
    # Create a string buffer to capture log output
    log_buffer = StringIO()
    
    # Create a logger with JSON formatter
    logger = logging.getLogger(f"test_logger_{error_message[:10]}")
    logger.setLevel(logging.ERROR)
    logger.handlers = []  # Clear any existing handlers
    
    # Create handler that writes to buffer
    handler = logging.StreamHandler(log_buffer)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    # Log an error with context
    logger.error(
        error_message,
        extra={
            "user_id": user_id,
            "room_id": room_id
        }
    )
    
    # Get the logged output
    log_output = log_buffer.getvalue()
    
    # Parse JSON log entry
    log_entry = json.loads(log_output)
    
    # Verify required fields are present
    assert "timestamp" in log_entry
    assert "level" in log_entry
    assert "message" in log_entry
    assert "logger" in log_entry
    
    # Verify field values
    assert log_entry["level"] == "ERROR"
    assert log_entry["message"] == error_message
    
    # Verify context fields are present
    assert "user_id" in log_entry
    assert "room_id" in log_entry
    assert log_entry["user_id"] == user_id
    assert log_entry["room_id"] == room_id
    
    # Verify timestamp is valid ISO format
    timestamp = log_entry["timestamp"]
    assert timestamp.endswith("Z")  # UTC timezone
    # Should be parseable as ISO datetime
    datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


# Feature: jamr-io-mvp, Property 48: Error Logging
# **Validates: Requirements 14.6**
@given(
    exception_message=st.text(min_size=1, max_size=100)
)
@settings(max_examples=100)
def test_error_logging_includes_stack_trace(exception_message):
    """
    Property 48: Error Logging
    
    For any error with an exception, the log entry must include the
    exception type, message, and stack trace.
    
    **Validates: Requirements 14.6**
    """
    # Create a string buffer to capture log output
    log_buffer = StringIO()
    
    # Create a logger with JSON formatter
    logger = logging.getLogger(f"test_logger_exc_{exception_message[:10]}")
    logger.setLevel(logging.ERROR)
    logger.handlers = []  # Clear any existing handlers
    
    # Create handler that writes to buffer
    handler = logging.StreamHandler(log_buffer)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    # Create an exception and log it
    try:
        raise ValueError(exception_message)
    except ValueError as e:
        logger.error("An error occurred", exc_info=True)
    
    # Get the logged output
    log_output = log_buffer.getvalue()
    
    # Parse JSON log entry
    log_entry = json.loads(log_output)
    
    # Verify exception information is present
    assert "exception" in log_entry
    assert "type" in log_entry["exception"]
    assert "message" in log_entry["exception"]
    assert "stack_trace" in log_entry["exception"]
    
    # Verify exception details
    assert log_entry["exception"]["type"] == "ValueError"
    assert log_entry["exception"]["message"] == exception_message
    assert len(log_entry["exception"]["stack_trace"]) > 0
    assert "Traceback" in log_entry["exception"]["stack_trace"]


# Feature: jamr-io-mvp, Property 48: Error Logging
# **Validates: Requirements 14.6**
@given(
    log_level=st.sampled_from(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    log_message=st.text(min_size=1, max_size=200)
)
@settings(max_examples=100)
def test_log_entries_have_correct_level(log_level, log_message):
    """
    Property 48: Error Logging
    
    For any log entry, the level field must correctly reflect the
    logging level used (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    
    **Validates: Requirements 14.6**
    """
    # Create a string buffer to capture log output
    log_buffer = StringIO()
    
    # Create a logger with JSON formatter
    logger = logging.getLogger(f"test_logger_level_{log_level}_{log_message[:10]}")
    logger.setLevel(logging.DEBUG)  # Set to DEBUG to capture all levels
    logger.handlers = []  # Clear any existing handlers
    
    # Create handler that writes to buffer
    handler = logging.StreamHandler(log_buffer)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    # Log at the specified level
    log_method = getattr(logger, log_level.lower())
    log_method(log_message)
    
    # Get the logged output
    log_output = log_buffer.getvalue()
    
    # Parse JSON log entry
    log_entry = json.loads(log_output)
    
    # Verify level is correct
    assert log_entry["level"] == log_level
    assert log_entry["message"] == log_message


# Feature: jamr-io-mvp, Property 48: Error Logging
# **Validates: Requirements 14.6**
@given(
    request_path=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'P'))),
    request_method=st.sampled_from(["GET", "POST", "PUT", "DELETE", "PATCH"]),
    error_message=st.text(min_size=1, max_size=200)
)
@settings(max_examples=100)
def test_error_logging_includes_request_context(request_path, request_method, error_message):
    """
    Property 48: Error Logging
    
    For any error that occurs during request processing, the log entry
    must include request context (path, method, etc.).
    
    **Validates: Requirements 14.6**
    """
    # Create a string buffer to capture log output
    log_buffer = StringIO()
    
    # Create a logger with JSON formatter
    logger = logging.getLogger(f"test_logger_req_{request_path[:10]}")
    logger.setLevel(logging.ERROR)
    logger.handlers = []  # Clear any existing handlers
    
    # Create handler that writes to buffer
    handler = logging.StreamHandler(log_buffer)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    # Log an error with request context
    logger.error(
        error_message,
        extra={
            "request_path": request_path,
            "request_method": request_method
        }
    )
    
    # Get the logged output
    log_output = log_buffer.getvalue()
    
    # Parse JSON log entry
    log_entry = json.loads(log_output)
    
    # Verify request context is present
    assert "request_path" in log_entry
    assert "request_method" in log_entry
    assert log_entry["request_path"] == request_path
    assert log_entry["request_method"] == request_method


# Feature: jamr-io-mvp, Property 48: Error Logging
# **Validates: Requirements 14.6**
@given(
    log_message=st.text(min_size=1, max_size=200)
)
@settings(max_examples=100)
def test_log_entries_are_valid_json(log_message):
    """
    Property 48: Error Logging
    
    For any log entry, the output must be valid JSON that can be parsed
    by log aggregation systems.
    
    **Validates: Requirements 14.6**
    """
    # Create a string buffer to capture log output
    log_buffer = StringIO()
    
    # Create a logger with JSON formatter
    logger = logging.getLogger(f"test_logger_json_{log_message[:10]}")
    logger.setLevel(logging.INFO)
    logger.handlers = []  # Clear any existing handlers
    
    # Create handler that writes to buffer
    handler = logging.StreamHandler(log_buffer)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    # Log a message
    logger.info(log_message)
    
    # Get the logged output
    log_output = log_buffer.getvalue()
    
    # Should be valid JSON
    log_entry = json.loads(log_output)
    
    # Verify it's a dictionary
    assert isinstance(log_entry, dict)
    
    # Verify required fields
    assert "timestamp" in log_entry
    assert "level" in log_entry
    assert "message" in log_entry
    
    # Verify message matches
    assert log_entry["message"] == log_message


# Feature: jamr-io-mvp, Property 48: Error Logging
# **Validates: Requirements 14.6**
@given(
    error_message=st.text(min_size=1, max_size=200),
    exception_type=st.sampled_from(["ValueError", "TypeError", "KeyError", "AttributeError"])
)
@settings(max_examples=100)
def test_log_error_helper_function(error_message, exception_type):
    """
    Property 48: Error Logging
    
    The log_error helper function must correctly log errors with
    exception information and context.
    
    **Validates: Requirements 14.6**
    """
    # Create a string buffer to capture log output
    log_buffer = StringIO()
    
    # Create a logger with JSON formatter
    logger = logging.getLogger(f"test_logger_helper_{error_message[:10]}")
    logger.setLevel(logging.ERROR)
    logger.handlers = []  # Clear any existing handlers
    
    # Create handler that writes to buffer
    handler = logging.StreamHandler(log_buffer)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    # Create an exception
    exception_classes = {
        "ValueError": ValueError,
        "TypeError": TypeError,
        "KeyError": KeyError,
        "AttributeError": AttributeError
    }
    
    exc_class = exception_classes[exception_type]
    exc = exc_class(error_message)
    
    # Use log_error helper
    log_error(
        logger,
        "An error occurred",
        exc=exc,
        user_id=123,
        room_id=456
    )
    
    # Get the logged output
    log_output = log_buffer.getvalue()
    
    # Parse JSON log entry
    log_entry = json.loads(log_output)
    
    # Verify error was logged correctly
    assert log_entry["level"] == "ERROR"
    assert log_entry["message"] == "An error occurred"
    assert "exception_type" in log_entry
    assert log_entry["exception_type"] == exception_type
    assert "exception_message" in log_entry
    # Just verify the exception message field is present and not empty
    # (Different exception types format messages differently)
    assert len(log_entry["exception_message"]) > 0
    assert "user_id" in log_entry
    assert log_entry["user_id"] == 123
    assert "room_id" in log_entry
    assert log_entry["room_id"] == 456


# Feature: jamr-io-mvp, Property 48: Error Logging
# **Validates: Requirements 14.6**
@given(
    source_file=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'P'))),
    line_number=st.integers(min_value=1, max_value=10000),
    function_name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))
)
@settings(max_examples=100)
def test_log_entries_include_source_location(source_file, line_number, function_name):
    """
    Property 48: Error Logging
    
    For any log entry, the output must include source location information
    (file, line number, function name) for debugging.
    
    **Validates: Requirements 14.6**
    """
    # Create a string buffer to capture log output
    log_buffer = StringIO()
    
    # Create a logger with JSON formatter
    logger = logging.getLogger(f"test_logger_source_{function_name}")
    logger.setLevel(logging.INFO)
    logger.handlers = []  # Clear any existing handlers
    
    # Create handler that writes to buffer
    handler = logging.StreamHandler(log_buffer)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    # Log a message
    logger.info("Test message")
    
    # Get the logged output
    log_output = log_buffer.getvalue()
    
    # Parse JSON log entry
    log_entry = json.loads(log_output)
    
    # Verify source location is present
    assert "source" in log_entry
    assert "file" in log_entry["source"]
    assert "line" in log_entry["source"]
    assert "function" in log_entry["source"]
    
    # Verify source fields are not empty
    assert len(log_entry["source"]["file"]) > 0
    assert log_entry["source"]["line"] > 0
    assert len(log_entry["source"]["function"]) > 0
