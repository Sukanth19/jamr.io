"""Unit tests for authentication endpoints."""

import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from backend.main import app

client = TestClient(app)


def test_spotify_oauth_redirect_success():
    """Test that /auth/spotify redirects to Spotify with correct parameters."""
    # Mock environment variables
    with patch.dict(os.environ, {
        'SPOTIFY_CLIENT_ID': 'test_client_id',
        'SPOTIFY_REDIRECT_URI': 'http://localhost:8000/auth/callback'
    }):
        response = client.get("/auth/spotify", follow_redirects=False)
        
        # Should return 302 redirect
        assert response.status_code == 302
        
        # Check redirect location
        location = response.headers.get("location")
        assert location is not None
        assert location.startswith("https://accounts.spotify.com/authorize")
        
        # Verify required parameters in URL
        assert "client_id=test_client_id" in location
        assert "response_type=code" in location
        assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fauth%2Fcallback" in location
        assert "state=" in location
        assert "scope=user-read-email+user-top-read" in location


def test_spotify_oauth_redirect_missing_client_id():
    """Test that /auth/spotify returns error when client ID is missing."""
    with patch.dict(os.environ, {
        'SPOTIFY_CLIENT_ID': '',
        'SPOTIFY_REDIRECT_URI': 'http://localhost:8000/auth/callback'
    }, clear=False):
        response = client.get("/auth/spotify")
        
        # Should return 500 error
        assert response.status_code == 500
        
        # Check error message
        data = response.json()
        assert "detail" in data
        assert "Spotify client ID not configured" in data["detail"]


def test_spotify_oauth_redirect_missing_redirect_uri():
    """Test that /auth/spotify returns error when redirect URI is missing."""
    with patch.dict(os.environ, {
        'SPOTIFY_CLIENT_ID': 'test_client_id',
        'SPOTIFY_REDIRECT_URI': ''
    }, clear=False):
        response = client.get("/auth/spotify")
        
        # Should return 500 error
        assert response.status_code == 500
        
        # Check error message
        data = response.json()
        assert "detail" in data
        assert "Spotify redirect URI not configured" in data["detail"]


def test_state_parameter_is_unique():
    """Test that each request generates a unique state parameter."""
    with patch.dict(os.environ, {
        'SPOTIFY_CLIENT_ID': 'test_client_id',
        'SPOTIFY_REDIRECT_URI': 'http://localhost:8000/auth/callback'
    }):
        # Make two requests
        response1 = client.get("/auth/spotify", follow_redirects=False)
        response2 = client.get("/auth/spotify", follow_redirects=False)
        
        # Extract state parameters
        location1 = response1.headers.get("location")
        location2 = response2.headers.get("location")
        
        state1 = [param.split("=")[1] for param in location1.split("&") if param.startswith("state=")][0]
        state2 = [param.split("=")[1] for param in location2.split("&") if param.startswith("state=")][0]
        
        # States should be different
        assert state1 != state2


def test_verify_state_valid():
    """Test that verify_state accepts valid state tokens."""
    from backend.auth import verify_state, _state_store
    from datetime import datetime, timedelta
    
    # Add a valid state token
    test_state = "test_state_token"
    _state_store[test_state] = datetime.now() + timedelta(minutes=5)
    
    # Verify it
    assert verify_state(test_state) is True
    
    # State should be removed after verification (one-time use)
    assert test_state not in _state_store


def test_verify_state_expired():
    """Test that verify_state rejects expired state tokens."""
    from backend.auth import verify_state, _state_store
    from datetime import datetime, timedelta
    
    # Add an expired state token
    test_state = "expired_state_token"
    _state_store[test_state] = datetime.now() - timedelta(minutes=1)
    
    # Verify it
    assert verify_state(test_state) is False
    
    # State should be removed
    assert test_state not in _state_store


def test_verify_state_invalid():
    """Test that verify_state rejects invalid state tokens."""
    from backend.auth import verify_state
    
    # Try to verify a non-existent state
    assert verify_state("nonexistent_state") is False


def test_oauth_callback_missing_code():
    """Test that /auth/callback returns error when code is missing."""
    response = client.get("/auth/callback?state=test_state")
    
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert data["detail"]["error"]["code"] == "MISSING_CODE"


