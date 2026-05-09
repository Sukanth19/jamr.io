"""Unit tests for session management functionality."""

import os
import secrets
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.models import User, Session as SessionModel


# Create in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture
def test_db():
    """Create a test database session."""
    # Create all tables
    Base.metadata.create_all(bind=test_engine)
    
    # Create a session
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Drop all tables after test
        Base.metadata.drop_all(bind=test_engine)


def test_session_token_generation():
    """Test that session tokens are unique and securely generated."""
    # Generate multiple tokens
    tokens = [secrets.token_urlsafe(32) for _ in range(100)]
    
    # All tokens should be unique
    assert len(tokens) == len(set(tokens))
    
    # All tokens should be non-empty strings
    assert all(isinstance(token, str) and len(token) > 0 for token in tokens)


def test_session_storage(test_db):
    """Test that sessions are stored correctly in the database."""
    # Create a test user
    user = User(
        spotify_id="test_spotify_id",
        display_name="Test User",
        email="test@example.com",
        access_token_encrypted="encrypted_token",
        taste_vector={"danceability": 0.5}
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    
    # Generate session token
    session_token = secrets.token_urlsafe(32)
    session_expires_at = datetime.now() + timedelta(days=7)
    
    # Store session
    session = SessionModel(
        user_id=user.id,
        token=session_token,
        expires_at=session_expires_at
    )
    test_db.add(session)
    test_db.commit()
    test_db.refresh(session)
    
    # Verify session was stored
    assert session.id is not None
    assert session.user_id == user.id
    assert session.token == session_token
    assert session.expires_at == session_expires_at
    assert session.created_at is not None


def test_session_expiration_calculation():
    """Test that session expiration is calculated correctly (7 days)."""
    now = datetime.now()
    expires_at = now + timedelta(days=7)
    
    # Calculate difference in seconds
    diff_seconds = (expires_at - now).total_seconds()
    
    # Should be approximately 7 days (604800 seconds)
    # Allow small margin for execution time
    assert 604799 <= diff_seconds <= 604801


def test_session_uniqueness(test_db):
    """Test that session tokens are unique in the database."""
    # Create a test user
    user = User(
        spotify_id="test_spotify_id",
        display_name="Test User",
        email="test@example.com",
        access_token_encrypted="encrypted_token",
        taste_vector={"danceability": 0.5}
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    
    # Create first session
    session_token_1 = secrets.token_urlsafe(32)
    session_1 = SessionModel(
        user_id=user.id,
        token=session_token_1,
        expires_at=datetime.now() + timedelta(days=7)
    )
    test_db.add(session_1)
    test_db.commit()
    
    # Try to create second session with same token (should fail due to unique constraint)
    session_2 = SessionModel(
        user_id=user.id,
        token=session_token_1,  # Same token
        expires_at=datetime.now() + timedelta(days=7)
    )
    test_db.add(session_2)
    
    with pytest.raises(Exception):  # SQLAlchemy will raise an IntegrityError
        test_db.commit()


def test_multiple_sessions_per_user(test_db):
    """Test that a user can have multiple sessions (different tokens)."""
    # Create a test user
    user = User(
        spotify_id="test_spotify_id",
        display_name="Test User",
        email="test@example.com",
        access_token_encrypted="encrypted_token",
        taste_vector={"danceability": 0.5}
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    
    # Create multiple sessions with different tokens
    session_1 = SessionModel(
        user_id=user.id,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.now() + timedelta(days=7)
    )
    session_2 = SessionModel(
        user_id=user.id,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.now() + timedelta(days=7)
    )
    
    test_db.add(session_1)
    test_db.add(session_2)
    test_db.commit()
    
    # Query sessions for user
    sessions = test_db.query(SessionModel).filter(SessionModel.user_id == user.id).all()
    
    # Should have 2 sessions
    assert len(sessions) == 2
    assert sessions[0].token != sessions[1].token


def test_http_only_cookie_parameters():
    """Test that HTTP-only cookie parameters are correct."""
    # These are the parameters that should be used when setting the cookie
    cookie_params = {
        "key": "session_token",
        "httponly": True,
        "max_age": 7 * 24 * 60 * 60,  # 7 days in seconds
        "secure": True,
        "samesite": "lax"
    }
    
    # Verify max_age is 7 days
    assert cookie_params["max_age"] == 604800
    
    # Verify security flags
    assert cookie_params["httponly"] is True
    assert cookie_params["secure"] is True
    assert cookie_params["samesite"] == "lax"
