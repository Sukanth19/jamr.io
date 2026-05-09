"""Property-based tests for room creation.

Feature: jamr-io-mvp
Tests room creation validation, persistence, and ownership properties.
"""

import pytest
import uuid
from hypothesis import given, strategies as st, settings, assume
from backend.models import Room, User
from backend.recommendation_engine import generate_room_taste_vector
from backend.validators import validate_room_name, validate_room_description
from tests.conftest import get_test_session
import json


# Helper function to create a test user
def create_test_user(db_session, spotify_id=None):
    """Create a test user for room creation tests."""
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


# Property 10: Room Name Validation
# **Validates: Requirements 5.2**
@settings(max_examples=100)
@given(name=st.text(min_size=0, max_size=2))
def test_property_10_room_name_too_short_rejected(name):
    """
    Property 10: Room Name Validation (Part 1 - Too Short)
    
    For any room creation attempt, if the room name length is less than 3 characters,
    the platform must reject the creation and return a validation error.
    
    Feature: jamr-io-mvp, Property 10: Room Name Validation
    """
    # Skip if name becomes valid after stripping
    assume(len(name.strip()) < 3)
    
    is_valid, error_message = validate_room_name(name)
    
    assert is_valid is False
    assert len(error_message) > 0
    assert "3" in error_message or "empty" in error_message.lower()


@settings(max_examples=100)
@given(name=st.text(min_size=51, max_size=100, alphabet=st.characters(min_codepoint=33, max_codepoint=126)))
def test_property_10_room_name_too_long_rejected(name):
    """
    Property 10: Room Name Validation (Part 2 - Too Long)
    
    For any room creation attempt, if the room name length is greater than 50 characters,
    the platform must reject the creation and return a validation error.
    
    Feature: jamr-io-mvp, Property 10: Room Name Validation
    """
    # Skip if name becomes valid after stripping
    assume(len(name.strip()) > 50)
    
    is_valid, error_message = validate_room_name(name)
    
    assert is_valid is False
    assert len(error_message) > 0
    assert "50" in error_message


@settings(max_examples=100)
@given(name=st.text(min_size=3, max_size=50, alphabet=st.characters(min_codepoint=33, max_codepoint=126)))
def test_property_10_room_name_valid_range_accepted(name):
    """
    Property 10: Room Name Validation (Part 3 - Valid Range)
    
    For any room creation attempt, if the room name length is between 3 and 50 characters
    (inclusive), the platform must accept the name.
    
    Feature: jamr-io-mvp, Property 10: Room Name Validation
    """
    is_valid, error_message = validate_room_name(name)
    
    assert is_valid is True
    assert error_message == ""


# Property 11: Room Description Validation
# **Validates: Requirements 5.3**
@settings(max_examples=100)
@given(description=st.text(min_size=301, max_size=500))
def test_property_11_room_description_too_long_rejected(description):
    """
    Property 11: Room Description Validation (Part 1 - Too Long)
    
    For any room creation attempt, if the description length exceeds 300 characters,
    the platform must reject the creation and return a validation error.
    
    Feature: jamr-io-mvp, Property 11: Room Description Validation
    """
    is_valid, error_message = validate_room_description(description)
    
    assert is_valid is False
    assert len(error_message) > 0
    assert "300" in error_message


@settings(max_examples=100)
@given(description=st.text(max_size=300, alphabet=st.characters(blacklist_characters=['\x00'])))
def test_property_11_room_description_valid_range_accepted(description):
    """
    Property 11: Room Description Validation (Part 2 - Valid Range)
    
    For any room creation attempt, if the description length is at most 300 characters,
    the platform must accept the description.
    
    Feature: jamr-io-mvp, Property 11: Room Description Validation
    """
    is_valid, error_message = validate_room_description(description)
    
    assert is_valid is True
    assert error_message == ""


def test_property_11_room_description_empty_accepted():
    """
    Property 11: Room Description Validation (Part 3 - Empty Allowed)
    
    Empty descriptions should be accepted.
    
    Feature: jamr-io-mvp, Property 11: Room Description Validation
    """
    is_valid, error_message = validate_room_description("")
    
    assert is_valid is True
    assert error_message == ""