def test_oauth_callback_missing_state():
    """Test that /auth/callback returns error when state is missing."""
    response = client.get("/auth/callback?code=test_code")
    
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert data["detail"]["error"]["code"] == "MISSING_STATE"


def test_oauth_callback_invalid_state():
    """Test that /auth/callback returns error when state is invalid."""
    response = client.get("/auth/callback?code=test_code&state=invalid_state")
    
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert data["detail"]["error"]["code"] == "INVALID_STATE"


def test_oauth_callback_authorization_denied():
    """Test that /auth/callback handles user denial of authorization."""
    response = client.get("/auth/callback?error=access_denied&state=test_state")
    
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert data["detail"]["error"]["code"] == "AUTHORIZATION_DENIED"



def test_get_current_user_missing_token(db_session):
    """Test that get_current_user raises 401 when session token is missing."""
    from backend.auth import get_current_user
    from fastapi import HTTPException
    
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(session_token=None, db=db_session)
    
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["error"]["code"] == "MISSING_SESSION_TOKEN"


def test_get_current_user_invalid_token(db_session):
    """Test that get_current_user raises 401 when session token is invalid."""
    from backend.auth import get_current_user
    from fastapi import HTTPException
    
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(session_token="invalid_token", db=db_session)
    
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["error"]["code"] == "INVALID_SESSION_TOKEN"


def test_get_current_user_expired_token(db_session):
    """Test that get_current_user raises 401 when session token is expired."""
    from backend.auth import get_current_user
    from backend.models import User, Session as SessionModel
    from datetime import datetime, timedelta
    from fastapi import HTTPException
    
    # Create a test user
    user = User(
        spotify_id="test_spotify_id",
        display_name="Test User",
        email="test@example.com",
        access_token_encrypted="encrypted_token",
        taste_vector={"danceability": 0.5}
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # Create an expired session
    expired_session = SessionModel(
        user_id=user.id,
        token="expired_token",
        expires_at=datetime.now() - timedelta(days=1)
    )
    db_session.add(expired_session)
    db_session.commit()
    
    # Try to use expired token
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(session_token="expired_token", db=db_session)
    
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["error"]["code"] == "SESSION_EXPIRED"
    
    # Verify expired session was deleted
    session = db_session.query(SessionModel).filter(
        SessionModel.token == "expired_token"
    ).first()
    assert session is None


def test_get_current_user_valid_token(db_session):
    """Test that get_current_user returns user when session token is valid."""
    from backend.auth import get_current_user
    from backend.models import User, Session as SessionModel
    from datetime import datetime, timedelta
    
    # Create a test user
    user = User(
        spotify_id="test_spotify_id",
        display_name="Test User",
        email="test@example.com",
        access_token_encrypted="encrypted_token",
        taste_vector={"danceability": 0.5}
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # Create a valid session
    valid_session = SessionModel(
        user_id=user.id,
        token="valid_token",
        expires_at=datetime.now() + timedelta(days=7)
    )
    db_session.add(valid_session)
    db_session.commit()
    
    # Get current user
    current_user = get_current_user(session_token="valid_token", db=db_session)
    
    # Verify user is returned
    assert current_user is not None
    assert current_user.id == user.id
    assert current_user.spotify_id == "test_spotify_id"
    assert current_user.display_name == "Test User"


def test_get_current_user_session_without_user(db_session):
    """Test that get_current_user raises 401 when session exists but user doesn't.
    
    Note: This test temporarily disables foreign key constraints to simulate
    a data integrity issue that shouldn't happen in production.
    """
    from backend.auth import get_current_user
    from backend.models import Session as SessionModel
    from datetime import datetime, timedelta
    from fastapi import HTTPException
    from sqlalchemy import text
    
    # Temporarily disable foreign key constraints for this test
    db_session.execute(text("PRAGMA foreign_keys=OFF"))
    
    # Create a session with non-existent user_id
    orphan_session = SessionModel(
        user_id=99999,  # Non-existent user
        token="orphan_token",
        expires_at=datetime.now() + timedelta(days=7)
    )
    db_session.add(orphan_session)
    db_session.commit()
    
    # Re-enable foreign key constraints
    db_session.execute(text("PRAGMA foreign_keys=ON"))
    
    # Try to use orphan token
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(session_token="orphan_token", db=db_session)
    
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["error"]["code"] == "USER_NOT_FOUND"
