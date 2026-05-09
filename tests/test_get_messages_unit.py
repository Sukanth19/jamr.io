"""Unit tests for GET /api/rooms/:room_id/messages endpoint."""

import pytest
import uuid
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from backend.main import app
from backend.models import Room, User, Message
from backend.recommendation_engine import generate_room_taste_vector
from tests.conftest import get_test_session


def create_test_user(db_session, spotify_id=None):
    """Create a test user."""
    if spotify_id is None:
        spotify_id = f"test_user_{uuid.uuid4()}"
    user = User(
        spotify_id=spotify_id,
        display_name="Test User",
        email="test@example.com",
        access_token_encrypted="encrypted_token",
        taste_vector={
            "danceability": 0.65,
            "energy": 0.72,
            "valence": 0.58,
            "acousticness": 0.23,
            "instrumentalness": 0.05,
            "speechiness": 0.08,
            "tempo_normalized": 0.55
        }
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_test_room(db_session, owner_id, name=None):
    """Create a test room."""
    if name is None:
        name = f"Test Room {uuid.uuid4()}"
    
    genre_tags = ['rock', 'indie']
    taste_vector = generate_room_taste_vector(genre_tags)
    
    room = Room(
        name=name,
        description="A test room for testing",
        owner_id=owner_id,
        genre_tags=genre_tags,
        taste_vector=taste_vector,
        user_count=0
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return room


def create_test_message(db_session, room_id, user_id, content, created_at=None):
    """Create a test message."""
    message = Message(
        room_id=room_id,
        user_id=user_id,
        content=content,
        created_at=created_at
    )
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)
    return message


def test_get_messages_empty_room():
    """Test getting messages from an empty room."""
    db_session = get_test_session()
    try:
        # Create user and room
        user = create_test_user(db_session)
        room = create_test_room(db_session, owner_id=user.id)
        
        # Make request
        client = TestClient(app)
        response = client.get(f"/api/rooms/{room.id}/messages")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["room_id"] == room.id
        assert data["total"] == 0
        assert len(data["messages"]) == 0
        
    finally:
        db_session.rollback()
        db_session.close()


def test_get_messages_with_messages():
    """Test getting messages from a room with messages."""
    db_session = get_test_session()
    try:
        # Create user and room
        user = create_test_user(db_session)
        room = create_test_room(db_session, owner_id=user.id)
        
        # Create 10 messages
        base_time = datetime.now()
        for i in range(10):
            timestamp = base_time + timedelta(seconds=i)
            create_test_message(
                db_session,
                room_id=room.id,
                user_id=user.id,
                content=f"Message {i}",
                created_at=timestamp
            )
        
        # Make request
        client = TestClient(app)
        response = client.get(f"/api/rooms/{room.id}/messages")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["room_id"] == room.id
        assert data["total"] == 10
        assert len(data["messages"]) == 10
        
        # Verify messages are ordered by created_at descending
        messages = data["messages"]
        assert messages[0]["content"] == "Message 9"  # Most recent
        assert messages[-1]["content"] == "Message 0"  # Oldest
        
        # Verify user information is included
        for message in messages:
            assert message["user_id"] == user.id
            assert message["username"] == user.display_name
            assert message["content"] is not None
            assert message["created_at"] is not None
        
    finally:
        db_session.rollback()
        db_session.close()


def test_get_messages_limit_50():
    """Test that only 50 most recent messages are returned."""
    db_session = get_test_session()
    try:
        # Create user and room
        user = create_test_user(db_session)
        room = create_test_room(db_session, owner_id=user.id)
        
        # Create 100 messages
        base_time = datetime.now()
        for i in range(100):
            timestamp = base_time + timedelta(seconds=i)
            create_test_message(
                db_session,
                room_id=room.id,
                user_id=user.id,
                content=f"Message {i}",
                created_at=timestamp
            )
        
        # Make request
        client = TestClient(app)
        response = client.get(f"/api/rooms/{room.id}/messages")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["room_id"] == room.id
        assert data["total"] == 50  # Limited to 50
        assert len(data["messages"]) == 50
        
        # Verify we got the most recent 50 messages
        messages = data["messages"]
        assert messages[0]["content"] == "Message 99"  # Most recent
        assert messages[-1]["content"] == "Message 50"  # 50th most recent
        
        # Verify older messages are not included
        message_contents = [msg["content"] for msg in messages]
        assert "Message 0" not in message_contents
        assert "Message 49" not in message_contents
        
    finally:
        db_session.rollback()
        db_session.close()


def test_get_messages_nonexistent_room():
    """Test getting messages from a nonexistent room."""
    client = TestClient(app)
    response = client.get("/api/rooms/99999/messages")
    
    # Verify 404 response
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"


def test_get_messages_multiple_users():
    """Test getting messages from multiple users."""
    db_session = get_test_session()
    try:
        # Create users and room
        user1 = create_test_user(db_session, spotify_id=f"user1_{uuid.uuid4()}")
        user2 = create_test_user(db_session, spotify_id=f"user2_{uuid.uuid4()}")
        room = create_test_room(db_session, owner_id=user1.id)
        
        # Create messages from different users
        base_time = datetime.now()
        create_test_message(db_session, room.id, user1.id, "Message from user1", base_time)
        create_test_message(db_session, room.id, user2.id, "Message from user2", base_time + timedelta(seconds=1))
        
        # Make request
        client = TestClient(app)
        response = client.get(f"/api/rooms/{room.id}/messages")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        
        # Verify user information is correct for each message
        messages = data["messages"]
        assert messages[0]["user_id"] == user2.id
        assert messages[0]["username"] == user2.display_name
        assert messages[1]["user_id"] == user1.id
        assert messages[1]["username"] == user1.display_name
        
    finally:
        db_session.rollback()
        db_session.close()
