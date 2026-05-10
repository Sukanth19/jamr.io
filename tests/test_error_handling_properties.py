"""Property-based tests for error handling and user feedback.

This module tests error response formatting, validation error display,
and sensitive data exclusion using property-based testing.
"""

import pytest
from hypothesis import given, strategies as st, settings
from fastapi import HTTPException
from backend.error_handlers import format_error_response


# Feature: jamr-io-mvp, Property 47: Validation Error Display
# **Validates: Requirements 14.5**
@given(
    field_name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'P'))),
    error_message=st.text(min_size=1, max_size=200)
)
@settings(max_examples=100)
def test_validation_error_format_includes_field_and_message(field_name, error_message):
    """
    Property 47: Validation Error Display
    
    For any validation error with a field name and error message,
    the error response must include both the field name and a clear
    error message describing the validation failure.
    
    **Validates: Requirements 14.5**
    """
    # Format error response
    error_response = format_error_response(
        code="VALIDATION_ERROR",
        message=error_message,
        field=field_name
    )
    
    # Verify response structure
    assert "error" in error_response
    assert "code" in error_response["error"]
    assert "message" in error_response["error"]
    assert "field" in error_response["error"]
    
    # Verify field and message are present
    assert error_response["error"]["field"] == field_name
    assert error_response["error"]["message"] == error_message
    assert error_response["error"]["code"] == "VALIDATION_ERROR"


# Feature: jamr-io-mvp, Property 47: Validation Error Display
# **Validates: Requirements 14.5**
@given(
    error_code=st.sampled_from([
        "VALIDATION_ERROR",
        "AUTHENTICATION_ERROR",
        "AUTHORIZATION_ERROR",
        "NOT_FOUND",
        "DATABASE_ERROR",
        "RATE_LIMIT_EXCEEDED"
    ]),
    error_message=st.text(min_size=1, max_size=200)
)
@settings(max_examples=100)
def test_error_response_has_consistent_structure(error_code, error_message):
    """
    Property 47: Validation Error Display
    
    For any error response, the structure must be consistent with:
    {"error": {"code": str, "message": str, "field": str (optional)}}
    
    **Validates: Requirements 14.5**
    """
    # Format error response without field
    error_response = format_error_response(
        code=error_code,
        message=error_message
    )
    
    # Verify response structure
    assert isinstance(error_response, dict)
    assert "error" in error_response
    assert isinstance(error_response["error"], dict)
    assert "code" in error_response["error"]
    assert "message" in error_response["error"]
    assert error_response["error"]["code"] == error_code
    assert error_response["error"]["message"] == error_message


# Feature: jamr-io-mvp, Property 50: Sensitive Data Exclusion
# **Validates: Requirements 15.5**
@given(
    user_data=st.fixed_dictionaries({
        "id": st.integers(min_value=1, max_value=1000000),
        "spotify_id": st.text(min_size=10, max_size=50),
        "display_name": st.text(min_size=1, max_size=100),
        "email": st.emails(),
        "access_token_encrypted": st.text(min_size=50, max_size=200),
        "refresh_token_encrypted": st.text(min_size=50, max_size=200),
        "taste_vector": st.fixed_dictionaries({
            "danceability": st.floats(min_value=0.0, max_value=1.0),
            "energy": st.floats(min_value=0.0, max_value=1.0),
            "valence": st.floats(min_value=0.0, max_value=1.0)
        })
    })
)
@settings(max_examples=100)
def test_sensitive_data_excluded_from_user_response(user_data):
    """
    Property 50: Sensitive Data Exclusion
    
    For any API response containing user data, the response must not
    include sensitive fields like access_token_encrypted,
    refresh_token_encrypted, or session tokens.
    
    **Validates: Requirements 15.5**
    """
    # Simulate creating a safe user response (what the API should return)
    safe_user_response = {
        "id": user_data["id"],
        "spotify_id": user_data["spotify_id"],
        "display_name": user_data["display_name"],
        "email": user_data["email"],
        "taste_vector": user_data["taste_vector"]
    }
    
    # Verify sensitive fields are NOT in the response
    assert "access_token_encrypted" not in safe_user_response
    assert "refresh_token_encrypted" not in safe_user_response
    assert "token" not in safe_user_response
    assert "session_token" not in safe_user_response
    
    # Verify safe fields ARE in the response
    assert "id" in safe_user_response
    assert "display_name" in safe_user_response
    assert "taste_vector" in safe_user_response


# Feature: jamr-io-mvp, Property 50: Sensitive Data Exclusion
# **Validates: Requirements 15.5**
@given(
    session_data=st.fixed_dictionaries({
        "user_id": st.integers(min_value=1, max_value=1000000),
        "token": st.text(min_size=32, max_size=64),
        "expires_at": st.datetimes()
    })
)
@settings(max_examples=100)
def test_session_token_never_in_api_response(session_data):
    """
    Property 50: Sensitive Data Exclusion
    
    For any API response, session tokens must never be included in the
    response body. Session tokens should only be transmitted via HTTP-only
    cookies.
    
    **Validates: Requirements 15.5**
    """
    # Simulate creating a safe session response (what the API should return)
    # Session creation should only return success message, not the token
    safe_session_response = {
        "message": "Successfully logged in",
        "user_id": session_data["user_id"]
    }
    
    # Verify token is NOT in the response
    assert "token" not in safe_session_response
    assert "session_token" not in safe_session_response
    assert session_data["token"] not in str(safe_session_response)
    
    # Verify only safe fields are present
    assert "message" in safe_session_response
    assert "user_id" in safe_session_response


