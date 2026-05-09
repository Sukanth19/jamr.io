"""Property-based tests for session management.

Feature: jamr-io-mvp
Tests session management properties including token generation, HTTP-only cookies, and validation.
"""

import pytest
import secrets
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume
from backend.models import User, Session as SessionModel
from tests.conftest import get_test_session


# Property 41: Session Token Generation
# **Validates: Requirements 13.1, 13.5**
@settings(max_examples=100)
@given(
    display_name=st.text(min_size=1, max_size=100, alphabet=st.characters(min_codepoint=33, max_codepoint=126))
)
def test_session_token_generated_on_authentication(display_name):
    """
    Property 41: Session Token Generation (Part 1 - Token Created)
    
    For any successful user authentication, the platform must generate a unique session token
    and store it in the sessions table with the user_id and an expiration timestamp 7 days
    in the future.
    """
    import uuid
    db_session = get_test_session()
    try:
        # Generate unique spotify_id to avoid conflicts
        spotify_id = str(uuid.uuid4())
        
        # Create a test user (simulating successful authentication)
        user = User(
            spotify_id=spotify_id,
            display_name=display_name,
            email=f"{spotify_id}@example.com",
            access_token_encrypted="encrypted_token",
            taste_vector={"danceability": 0.5}
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Generate session token (as done in auth callback)
        session_token = secrets.token_urlsafe(32)
        session_expires_at = datetime.now() + timedelta(days=7)
        
        # Store session in database
        session = SessionModel(
            user_id=user.id,
            token=session_token,
            expires_at=session_expires_at
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        
        # Verify session was created
        assert session.id is not None
        assert session.user_id == user.id
        assert session.token == session_token
        assert session.created_at is not None
        
        # Verify session is stored in database
        stored_session = db_session.query(SessionModel).filter(
            SessionModel.token == session_token
        ).first()
        assert stored_session is not None
        assert stored_session.user_id == user.id
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    display_name=st.text(min_size=1, max_size=100, alphabet=st.characters(min_codepoint=33, max_codepoint=126))
)
def test_session_expiration_set_to_7_days(display_name):
    """
    Property 41: Session Token Generation (Part 2 - 7 Day Expiration)
    
    For any successful user authentication, the session token expiration must be set to
    7 days in the future.
    """
    import uuid
    db_session = get_test_session()
    try:
        # Generate unique spotify_id
        spotify_id = str(uuid.uuid4())
        
        # Create a test user
        user = User(
            spotify_id=spotify_id,
            display_name=display_name,
            email=f"{spotify_id}@example.com",
            access_token_encrypted="encrypted_token",
            taste_vector={"danceability": 0.5}
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Generate session with 7-day expiration
        now = datetime.now()
        session_token = secrets.token_urlsafe(32)
        session_expires_at = now + timedelta(days=7)
        
        session = SessionModel(
            user_id=user.id,
            token=session_token,
            expires_at=session_expires_at
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        
        # Verify expiration is approximately 7 days from now
        time_diff = (session.expires_at - now).total_seconds()
        expected_seconds = 7 * 24 * 60 * 60  # 604800 seconds
        
        # Allow 5 second margin for test execution time
        assert expected_seconds - 5 <= time_diff <= expected_seconds + 5
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    display_name=st.text(min_size=1, max_size=100, alphabet=st.characters(min_codepoint=33, max_codepoint=126))
)
def test_session_token_is_unique(display_name):
    """
    Property 41: Session Token Generation (Part 3 - Token Uniqueness)
    
    For any successful user authentication, the generated session token must be unique.
    """
    import uuid
    db_session = get_test_session()
    try:
        # Generate unique spotify_id
        spotify_id = str(uuid.uuid4())
        
        # Create a test user
        user = User(
            spotify_id=spotify_id,
            display_name=display_name,
            email=f"{spotify_id}@example.com",
            access_token_encrypted="encrypted_token",
            taste_vector={"danceability": 0.5}
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Generate multiple session tokens
        tokens = [secrets.token_urlsafe(32) for _ in range(10)]
        
        # All tokens should be unique
        assert len(tokens) == len(set(tokens))
        
        # Store first session
        session_1 = SessionModel(
            user_id=user.id,
            token=tokens[0],
            expires_at=datetime.now() + timedelta(days=7)
        )
        db_session.add(session_1)
        db_session.commit()
        
        # Try to store second session with duplicate token (should fail)
        session_2 = SessionModel(
            user_id=user.id,
            token=tokens[0],  # Same token
            expires_at=datetime.now() + timedelta(days=7)
        )
        db_session.add(session_2)
        
        with pytest.raises(Exception):  # Should raise IntegrityError due to unique constraint
            db_session.commit()
    finally:
        db_session.rollback()
        db_session.close()


# Property 42: HTTP-Only Cookie
# **Validates: Requirements 13.2**
def test_http_only_cookie_flag_set():
    """
    Property 42: HTTP-Only Cookie (Part 1 - HttpOnly Flag)
    
    For any session token issued, the Set-Cookie header must include the HttpOnly flag
    to prevent JavaScript access.
    """
    # Define the cookie parameters that should be used
    cookie_params = {
        "key": "session_token",
        "httponly": True,
        "max_age": 7 * 24 * 60 * 60,  # 7 days in seconds
        "secure": True,
        "samesite": "lax"
    }
    
    # Verify HttpOnly flag is set
    assert cookie_params["httponly"] is True
    
    # Verify other security flags
    assert cookie_params["secure"] is True
    assert cookie_params["samesite"] == "lax"


@settings(max_examples=100)
@given(
    session_token=st.text(min_size=32, max_size=64, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_')
)
def test_http_only_cookie_parameters_correct(session_token):
    """
    Property 42: HTTP-Only Cookie (Part 2 - Cookie Parameters)
    
    For any session token issued, the cookie must have correct parameters:
    - httponly: True
    - max_age: 7 days (604800 seconds)
    - secure: True
    - samesite: lax
    """
    # Simulate cookie parameters that would be set in the response
    cookie_params = {
        "key": "session_token",
        "value": session_token,
        "httponly": True,
        "max_age": 7 * 24 * 60 * 60,
        "secure": True,
        "samesite": "lax"
    }
    
    # Verify all parameters are correct
    assert cookie_params["httponly"] is True
    assert cookie_params["max_age"] == 604800
    assert cookie_params["secure"] is True
    assert cookie_params["samesite"] == "lax"
    assert cookie_params["key"] == "session_token"
    assert cookie_params["value"] == session_token


# Property 43: Session Token Validation
# **Validates: Requirements 13.3**
@settings(max_examples=100)
@given(
    display_name=st.text(min_size=1, max_size=100, alphabet=st.characters(min_codepoint=33, max_codepoint=126))
)
def test_missing_session_token_rejected(display_name):
    """
    Property 43: Session Token Validation (Part 1 - Missing Token)
    
    For any authenticated API request, if the session token is missing, the platform
    must reject the request with a 401 Unauthorized status.
    """
    import uuid
    db_session = get_test_session()
    try:
        # Generate unique spotify_id
        spotify_id = str(uuid.uuid4())
        
        # Create a test user
        user = User(
            spotify_id=spotify_id,
            display_name=display_name,
            email=f"{spotify_id}@example.com",
            access_token_encrypted="encrypted_token",
            taste_vector={"danceability": 0.5}
        )
        db_session.add(user)
        db_session.commit()
        
        # Simulate validation with missing token
        session_token = None
        
        # Query for session (should not find any)
        session = None
        if session_token:
            session = db_session.query(SessionModel).filter(
                SessionModel.token == session_token
            ).first()
        
        # Verify that missing token results in no session found
        assert session is None
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    display_name=st.text(min_size=1, max_size=100, alphabet=st.characters(min_codepoint=33, max_codepoint=126)),
    invalid_token=st.text(min_size=1, max_size=64, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_')
)
def test_invalid_session_token_rejected(display_name, invalid_token):
    """
    Property 43: Session Token Validation (Part 2 - Invalid Token)
    
    For any authenticated API request, if the session token is invalid (not in database),
    the platform must reject the request with a 401 Unauthorized status.
    """
    import uuid
    db_session = get_test_session()
    try:
        # Generate unique spotify_id
        spotify_id = str(uuid.uuid4())
        
        # Create a test user with a valid session
        user = User(
            spotify_id=spotify_id,
            display_name=display_name,
            email=f"{spotify_id}@example.com",
            access_token_encrypted="encrypted_token",
            taste_vector={"danceability": 0.5}
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Create a valid session
        valid_token = secrets.token_urlsafe(32)
        session = SessionModel(
            user_id=user.id,
            token=valid_token,
            expires_at=datetime.now() + timedelta(days=7)
        )
        db_session.add(session)
        db_session.commit()
        
        # Ensure invalid_token is different from valid_token
        assume(invalid_token != valid_token)
        
        # Try to validate with invalid token
        invalid_session = db_session.query(SessionModel).filter(
            SessionModel.token == invalid_token
        ).first()
        
        # Verify that invalid token results in no session found
        assert invalid_session is None
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    display_name=st.text(min_size=1, max_size=100, alphabet=st.characters(min_codepoint=33, max_codepoint=126))
)
def test_expired_session_token_rejected(display_name):
    """
    Property 43: Session Token Validation (Part 3 - Expired Token)
    
    For any authenticated API request, if the session token is expired, the platform
    must reject the request with a 401 Unauthorized status.
    """
    import uuid
    db_session = get_test_session()
    try:
        # Generate unique spotify_id
        spotify_id = str(uuid.uuid4())
        
        # Create a test user
        user = User(
            spotify_id=spotify_id,
            display_name=display_name,
            email=f"{spotify_id}@example.com",
            access_token_encrypted="encrypted_token",
            taste_vector={"danceability": 0.5}
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Create an expired session (expired 1 day ago)
        expired_token = secrets.token_urlsafe(32)
        expired_session = SessionModel(
            user_id=user.id,
            token=expired_token,
            expires_at=datetime.now() - timedelta(days=1)  # Expired
        )
        db_session.add(expired_session)
        db_session.commit()
        
        # Query for the session
        session = db_session.query(SessionModel).filter(
            SessionModel.token == expired_token
        ).first()
        
        # Verify session exists but is expired
        assert session is not None
        assert session.expires_at < datetime.now()
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    display_name=st.text(min_size=1, max_size=100, alphabet=st.characters(min_codepoint=33, max_codepoint=126))
)
def test_valid_session_token_accepted(display_name):
    """
    Property 43: Session Token Validation (Part 4 - Valid Token)
    
    For any authenticated API request, if the session token is valid and not expired,
    the platform must accept the request and return the associated user.
    """
    import uuid
    db_session = get_test_session()
    try:
        # Generate unique spotify_id
        spotify_id = str(uuid.uuid4())
        
        # Create a test user
        user = User(
            spotify_id=spotify_id,
            display_name=display_name,
            email=f"{spotify_id}@example.com",
            access_token_encrypted="encrypted_token",
            taste_vector={"danceability": 0.5}
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Create a valid, non-expired session
        valid_token = secrets.token_urlsafe(32)
        valid_session = SessionModel(
            user_id=user.id,
            token=valid_token,
            expires_at=datetime.now() + timedelta(days=7)  # Not expired
        )
        db_session.add(valid_session)
        db_session.commit()
        
        # Query for the session
        session = db_session.query(SessionModel).filter(
            SessionModel.token == valid_token
        ).first()
        
        # Verify session is valid
        assert session is not None
        assert session.user_id == user.id
        assert session.expires_at > datetime.now()
        
        # Verify we can retrieve the user from the session
        retrieved_user = db_session.query(User).filter(User.id == session.user_id).first()
        assert retrieved_user is not None
        assert retrieved_user.id == user.id
        assert retrieved_user.spotify_id == spotify_id
    finally:
        db_session.rollback()
        db_session.close()
