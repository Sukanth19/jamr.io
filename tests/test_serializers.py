"""Unit tests for data serialization utilities.

Tests that serializers properly exclude sensitive data from API responses.
"""

import pytest
from datetime import datetime
from backend.models import User, Room, Message
from backend.serializers import serialize_user, serialize_room, serialize_message


def test_serialize_user_excludes_sensitive_fields():
    """
    Test that serialize_user excludes sensitive fields.
    
    Verifies that access_token_encrypted, refresh_token_encrypted,
    and token_expires_at are not included in the serialized output.
    """
    # Create a user with sensitive data
    user = User(
        id=1,
        spotify_id="test_spotify_123",
        display_name="Test User",
        email="test@example.com",
        profile_image_url="https://example.com/image.jpg",
        access_token_encrypted="encrypted_access_token_12345",
        refresh_token_encrypted="encrypted_refresh_token_67890",
        token_expires_at=datetime.now(),
        taste_vector={
            "danceability": 0.65,
            "energy": 0.72,
            "valence": 0.58
        },
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    # Serialize the user
    serialized = serialize_user(user)
    
    # Verify sensitive fields are NOT present
    assert "access_token_encrypted" not in serialized
    assert "refresh_token_encrypted" not in serialized
    assert "token_expires_at" not in serialized
    
    # Verify safe fields ARE present
    assert serialized["id"] == 1
    assert serialized["spotify_id"] == "test_spotify_123"
    assert serialized["display_name"] == "Test User"
    assert serialized["email"] == "test@example.com"
    assert serialized["profile_image_url"] == "https://example.com/image.jpg"
    assert serialized["taste_vector"] == user.taste_vector
    assert "created_at" in serialized
    assert "updated_at" in serialized


def test_serialize_user_can_exclude_email():
    """
    Test that serialize_user can optionally exclude email.
    
    Verifies that the include_email parameter works correctly.
    """
    user = User(
        id=1,
        spotify_id="test_spotify_123",
        display_name="Test User",
        email="test@example.com",
        access_token_encrypted="encrypted_token",
        taste_vector={"danceability": 0.5},
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    # Serialize without email
    serialized = serialize_user(user, include_email=False)
    
    # Verify email is NOT present
    assert "email" not in serialized
    
    # Verify other safe fields ARE present
    assert serialized["id"] == 1
    assert serialized["display_name"] == "Test User"


def test_serialize_user_handles_none_values():
    """
    Test that serialize_user handles None values gracefully.
    
    Verifies that optional fields with None values are handled correctly.
    """
    user = User(
        id=1,
        spotify_id="test_spotify_123",
        display_name="Test User",
        email=None,
        profile_image_url=None,
        access_token_encrypted="encrypted_token",
        taste_vector={"danceability": 0.5},
        created_at=None,
        updated_at=None
    )
    
    # Serialize the user
    serialized = serialize_user(user)
    
    # Verify None values are handled
    assert serialized["email"] is None
    assert serialized["profile_image_url"] is None
    assert serialized["created_at"] is None
    assert serialized["updated_at"] is None
    
    # Verify required fields are still present
    assert serialized["id"] == 1
    assert serialized["display_name"] == "Test User"


def test_serialize_room_includes_all_safe_fields():
    """
    Test that serialize_room includes all room fields.
    
    Rooms don't have sensitive data, so all fields should be included.
    """
    room = Room(
        id=1,
        name="Rock Lovers",
        description="A room for rock music fans",
        owner_id=1,
        genre_tags=["rock", "indie"],
        taste_vector={"danceability": 0.6, "energy": 0.8},
        active_jam_link="https://open.spotify.com/jam/abc123",
        user_count=5,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    # Serialize the room
    serialized = serialize_room(room)
    
    # Verify all fields are present
    assert serialized["id"] == 1
    assert serialized["name"] == "Rock Lovers"
    assert serialized["description"] == "A room for rock music fans"
    assert serialized["owner_id"] == 1
    assert serialized["genre_tags"] == ["rock", "indie"]
    assert serialized["taste_vector"] == room.taste_vector
    assert serialized["active_jam_link"] == "https://open.spotify.com/jam/abc123"
    assert serialized["user_count"] == 5
    assert "created_at" in serialized
    assert "updated_at" in serialized


def test_serialize_message_includes_username():
    """
    Test that serialize_message can include username.
    
    Verifies that the optional username parameter works correctly.
    """
    message = Message(
        id=1,
        room_id=1,
        user_id=1,
        content="Hello, world!",
        created_at=datetime.now()
    )
    
    # Serialize with username
    serialized = serialize_message(message, username="Test User")
    
    # Verify all fields are present
    assert serialized["id"] == 1
    assert serialized["room_id"] == 1
    assert serialized["user_id"] == 1
    assert serialized["content"] == "Hello, world!"
    assert serialized["username"] == "Test User"
    assert "created_at" in serialized


def test_serialize_message_without_username():
    """
    Test that serialize_message works without username.
    
    Verifies that username is optional.
    """
    message = Message(
        id=1,
        room_id=1,
        user_id=1,
        content="Hello, world!",
        created_at=datetime.now()
    )
    
    # Serialize without username
    serialized = serialize_message(message)
    
    # Verify username is NOT present
    assert "username" not in serialized
    
    # Verify other fields are present
    assert serialized["id"] == 1
    assert serialized["content"] == "Hello, world!"


def test_utc_isoformat_marks_naive_timestamps_as_utc():
    """Naive DB timestamps (UTC) must carry an offset so browsers don't treat them as local time."""
    from datetime import timezone, timedelta
    from backend.serializers import utc_isoformat
    
    assert utc_isoformat(datetime(2026, 11, 8, 18, 7)) == "2026-11-08T18:07:00+00:00"
    assert utc_isoformat(None) is None
    
    # Already timezone-aware values are left as they are
    ist = timezone(timedelta(hours=5, minutes=30))
    assert utc_isoformat(datetime(2026, 11, 8, 23, 37, tzinfo=ist)) == "2026-11-08T23:37:00+05:30"