def test_property_11_room_description_none_accepted():
    """
    Property 11: Room Description Validation (Part 4 - None Allowed)
    
    None descriptions should be accepted (treated as empty).
    
    Feature: jamr-io-mvp, Property 11: Room Description Validation
    """
    is_valid, error_message = validate_room_description(None)
    
    assert is_valid is True
    assert error_message == ""


# Property 12: Room Persistence
# **Validates: Requirements 5.5**
@settings(max_examples=100)
@given(
    name=st.text(min_size=3, max_size=50, alphabet=st.characters(min_codepoint=33, max_codepoint=126)),
    description=st.text(max_size=300, alphabet=st.characters(blacklist_characters=['\x00'])),
    genre_tags=st.lists(
        st.sampled_from(['rock', 'pop', 'hip-hop', 'electronic', 'jazz', 'classical', 'indie', 'metal']),
        min_size=1,
        max_size=5,
        unique=True
    )
)
def test_property_12_room_persistence(name, description, genre_tags):
    """
    Property 12: Room Persistence
    
    For any successful room creation, the room data (name, description, genre_tags,
    owner_id, taste_vector) must be stored in the database and retrievable by room ID.
    
    Feature: jamr-io-mvp, Property 12: Room Persistence
    """
    db_session = get_test_session()
    try:
        # Create a test user
        user = create_test_user(db_session)
    
        # Generate taste vector
        taste_vector = generate_room_taste_vector(genre_tags)
        
        # Create room
        room = Room(
            name=name.strip(),
            description=description if description else None,
            owner_id=user.id,
            genre_tags=genre_tags,
            taste_vector=taste_vector,
            user_count=0
        )
        
        db_session.add(room)
        db_session.commit()
        db_session.refresh(room)
        
        # Verify room was assigned an ID
        assert room.id is not None
        
        # Retrieve room from database
        retrieved_room = db_session.query(Room).filter(Room.id == room.id).first()
        
        # Verify room exists
        assert retrieved_room is not None
        
        # Verify all fields are persisted correctly
        assert retrieved_room.name == name.strip()
        assert retrieved_room.description == (description if description else None)
        assert retrieved_room.owner_id == user.id
        
        # Handle both string (SQLite) and list (PostgreSQL) formats for genre_tags
        if isinstance(retrieved_room.genre_tags, str):
            retrieved_genre_tags = json.loads(retrieved_room.genre_tags)
        else:
            retrieved_genre_tags = retrieved_room.genre_tags
        
        assert retrieved_genre_tags == genre_tags
        
        # Verify taste vector is persisted
        assert retrieved_room.taste_vector is not None
        assert isinstance(retrieved_room.taste_vector, dict)
        
        # Verify taste vector has expected keys
        expected_keys = ['danceability', 'energy', 'valence', 'acousticness', 
                         'instrumentalness', 'speechiness', 'tempo_normalized']
        for key in expected_keys:
            assert key in retrieved_room.taste_vector
            assert isinstance(retrieved_room.taste_vector[key], (int, float))
            assert 0 <= retrieved_room.taste_vector[key] <= 1
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    name=st.text(min_size=3, max_size=50, alphabet=st.characters(min_codepoint=33, max_codepoint=126)),
    genre_tags=st.lists(
        st.sampled_from(['rock', 'pop', 'hip-hop', 'electronic', 'jazz', 'classical', 'indie', 'metal']),
        min_size=1,
        max_size=5,
        unique=True
    )
)
def test_property_12_room_persistence_with_null_description(name, genre_tags):
    """
    Property 12: Room Persistence (Part 2 - Null Description)
    
    For any successful room creation with null description, the room must be stored
    and retrievable with description as None.
    
    Feature: jamr-io-mvp, Property 12: Room Persistence
    """
    db_session = get_test_session()
    try:
        # Create a test user
        user = create_test_user(db_session)
        
        # Generate taste vector
        taste_vector = generate_room_taste_vector(genre_tags)
        
        # Create room with None description
        room = Room(
            name=name.strip(),
            description=None,
            owner_id=user.id,
            genre_tags=genre_tags,
            taste_vector=taste_vector,
            user_count=0
        )
        
        db_session.add(room)
        db_session.commit()
        db_session.refresh(room)
        
        # Retrieve room from database
        retrieved_room = db_session.query(Room).filter(Room.id == room.id).first()
        
        # Verify room exists and description is None
        assert retrieved_room is not None
        assert retrieved_room.description is None
    finally:
        db_session.rollback()
        db_session.close()


