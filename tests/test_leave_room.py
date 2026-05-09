"""Unit tests for POST /api/rooms/:room_id/leave endpoint."""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from cryptography.fernet import Fernet

from backend.main import app
from backend.models import User, Session as SessionModel, Room, RoomMembership
from backend.encryption import get_encryptor
from backend.database import get_db
from tests.conftest import get_test_session


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
        spotify_id="test_spotify_id_123",
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
    session_token = "test_session_token_123"
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
        description="A test room for testing",
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
        user_count=1
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    
    return room


@pytest.fixture
def room_membership(db_session, authenticated_user, test_room):
    """Create a room membership for the authenticated user."""
    user, _ = authenticated_user
    
    membership = RoomMembership(
        user_id=user.id,
        room_id=test_room.id
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(membership)
    
    return membership


def test_leave_room_success(client, authenticated_user, test_room, room_membership, db_session):
    """Test successful room leave."""
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # Make request with session cookie
        response = client.post(
            f"/api/rooms/{test_room.id}/leave",
            cookies={"session_token": session_token}
        )
        
        # Assert response
        assert response.status_code == 200
        data = response.json()
        
        assert data["message"] == "Successfully left room"
        assert data["room_id"] == test_room.id
        assert data["user_id"] == user.id
        
        # Verify room membership was deleted from database
        membership = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == user.id,
            RoomMembership.room_id == test_room.id
        ).first()
        assert membership is None
        
        # Verify room user count was decremented
        db_session.refresh(test_room)
        assert test_room.user_count == 0
    finally:
        app.dependency_overrides.clear()


def test_leave_room_without_authentication(client, test_room, db_session):
    """Test room leave without authentication fails."""
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        response = client.post(f"/api/rooms/{test_room.id}/leave")
        
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_leave_room_nonexistent_room(client, authenticated_user, db_session):
    """Test leaving a nonexistent room fails."""
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # Use a room ID that doesn't exist
        response = client.post(
            "/api/rooms/99999/leave",
            cookies={"session_token": session_token}
        )
        
        assert response.status_code == 404
        data = response.json()
        # The response format can be either from HTTPException or global handler
        # Check for either format
        if "detail" in data:
            assert "error" in data["detail"]
            assert data["detail"]["error"]["code"] == "NOT_FOUND"
        elif "error" in data:
            assert data["error"]["code"] == "NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_leave_room_not_member(client, authenticated_user, test_room, db_session):
    """Test leaving a room when not a member fails."""
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # Ensure no membership exists
        membership = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == user.id,
            RoomMembership.room_id == test_room.id
        ).first()
        if membership:
            db_session.delete(membership)
            db_session.commit()
        
        # Try to leave room
        response = client.post(
            f"/api/rooms/{test_room.id}/leave",
            cookies={"session_token": session_token}
        )
        
        # Should return 404 not found
        assert response.status_code == 404
        data = response.json()
        # The response format can be either from HTTPException or global handler
        # Check for either format
        if "detail" in data:
            assert "error" in data["detail"]
            assert data["detail"]["error"]["code"] == "NOT_FOUND"
        elif "error" in data:
            assert data["error"]["code"] == "NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_leave_room_decrements_user_count(client, authenticated_user, test_room, room_membership, db_session):
    """Test that leaving a room decrements the user count by exactly 1."""
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # Set initial user count
        initial_count = 5
        test_room.user_count = initial_count
        db_session.commit()
        
        # Leave room
        response = client.post(
            f"/api/rooms/{test_room.id}/leave",
            cookies={"session_token": session_token}
        )
        
        assert response.status_code == 200
        
        # Verify user count decreased by exactly 1
        db_session.refresh(test_room)
        assert test_room.user_count == initial_count - 1
    finally:
        app.dependency_overrides.clear()


def test_leave_room_deletes_membership_record(client, authenticated_user, test_room, room_membership, db_session):
    """Test that leaving a room deletes the room_memberships record."""
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # Verify membership exists initially
        membership = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == user.id,
            RoomMembership.room_id == test_room.id
        ).first()
        assert membership is not None
        
        # Leave room
        response = client.post(
            f"/api/rooms/{test_room.id}/leave",
            cookies={"session_token": session_token}
        )
        
        assert response.status_code == 200
        
        # Verify membership record was deleted
        membership = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == user.id,
            RoomMembership.room_id == test_room.id
        ).first()
        assert membership is None
    finally:
        app.dependency_overrides.clear()