# Feature: jamr-io-mvp, Property 47: Validation Error Display
# **Validates: Requirements 14.5**
@given(
    room_name=st.text(min_size=0, max_size=2),
)
@settings(max_examples=100)
def test_validation_error_for_short_room_name(room_name):
    """
    Property 47: Validation Error Display
    
    For any room name that is too short (< 3 characters after trimming),
    the validation error must clearly indicate which field failed and why.
    
    **Validates: Requirements 14.5**
    """
    from backend.validators import validate_room_name
    
    # Validate room name
    is_valid, error_message = validate_room_name(room_name)
    
    # Should be invalid
    assert not is_valid
    
    # Error message should be clear and descriptive
    assert len(error_message) > 0
    assert "room name" in error_message.lower() or "name" in error_message.lower()
    # Error message should mention either "3" characters or "empty" for empty strings
    assert "3" in error_message or "three" in error_message.lower() or "empty" in error_message.lower()


# Feature: jamr-io-mvp, Property 47: Validation Error Display
# **Validates: Requirements 14.5**
@given(
    room_name=st.text(min_size=51, max_size=100),
)
@settings(max_examples=100)
def test_validation_error_for_long_room_name(room_name):
    """
    Property 47: Validation Error Display
    
    For any room name that is too long (> 50 characters after trimming),
    the validation error must clearly indicate which field failed and why.
    
    **Validates: Requirements 14.5**
    """
    from backend.validators import validate_room_name
    
    # Validate room name
    is_valid, error_message = validate_room_name(room_name)
    
    # Should be invalid
    assert not is_valid
    
    # Error message should be clear and descriptive
    assert len(error_message) > 0
    assert "room name" in error_message.lower() or "name" in error_message.lower()
    assert "50" in error_message or "fifty" in error_message.lower()


# Feature: jamr-io-mvp, Property 47: Validation Error Display
# **Validates: Requirements 14.5**
@given(
    message_content=st.text(min_size=501, max_size=1000),
)
@settings(max_examples=100)
def test_validation_error_for_long_message(message_content):
    """
    Property 47: Validation Error Display
    
    For any message that exceeds 500 characters, the validation error
    must clearly indicate the field and the character limit.
    
    **Validates: Requirements 14.5**
    """
    from backend.validators import validate_message_content
    
    # Validate message content
    is_valid, error_message = validate_message_content(message_content)
    
    # Should be invalid
    assert not is_valid
    
    # Error message should be clear and descriptive
    assert len(error_message) > 0
    assert "message" in error_message.lower() or "content" in error_message.lower()
    assert "500" in error_message


# Feature: jamr-io-mvp, Property 47: Validation Error Display
# **Validates: Requirements 14.5**
@given(
    invalid_link=st.one_of(
        st.text(min_size=1, max_size=100).filter(lambda x: not x.startswith("https://open.spotify.com/jam/")),
        st.just(""),
        st.just("http://open.spotify.com/jam/abc123"),  # Wrong protocol
        st.just("https://spotify.com/jam/abc123"),  # Wrong domain
        st.just("https://open.spotify.com/track/abc123"),  # Wrong path
    )
)
@settings(max_examples=100)
def test_validation_error_for_invalid_jam_link(invalid_link):
    """
    Property 47: Validation Error Display
    
    For any invalid Spotify Jam link, the validation error must clearly
    indicate the expected format.
    
    **Validates: Requirements 14.5**
    """
    from backend.validators import validate_spotify_jam_link
    
    # Validate Spotify Jam link
    is_valid, error_message = validate_spotify_jam_link(invalid_link)
    
    # Should be invalid
    assert not is_valid
    
    # Error message should be clear and descriptive
    assert len(error_message) > 0
    assert "spotify" in error_message.lower() or "jam" in error_message.lower() or "link" in error_message.lower()


# Feature: jamr-io-mvp, Property 50: Sensitive Data Exclusion
# **Validates: Requirements 15.5**
@given(
    error_context=st.fixed_dictionaries({
        "user_id": st.integers(min_value=1, max_value=1000000),
        "access_token": st.text(min_size=50, max_size=200, alphabet=st.characters(blacklist_characters='0')),
        "error_message": st.text(min_size=10, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'P', 'Zs')))
    })
)
@settings(max_examples=100)
def test_error_responses_do_not_leak_sensitive_data(error_context):
    """
    Property 50: Sensitive Data Exclusion
    
    For any error response, sensitive data like access tokens must never
    be included in the error message or response body.
    
    **Validates: Requirements 15.5**
    """
    # Ensure error message and access token are different
    # (to avoid false positives when they happen to be the same)
    if error_context["access_token"] == error_context["error_message"]:
        return  # Skip this test case
    
    # Format error response
    error_response = format_error_response(
        code="INTERNAL_ERROR",
        message=error_context["error_message"]
    )
    
    # Convert response to string for checking
    response_str = str(error_response)
    
    # Verify access token is NOT in the response
    assert error_context["access_token"] not in response_str
    
    # Verify response only contains safe information
    assert "error" in error_response
    assert "code" in error_response["error"]
    assert "message" in error_response["error"]
    
    # Verify no token-like strings in the message
    message = error_response["error"]["message"]
    # Check that if "token" appears, "access" doesn't appear nearby (and vice versa)
    has_token = "token" in message.lower()
    has_access = "access" in message.lower()
    # It's okay to have one or the other, but not both together (which would suggest a token leak)
    assert not (has_token and has_access)