# Property 13: Room Ownership Assignment
# **Validates: Requirements 5.7**
@settings(max_examples=100)
@given(
    name=st.text(min_size=3, max_size=50, alphabet=st.characters(min_codepoint=33, max_codepoint=126)),
    description=st.text(max_size=300, alphabet=st.characters(blacklist_characters=['\x00'])),
    genre_tags=st.lists(
        st.sampled_from(['rock', 'pop', 'hip-hop', 'electronic', 'jazz', 'classical', 'indie', 'metal']),
        min_size=1,
        max_size=5,
        unique=True
    ),
    spotify_id=st.text(min_size=5, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789_')
)
def test_property_13_room_ownership_assignment(name, description, genre_tags, spotify_id):
    """
    Property 13: Room Ownership Assignment
    
    For any room creation, the owner_id field must equal the user_id of the
    authenticated user who created the room.
    
    Feature: jamr-io-mvp, Property 13: Room Ownership Assignment
    """
    db_session = get_test_session()
    try:
        # Create a test user with unique spotify_id
        user = create_test_user(db_session, spotify_id=f"{spotify_id}_{uuid.uuid4()}")
        
        # Generate taste vector
        taste_vector = generate_room_taste_vector(genre_tags)
        
        # Create room
        room = Room(
            name=name.strip(),
            description=description if description else None,
            owner_id=user.id,
            genre_tags=genre_tags,
            taste_vector=taste_vector,
            user_count=0
        )
        
        db_session.add(room)
        db_session.commit()
        db_session.refresh(room)
        
        # Verify owner_id matches the creating user's ID
        assert room.owner_id == user.id
        
        # Retrieve room from database and verify ownership persists
        retrieved_room = db_session.query(Room).filter(Room.id == room.id).first()
        assert retrieved_room is not None
        assert retrieved_room.owner_id == user.id
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    name=st.text(min_size=3, max_size=50, alphabet=st.characters(min_codepoint=33, max_codepoint=126)),
    genre_tags=st.lists(
        st.sampled_from(['rock', 'pop', 'hip-hop', 'electronic', 'jazz', 'classical', 'indie', 'metal']),
        min_size=1,
        max_size=5,
        unique=True
    )
)
def test_property_13_room_ownership_different_users(name, genre_tags):
    """
    Property 13: Room Ownership Assignment (Part 2 - Different Users)
    
    For any two rooms created by different users, each room's owner_id must match
    the respective creating user's ID.
    
    Feature: jamr-io-mvp, Property 13: Room Ownership Assignment
    """
    db_session = get_test_session()
    try:
        # Create two different users
        user1 = create_test_user(db_session)
        user2 = create_test_user(db_session)
        
        # Generate taste vector
        taste_vector = generate_room_taste_vector(genre_tags)
        
        # Create room for user1
        room1 = Room(
            name=f"{name.strip()}_1",
            description="Room 1",
            owner_id=user1.id,
            genre_tags=genre_tags,
            taste_vector=taste_vector,
            user_count=0
        )
        
        # Create room for user2
        room2 = Room(
            name=f"{name.strip()}_2",
            description="Room 2",
            owner_id=user2.id,
            genre_tags=genre_tags,
            taste_vector=taste_vector,
            user_count=0
        )
        
        db_session.add(room1)
        db_session.add(room2)
        db_session.commit()
        db_session.refresh(room1)
        db_session.refresh(room2)
        
        # Verify each room has the correct owner
        assert room1.owner_id == user1.id
        assert room2.owner_id == user2.id
        assert room1.owner_id != room2.owner_id
        
        # Retrieve rooms from database and verify ownership persists
        retrieved_room1 = db_session.query(Room).filter(Room.id == room1.id).first()
        retrieved_room2 = db_session.query(Room).filter(Room.id == room2.id).first()
        
        assert retrieved_room1.owner_id == user1.id
        assert retrieved_room2.owner_id == user2.id
    finally:
        db_session.rollback()
        db_session.close()
