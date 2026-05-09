"""Unit tests for GET /api/rooms/:room_id endpoint."""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from cryptography.fernet import Fernet

from backend.main import app
from backend.models import User, Session as SessionModel, Room
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
def test_user(db_session):
    """Create a test user."""
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
    
    return user


@pytest.fixture
def test_room(db_session, test_user):
    """Create a test room."""
    room = Room(
        name="Indie Rock Lovers",
        description="A room for fans of indie and alternative rock music",
        owner_id=test_user.id,
        genre_tags=["rock", "indie"],
        taste_vector={
            'danceability': 0.5,
            'energy': 0.8,
            'valence': 0.6,
            'acousticness': 0.3,
            'instrumentalness': 0.4,
            'speechiness': 0.05,
            'tempo_normalized': 0.65
        },
        active_jam_link="https://open.spotify.com/jam/abc123",
        user_count=5
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    
    return room


def test_get_room_success(client, test_room, db_session):
    """Test successful room retrieval."""
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # Make request
        response = client.get(f"/api/rooms/{test_room.id}")
        
        # Assert response
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == test_room.id
        assert data["name"] == "Indie Rock Lovers"
        assert data["description"] == "A room for fans of indie and alternative rock music"
        assert data["genre_tags"] == ["rock", "indie"]
        assert data["owner_id"] == test_room.owner_id
        assert data["user_count"] == 5
        assert data["active_jam_link"] == "https://open.spotify.com/jam/abc123"
        assert "taste_vector" in data
        assert "created_at" in data
        assert "updated_at" in data
        
        # Verify taste vector structure
        taste_vector = data["taste_vector"]
        assert "danceability" in taste_vector
        assert "energy" in taste_vector
        assert "valence" in taste_vector
        assert "acousticness" in taste_vector
        assert "instrumentalness" in taste_vector
        assert "speechiness" in taste_vector
        assert "tempo_normalized" in taste_vector
    finally:
        app.dependency_overrides.clear()


def test_get_room_not_found(client, db_session):
    """Test room retrieval with non-existent ID returns 404."""
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # Make request with non-existent room ID
        response = client.get("/api/rooms/99999")
        
        # Assert response
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND"
        # The global 404 handler returns a generic message
        assert "not found" in data["error"]["message"].lower()
    finally:
        app.dependency_overrides.clear()


def test_get_room_with_null_jam_link(client, test_user, db_session):
    """Test room retrieval when active_jam_link is null."""
    # Create room without jam link
    room = Room(
        name="Test Room",
        description="Test description",
        owner_id=test_user.id,
        genre_tags=["pop"],
        taste_vector={
            'danceability': 0.7,
            'energy': 0.7,
            'valence': 0.7,
            'acousticness': 0.2,
            'instrumentalness': 0.1,
            'speechiness': 0.1,
            'tempo_normalized': 0.6
        },
        active_jam_link=None,
        user_count=0
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # Make request
        response = client.get(f"/api/rooms/{room.id}")
        
        # Assert response
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == room.id
        assert data["active_jam_link"] is None
    finally:
        app.dependency_overrides.clear()


def test_get_room_with_null_description(client, test_user, db_session):
    """Test room retrieval when description is null."""
    # Create room without description
    room = Room(
        name="Test Room",
        description=None,
        owner_id=test_user.id,
        genre_tags=["jazz"],
        taste_vector={
            'danceability': 0.5,
            'energy': 0.4,
            'valence': 0.5,
            'acousticness': 0.6,
            'instrumentalness': 0.7,
            'speechiness': 0.05,
            'tempo_normalized': 0.5
        },
        active_jam_link=None,
        user_count=0
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # Make request
        response = client.get(f"/api/rooms/{room.id}")
        
        # Assert response
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == room.id
        assert data["description"] is None
    finally:
        app.dependency_overrides.clear()


def test_get_room_returns_all_fields(client, test_room, db_session):
    """Test that get_room returns all required fields."""
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # Make request
        response = client.get(f"/api/rooms/{test_room.id}")
        
        # Assert response
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required fields are present
        required_fields = [
            "id", "name", "description", "genre_tags", "taste_vector",
            "owner_id", "active_jam_link", "user_count", "created_at", "updated_at"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
    finally:
        app.dependency_overrides.clear()


def test_get_room_invalid_id_format(client, db_session):
    """Test room retrieval with invalid ID format."""
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # Make request with invalid ID format (string instead of int)
        response = client.get("/api/rooms/invalid")
        
        # FastAPI returns 422 for invalid path parameter types
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
