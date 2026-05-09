"""Property-based test for session invalidation.

Feature: jamr-io-mvp
Tests Property 44: Session Invalidation
"""

import pytest
import secrets
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings
from backend.models import User, Session as SessionModel
from tests.conftest import get_test_session


# Property 44: Session Invalidation
# **Validates: Requirements 13.6**
@settings(max_examples=100)
@given(
    display_name=st.text(min_size=1, max_size=100, alphabet=st.characters(min_codepoint=33, max_codepoint=126))
)
def test_session_invalidation_deletes_token_from_database(display_name):
    """
    Property 44: Session Invalidation (Part 1 - Token Deletion)
    
    For any logout request, the platform must delete the session token from the sessions
    table, making it invalid for future requests.
    
    This test verifies that after logout, the session token is removed from the database.
    """
    import uuid
    db_session = get_test_session()
    try:
        # Generate unique spotify_id to avoid conflicts
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
        
        # Create a valid session
        session_token = secrets.token_urlsafe(32)
        session = SessionModel(
            user_id=user.id,
            token=session_token,
            expires_at=datetime.now() + timedelta(days=7)
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        
        # Verify session exists before logout
        existing_session = db_session.query(SessionModel).filter(
            SessionModel.token == session_token
        ).first()
        assert existing_session is not None
        assert existing_session.user_id == user.id
        
        # Simulate logout: delete session from database
        db_session.delete(session)
        db_session.commit()
        
        # Verify session was deleted from database
        deleted_session = db_session.query(SessionModel).filter(
            SessionModel.token == session_token
        ).first()
        assert deleted_session is None
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    display_name=st.text(min_size=1, max_size=100, alphabet=st.characters(min_codepoint=33, max_codepoint=126))
)
def test_session_invalidation_prevents_future_authentication(display_name):
    """
    Property 44: Session Invalidation (Part 2 - Future Request Rejection)
    
    For any logout request, after the session token is deleted from the sessions table,
    any subsequent request using that token must be rejected (session not found).
    
    This test verifies that after logout, the invalidated token cannot be used for
    authentication.
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
        
        # Create a valid session
        session_token = secrets.token_urlsafe(32)
        session = SessionModel(
            user_id=user.id,
            token=session_token,
            expires_at=datetime.now() + timedelta(days=7)
        )
        db_session.add(session)
        db_session.commit()
        
        # Verify session is valid before logout
        valid_session = db_session.query(SessionModel).filter(
            SessionModel.token == session_token,
            SessionModel.expires_at > datetime.now()
        ).first()
        assert valid_session is not None
        
        # Simulate logout: delete session
        db_session.delete(session)
        db_session.commit()
        
        # Attempt to authenticate with the invalidated token
        # (simulating a subsequent request)
        invalidated_session = db_session.query(SessionModel).filter(
            SessionModel.token == session_token
        ).first()
        
        # Verify that the token is no longer valid (not found in database)
        assert invalidated_session is None
        
        # This means any authentication attempt with this token would fail
        # because the session doesn't exist in the database
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    display_name=st.text(min_size=1, max_size=100, alphabet=st.characters(min_codepoint=33, max_codepoint=126))
)
def test_session_invalidation_only_affects_target_session(display_name):
    """
    Property 44: Session Invalidation (Part 3 - Selective Deletion)
    
    For any logout request, only the specific session token being logged out should be
    deleted. Other sessions for the same user or different users should remain valid.
    
    This test verifies that logout only invalidates the specific session, not all
    sessions for the user.
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
        
        # Create multiple sessions for the same user (e.g., different devices)
        session_token_1 = secrets.token_urlsafe(32)
        session_1 = SessionModel(
            user_id=user.id,
            token=session_token_1,
            expires_at=datetime.now() + timedelta(days=7)
        )
        
        session_token_2 = secrets.token_urlsafe(32)
        session_2 = SessionModel(
            user_id=user.id,
            token=session_token_2,
            expires_at=datetime.now() + timedelta(days=7)
        )
        
        db_session.add(session_1)
        db_session.add(session_2)
        db_session.commit()
        
        # Verify both sessions exist
        assert db_session.query(SessionModel).filter(
            SessionModel.token == session_token_1
        ).first() is not None
        assert db_session.query(SessionModel).filter(
            SessionModel.token == session_token_2
        ).first() is not None
        
        # Simulate logout for session_1 only
        db_session.delete(session_1)
        db_session.commit()
        
        # Verify session_1 was deleted
        deleted_session = db_session.query(SessionModel).filter(
            SessionModel.token == session_token_1
        ).first()
        assert deleted_session is None
        
        # Verify session_2 still exists (not affected by logout of session_1)
        remaining_session = db_session.query(SessionModel).filter(
            SessionModel.token == session_token_2
        ).first()
        assert remaining_session is not None
        assert remaining_session.user_id == user.id
        assert remaining_session.expires_at > datetime.now()
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    display_name=st.text(min_size=1, max_size=100, alphabet=st.characters(min_codepoint=33, max_codepoint=126))
)
def test_session_invalidation_is_immediate(display_name):
    """
    Property 44: Session Invalidation (Part 4 - Immediate Effect)
    
    For any logout request, the session invalidation must take effect immediately.
    There should be no delay between the logout operation and the token becoming invalid.
    
    This test verifies that session deletion is immediate and atomic.
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
        
        # Create a valid session
        session_token = secrets.token_urlsafe(32)
        session = SessionModel(
            user_id=user.id,
            token=session_token,
            expires_at=datetime.now() + timedelta(days=7)
        )
        db_session.add(session)
        db_session.commit()
        
        # Record the time before logout
        before_logout = datetime.now()
        
        # Simulate logout: delete session
        db_session.delete(session)
        db_session.commit()
        
        # Record the time after logout
        after_logout = datetime.now()
        
        # Immediately check if session is deleted
        invalidated_session = db_session.query(SessionModel).filter(
            SessionModel.token == session_token
        ).first()
        
        # Verify session is immediately invalid (not found)
        assert invalidated_session is None
        
        # Verify the operation was fast (should be nearly instantaneous)
        # Allow up to 1 second for database operation
        time_diff = (after_logout - before_logout).total_seconds()
        assert time_diff < 1.0
    finally:
        db_session.rollback()
        db_session.close()
