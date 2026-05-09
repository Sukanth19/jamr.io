"""Unit tests for POST /api/rooms endpoint."""

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


def test_create_room_success(client, authenticated_user, db_session):
    """Test successful room creation."""
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # Create room data
        room_data = {
            "name": "Indie Rock Lovers",
            "description": "A room for fans of indie and alternative rock music",
            "genre_tags": ["rock", "indie"]
        }
        
        # Make request with session cookie
        response = client.post(
            "/api/rooms",
            json=room_data,
            cookies={"session_token": session_token}
        )
        
        # Assert response
        assert response.status_code == 201
        data = response.json()
        
        assert data["name"] == "Indie Rock Lovers"
        assert data["description"] == "A room for fans of indie and alternative rock music"
        assert data["genre_tags"] == ["rock", "indie"]
        assert data["owner_id"] == user.id
        assert data["user_count"] == 0
        assert data["active_jam_link"] is None
        assert "id" in data
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
        
        # Verify room was stored in database
        room = db_session.query(Room).filter(Room.id == data["id"]).first()
        assert room is not None
        assert room.name == "Indie Rock Lovers"
        assert room.owner_id == user.id
    finally:
        app.dependency_overrides.clear()


def test_create_room_without_authentication(client, db_session):
    """Test room creation without authentication fails."""
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        room_data = {
            "name": "Test Room",
            "description": "Test description",
            "genre_tags": ["rock"]
        }
        
        response = client.post("/api/rooms", json=room_data)
        
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_create_room_name_too_short(client, authenticated_user, db_session):
    """Test room creation with name too short fails."""
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        room_data = {
            "name": "AB",  # Only 2 characters
            "description": "Test description",
            "genre_tags": ["rock"]
        }
        
        response = client.post(
            "/api/rooms",
            json=room_data,
            cookies={"session_token": session_token}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert data["detail"]["error"]["field"] == "name"
    finally:
        app.dependency_overrides.clear()


def test_create_room_name_too_long(client, authenticated_user, db_session):
    """Test room creation with name too long fails."""
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        room_data = {
            "name": "A" * 51,  # 51 characters
            "description": "Test description",
            "genre_tags": ["rock"]
        }
        
        response = client.post(
            "/api/rooms",
            json=room_data,
            cookies={"session_token": session_token}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert data["detail"]["error"]["field"] == "name"
    finally:
        app.dependency_overrides.clear()


def test_create_room_description_too_long(client, authenticated_user, db_session):
    """Test room creation with description too long fails."""
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        room_data = {
            "name": "Test Room",
            "description": "A" * 301,  # 301 characters
            "genre_tags": ["rock"]
        }
        
        response = client.post(
            "/api/rooms",
            json=room_data,
            cookies={"session_token": session_token}
        )
        
        # Pydantic validation returns 422 for field validation errors
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_create_room_empty_genre_tags(client, authenticated_user, db_session):
    """Test room creation with empty genre tags fails."""
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        room_data = {
            "name": "Test Room",
            "description": "Test description",
            "genre_tags": []  # Empty array
        }
        
        response = client.post(
            "/api/rooms",
            json=room_data,
            cookies={"session_token": session_token}
        )
        
        # Pydantic validation returns 422 for field validation errors
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_create_room_trims_whitespace(client, authenticated_user, db_session):
    """Test room creation trims whitespace from name."""
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        room_data = {
            "name": "  Test Room  ",  # Name with leading/trailing whitespace
            "description": "Test description",
            "genre_tags": ["rock"]
        }
        
        response = client.post(
            "/api/rooms",
            json=room_data,
            cookies={"session_token": session_token}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Room"  # Whitespace trimmed
    finally:
        app.dependency_overrides.clear()


def test_create_room_without_description(client, authenticated_user, db_session):
    """Test room creation without description succeeds."""
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        room_data = {
            "name": "Test Room",
            "genre_tags": ["rock"]
        }
        
        response = client.post(
            "/api/rooms",
            json=room_data,
            cookies={"session_token": session_token}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Room"
        assert data["description"] is None
    finally:
        app.dependency_overrides.clear()
