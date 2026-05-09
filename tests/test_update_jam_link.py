"""Integration tests for PUT /api/rooms/:room_id/jam-link endpoint.

Feature: jamr-io-mvp
Tests the Spotify Jam link update endpoint.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from cryptography.fernet import Fernet

from backend.main import app
from backend.models import User, Session as SessionModel, Room, RoomMembership
from backend.encryption import get_encryptor
from backend.database import get_db


# Generate a valid Fernet key for testing
TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def set_test_encryption_key(monkeypatch):
    """Set a test encryption key for all tests in this module."""
    monkeypatch.setenv('ENCRYPTION_KEY', TEST_ENCRYPTION_KEY)
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///test.db')


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def authenticated_user(db_session):
    """Create an authenticated user with a valid session."""
    # Create a test user with taste vector
    encryptor = get_encryptor()
    test_access_token = "test_access_token_123"
    encrypted_token = encryptor.encrypt(test_access_token)
    
    user = User(
        spotify_id="test_spotify_id_jam_link",
        display_name="Test User",
        email="test@example.com",
        access_token_encrypted=encrypted_token,
        taste_vector={
            'danceability': 0.6,
            'energy': 0.7,
            'valence': 0.5,
            'acousticness': 0.3,
            'instrumentalness': 0.2,
            'speechiness': 0.1,
            'tempo_normalized': 0.6
        }
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # Create a session for the user
    session_token = "test_session_token_jam_link"
    session = SessionModel(
        user_id=user.id,
        token=session_token,
        expires_at=datetime.now() + timedelta(days=7)
    )
    db_session.add(session)
    db_session.commit()
    
    return user, session_token


@pytest.fixture
def test_room(db_session, authenticated_user):
    """Create a test room."""
    user, _ = authenticated_user
    
    room = Room(
        name="Test Room",
        description="A test room for jam link testing",
        owner_id=user.id,
        genre_tags=["rock", "indie"],
        taste_vector={
            'danceability': 0.6,
            'energy': 0.7,
            'valence': 0.5,
            'acousticness': 0.3,
            'instrumentalness': 0.2,
            'speechiness': 0.1,
            'tempo_normalized': 0.6
        },
        user_count=0
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    
    return room


@pytest.fixture
def test_membership(db_session, authenticated_user, test_room):
    """Create a room membership for the test user."""
    user, _ = authenticated_user
    
    membership = RoomMembership(
        user_id=user.id,
        room_id=test_room.id
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(membership)
    
    return membership


def test_update_jam_link_success(client, authenticated_user, test_room, test_membership, db_session):
    """
    Test successful Spotify Jam link update.
    
    Validates: Requirements 8.1, 8.2, 8.3, 8.7
    """
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # Valid Spotify Jam link
        jam_link = "https://open.spotify.com/jam/abc123xyz"
        
        # Update jam link
        response = client.put(
            f"/api/rooms/{test_room.id}/jam-link",
            json={"link": jam_link},
            cookies={"session_token": session_token}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Successfully updated Spotify Jam link"
        assert data["room_id"] == test_room.id
        assert data["active_jam_link"] == jam_link
        assert data["updated_by"] == user.id
        assert "updated_at" in data
    finally:
        app.dependency_overrides.clear()


def test_update_jam_link_requires_authentication(client, test_room, db_session):
    """
    Test that updating jam link requires authentication.
    
    Validates: Requirements 8.1
    """
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # No session cookie
        jam_link = "https://open.spotify.com/jam/abc123xyz"
        
        response = client.put(
            f"/api/rooms/{test_room.id}/jam-link",
            json={"link": jam_link}
        )
        
        # Should return 401 Unauthorized
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_update_jam_link_requires_membership(client, authenticated_user, test_room, db_session):
    """
    Test that only room members can update jam link.
    
    Validates: Requirements 8.7
    """
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # User is authenticated but not a member
        jam_link = "https://open.spotify.com/jam/abc123xyz"
        
        response = client.put(
            f"/api/rooms/{test_room.id}/jam-link",
            json={"link": jam_link},
            cookies={"session_token": session_token}
        )
        
        # Should return 403 Forbidden
        assert response.status_code == 403
        data = response.json()
        # Check for either format (detail or error)
        if "detail" in data:
            assert data["detail"]["error"]["code"] == "FORBIDDEN"
            assert "member" in data["detail"]["error"]["message"].lower()
        else:
            assert data["error"]["code"] == "FORBIDDEN"
            assert "member" in data["error"]["message"].lower()
    finally:
        app.dependency_overrides.clear()


def test_update_jam_link_invalid_format(client, authenticated_user, test_room, test_membership, db_session):
    """
    Test that invalid Spotify Jam link format is rejected.
    
    Validates: Requirements 8.2
    """
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # Invalid jam link (wrong domain)
        invalid_link = "https://example.com/jam/abc123"
        
        response = client.put(
            f"/api/rooms/{test_room.id}/jam-link",
            json={"link": invalid_link},
            cookies={"session_token": session_token}
        )
        
        # Should return 400 Bad Request
        assert response.status_code == 400
        data = response.json()
        # Check for either format (detail or error)
        if "detail" in data:
            assert data["detail"]["error"]["code"] == "VALIDATION_ERROR"
        else:
            assert data["error"]["code"] == "VALIDATION_ERROR"
            assert "format" in data["error"]["message"].lower()
    finally:
        app.dependency_overrides.clear()


def test_update_jam_link_room_not_found(client, authenticated_user, db_session):
    """
    Test that updating jam link for non-existent room returns 404.
    
    Validates: Requirements 8.1
    """
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        jam_link = "https://open.spotify.com/jam/abc123xyz"
        
        # Non-existent room ID
        response = client.put(
            "/api/rooms/99999/jam-link",
            json={"link": jam_link},
            cookies={"session_token": session_token}
        )
        
        # Should return 404 Not Found
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_update_jam_link_stores_in_database(client, authenticated_user, test_room, test_membership, db_session):
    """
    Test that jam link is stored in database.
    
    Validates: Requirements 8.3
    """
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        jam_link = "https://open.spotify.com/jam/abc123xyz"
        
        # Update jam link
        response = client.put(
            f"/api/rooms/{test_room.id}/jam-link",
            json={"link": jam_link},
            cookies={"session_token": session_token}
        )
        
        assert response.status_code == 200
        
        # Verify it's stored in database
        db_session.refresh(test_room)
        assert test_room.active_jam_link == jam_link
    finally:
        app.dependency_overrides.clear()


def test_update_jam_link_multiple_times(client, authenticated_user, test_room, test_membership, db_session):
    """
    Test that jam link can be updated multiple times.
    
    Validates: Requirements 8.3
    """
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # First update
        jam_link_1 = "https://open.spotify.com/jam/abc123"
        response = client.put(
            f"/api/rooms/{test_room.id}/jam-link",
            json={"link": jam_link_1},
            cookies={"session_token": session_token}
        )
        assert response.status_code == 200
        
        # Second update
        jam_link_2 = "https://open.spotify.com/jam/xyz789"
        response = client.put(
            f"/api/rooms/{test_room.id}/jam-link",
            json={"link": jam_link_2},
            cookies={"session_token": session_token}
        )
        assert response.status_code == 200
        
        # Verify latest link is stored
        db_session.refresh(test_room)
        assert test_room.active_jam_link == jam_link_2
    finally:
        app.dependency_overrides.clear()


def test_update_jam_link_empty_link_rejected(client, authenticated_user, test_room, test_membership, db_session):
    """
    Test that empty jam link is rejected.
    
    Validates: Requirements 8.2
    """
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        response = client.put(
            f"/api/rooms/{test_room.id}/jam-link",
            json={"link": ""},
            cookies={"session_token": session_token}
        )
        
        # Should return 400 Bad Request
        assert response.status_code == 400
        data = response.json()
        # Check for either format (detail or error)
        if "detail" in data:
            assert data["detail"]["error"]["code"] == "VALIDATION_ERROR"
        else:
            assert data["error"]["code"] == "VALIDATION_ERROR"
    finally:
        app.dependency_overrides.clear()


def test_update_jam_link_http_rejected(client, authenticated_user, test_room, test_membership, db_session):
    """
    Test that HTTP (non-HTTPS) jam link is rejected.
    
    Validates: Requirements 8.2
    """
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # HTTP instead of HTTPS
        http_link = "http://open.spotify.com/jam/abc123"
        
        response = client.put(
            f"/api/rooms/{test_room.id}/jam-link",
            json={"link": http_link},
            cookies={"session_token": session_token}
        )
        
        # Should return 400 Bad Request
        assert response.status_code == 400
        data = response.json()
        # Check for either format (detail or error)
        if "detail" in data:
            assert data["detail"]["error"]["code"] == "VALIDATION_ERROR"
        else:
            assert data["error"]["code"] == "VALIDATION_ERROR"
    finally:
        app.dependency_overrides.clear()
