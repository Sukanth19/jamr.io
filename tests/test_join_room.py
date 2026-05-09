"""Unit tests for POST /api/rooms/:room_id/join endpoint."""

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
        user_count=0
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    
    return room


def test_join_room_success(client, authenticated_user, test_room, db_session):
    """Test successful room join."""
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # Make request with session cookie
        response = client.post(
            f"/api/rooms/{test_room.id}/join",
            cookies={"session_token": session_token}
        )
        
        # Assert response
        assert response.status_code == 200
        data = response.json()
        
        assert data["message"] == "Successfully joined room"
        assert data["room_id"] == test_room.id
        assert data["user_id"] == user.id
        assert "joined_at" in data
        
        # Verify room membership was created in database
        membership = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == user.id,
            RoomMembership.room_id == test_room.id
        ).first()
        assert membership is not None
        
        # Verify room user count was incremented
        db_session.refresh(test_room)
        assert test_room.user_count == 1
    finally:
        app.dependency_overrides.clear()


def test_join_room_without_authentication(client, test_room, db_session):
    """Test room join without authentication fails."""
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        response = client.post(f"/api/rooms/{test_room.id}/join")
        
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_join_room_nonexistent_room(client, authenticated_user, db_session):
    """Test joining a nonexistent room fails."""
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # Use a room ID that doesn't exist
        response = client.post(
            "/api/rooms/99999/join",
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


def test_join_room_already_member(client, authenticated_user, test_room, db_session):
    """Test joining a room when already a member returns success."""
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # Create existing membership
        membership = RoomMembership(
            user_id=user.id,
            room_id=test_room.id
        )
        db_session.add(membership)
        test_room.user_count = 1
        db_session.commit()
        db_session.refresh(membership)
        
        # Try to join again
        response = client.post(
            f"/api/rooms/{test_room.id}/join",
            cookies={"session_token": session_token}
        )
        
        # Should return success without creating duplicate
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Already a member of this room"
        assert data["room_id"] == test_room.id
        assert data["user_id"] == user.id
        
        # Verify user count was not incremented again
        db_session.refresh(test_room)
        assert test_room.user_count == 1
        
        # Verify only one membership record exists
        membership_count = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == user.id,
            RoomMembership.room_id == test_room.id
        ).count()
        assert membership_count == 1
    finally:
        app.dependency_overrides.clear()


def test_join_room_increments_user_count(client, authenticated_user, test_room, db_session):
    """Test that joining a room increments the user count by exactly 1."""
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # Set initial user count
        initial_count = 5
        test_room.user_count = initial_count
        db_session.commit()
        
        # Join room
        response = client.post(
            f"/api/rooms/{test_room.id}/join",
            cookies={"session_token": session_token}
        )
        
        assert response.status_code == 200
        
        # Verify user count increased by exactly 1
        db_session.refresh(test_room)
        assert test_room.user_count == initial_count + 1
    finally:
        app.dependency_overrides.clear()


def test_join_room_creates_membership_record(client, authenticated_user, test_room, db_session):
    """Test that joining a room creates a room_memberships record."""
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # Verify no membership exists initially
        membership = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == user.id,
            RoomMembership.room_id == test_room.id
        ).first()
        assert membership is None
        
        # Join room
        response = client.post(
            f"/api/rooms/{test_room.id}/join",
            cookies={"session_token": session_token}
        )
        
        assert response.status_code == 200
        
        # Verify membership record was created
        membership = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == user.id,
            RoomMembership.room_id == test_room.id
        ).first()
        assert membership is not None
        assert membership.user_id == user.id
        assert membership.room_id == test_room.id
        assert membership.joined_at is not None
    finally:
        app.dependency_overrides.clear()
