"""Integration test for GET /api/rooms/:room_id endpoint."""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from cryptography.fernet import Fernet

from backend.main import app
from backend.models import User, Session as SessionModel, Room
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
    encryptor = get_encryptor()
    test_access_token = "test_access_token_integration"
    encrypted_token = encryptor.encrypt(test_access_token)
    
    user = User(
        spotify_id="test_spotify_id_integration",
        display_name="Integration Test User",
        email="integration@example.com",
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
    session_token = "test_session_token_integration"
    session = SessionModel(
        user_id=user.id,
        token=session_token,
        expires_at=datetime.now() + timedelta(days=7)
    )
    db_session.add(session)
    db_session.commit()
    
    return user, session_token


def test_create_and_get_room_integration(client, authenticated_user, db_session):
    """
    Integration test: Create a room and then retrieve it by ID.
    
    This test demonstrates the full workflow:
    1. Create a room using POST /api/rooms
    2. Retrieve the room using GET /api/rooms/:room_id
    3. Verify all fields match
    """
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # Step 1: Create a room
        room_data = {
            "name": "Integration Test Room",
            "description": "A room created for integration testing",
            "genre_tags": ["rock", "indie", "alternative"]
        }
        
        create_response = client.post(
            "/api/rooms",
            json=room_data,
            cookies={"session_token": session_token}
        )
        
        assert create_response.status_code == 201
        created_room = create_response.json()
        room_id = created_room["id"]
        
        # Step 2: Retrieve the room by ID
        get_response = client.get(f"/api/rooms/{room_id}")
        
        assert get_response.status_code == 200
        retrieved_room = get_response.json()
        
        # Step 3: Verify all fields match
        assert retrieved_room["id"] == created_room["id"]
        assert retrieved_room["name"] == created_room["name"]
        assert retrieved_room["description"] == created_room["description"]
        assert retrieved_room["genre_tags"] == created_room["genre_tags"]
        assert retrieved_room["owner_id"] == created_room["owner_id"]
        assert retrieved_room["user_count"] == created_room["user_count"]
        assert retrieved_room["active_jam_link"] == created_room["active_jam_link"]
        assert retrieved_room["taste_vector"] == created_room["taste_vector"]
        
        # Verify the room is actually in the database
        room_in_db = db_session.query(Room).filter(Room.id == room_id).first()
        assert room_in_db is not None
        assert room_in_db.name == "Integration Test Room"
        assert room_in_db.owner_id == user.id
        
    finally:
        app.dependency_overrides.clear()


def test_get_room_after_updating_jam_link(client, authenticated_user, db_session):
    """
    Integration test: Verify GET endpoint returns updated jam link.
    
    This test demonstrates that the endpoint correctly returns the active_jam_link
    field, which is important for Requirement 8.5.
    """
    user, session_token = authenticated_user
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        # Create a room
        room_data = {
            "name": "Jam Link Test Room",
            "description": "Testing jam link retrieval",
            "genre_tags": ["electronic"]
        }
        
        create_response = client.post(
            "/api/rooms",
            json=room_data,
            cookies={"session_token": session_token}
        )
        
        assert create_response.status_code == 201
        room_id = create_response.json()["id"]
        
        # Update the jam link directly in the database
        room = db_session.query(Room).filter(Room.id == room_id).first()
        room.active_jam_link = "https://open.spotify.com/jam/xyz789"
        db_session.commit()
        
        # Retrieve the room and verify jam link is returned
        get_response = client.get(f"/api/rooms/{room_id}")
        
        assert get_response.status_code == 200
        retrieved_room = get_response.json()
        assert retrieved_room["active_jam_link"] == "https://open.spotify.com/jam/xyz789"
        
    finally:
        app.dependency_overrides.clear()
