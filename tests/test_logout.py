"""Unit tests for logout endpoint."""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.models import User, Session as SessionModel
from backend.database import get_db
from datetime import datetime, timedelta

client = TestClient(app)


def test_logout_success(db_session):
    """Test that logout successfully deletes session and clears cookie."""
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
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
        session_token = "valid_logout_token"
        valid_session = SessionModel(
            user_id=user.id,
            token=session_token,
            expires_at=datetime.now() + timedelta(days=7)
        )
        db_session.add(valid_session)
        db_session.commit()
        
        # Make logout request with session cookie
        response = client.post(
            "/auth/logout",
            cookies={"session_token": session_token}
        )
        
        # Should return 200 success
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"] == "Successfully logged out"
        
        # Verify session was deleted from database
        session = db_session.query(SessionModel).filter(
            SessionModel.token == session_token
        ).first()
        assert session is None
        
        # Verify cookie was cleared (max_age=0)
        set_cookie_header = response.headers.get("set-cookie")
        assert set_cookie_header is not None
        assert "session_token=" in set_cookie_header
        assert "Max-Age=0" in set_cookie_header
    finally:
        app.dependency_overrides.clear()


def test_logout_missing_session_token(db_session):
    """Test that logout returns 401 when session token is missing."""
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        response = client.post("/auth/logout")
        
        # Should return 401 unauthorized
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert data["detail"]["error"]["code"] == "MISSING_SESSION_TOKEN"
    finally:
        app.dependency_overrides.clear()


def test_logout_invalid_session_token(db_session):
    """Test that logout returns 401 when session token is invalid."""
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        response = client.post(
            "/auth/logout",
            cookies={"session_token": "invalid_token"}
        )
        
        # Should return 401 unauthorized
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert data["detail"]["error"]["code"] == "INVALID_SESSION_TOKEN"
    finally:
        app.dependency_overrides.clear()


def test_logout_expired_session_token(db_session):
    """Test that logout returns 401 when session token is expired."""
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
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
        expired_token = "expired_logout_token"
        expired_session = SessionModel(
            user_id=user.id,
            token=expired_token,
            expires_at=datetime.now() - timedelta(days=1)
        )
        db_session.add(expired_session)
        db_session.commit()
        
        # Make logout request with expired token
        response = client.post(
            "/auth/logout",
            cookies={"session_token": expired_token}
        )
        
        # Should return 401 unauthorized
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert data["detail"]["error"]["code"] == "SESSION_EXPIRED"
    finally:
        app.dependency_overrides.clear()


def test_logout_clears_cookie_with_correct_attributes(db_session):
    """Test that logout clears cookie with correct security attributes."""
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
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
        session_token = "valid_token_for_cookie_test"
        valid_session = SessionModel(
            user_id=user.id,
            token=session_token,
            expires_at=datetime.now() + timedelta(days=7)
        )
        db_session.add(valid_session)
        db_session.commit()
        
        # Make logout request
        response = client.post(
            "/auth/logout",
            cookies={"session_token": session_token}
        )
        
        # Verify cookie attributes
        set_cookie_header = response.headers.get("set-cookie")
        assert set_cookie_header is not None
        
        # Check for security attributes
        assert "HttpOnly" in set_cookie_header
        assert "Secure" in set_cookie_header
        assert "SameSite=lax" in set_cookie_header
        assert "Max-Age=0" in set_cookie_header
    finally:
        app.dependency_overrides.clear()


def test_logout_multiple_times(db_session):
    """Test that logout can be called multiple times (idempotent for cookie clearing)."""
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
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
        session_token = "valid_token_for_multiple_logout"
        valid_session = SessionModel(
            user_id=user.id,
            token=session_token,
            expires_at=datetime.now() + timedelta(days=7)
        )
        db_session.add(valid_session)
        db_session.commit()
        
        # First logout - should succeed
        response1 = client.post(
            "/auth/logout",
            cookies={"session_token": session_token}
        )
        assert response1.status_code == 200
        
        # Second logout with same token - should fail (token already deleted)
        response2 = client.post(
            "/auth/logout",
            cookies={"session_token": session_token}
        )
        assert response2.status_code == 401
        assert response2.json()["detail"]["error"]["code"] == "INVALID_SESSION_TOKEN"
    finally:
        app.dependency_overrides.clear()
