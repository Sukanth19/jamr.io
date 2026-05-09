"""Property-based tests for database models.

Feature: jamr-io-mvp
Tests database persistence and referential integrity properties.
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta
from backend.models import User, Room, Message, RoomMembership, Session
from sqlalchemy.exc import IntegrityError
from tests.conftest import get_test_session


# Custom strategies for generating test data
@st.composite
def user_data(draw):
    """Generate valid user data."""
    # Generate a unique spotify_id using a UUID-like string
    import uuid
    unique_id = str(uuid.uuid4())
    
    # Filter strategy to exclude surrogate characters and null bytes
    valid_text = st.characters(
        blacklist_categories=('Cs',),  # Exclude surrogates
        blacklist_characters=['\x00']  # Exclude null bytes
    )
    
    return {
        "spotify_id": unique_id,
        "display_name": draw(st.text(min_size=1, max_size=255, alphabet=valid_text)),
        "email": draw(st.emails()),
        "profile_image_url": draw(st.text(max_size=500, alphabet=valid_text)),
        "access_token_encrypted": draw(st.text(min_size=1, max_size=1000, alphabet=valid_text)),
        "refresh_token_encrypted": draw(st.text(min_size=1, max_size=1000, alphabet=valid_text)),
        "taste_vector": {
            "danceability": draw(st.floats(min_value=0.0, max_value=1.0)),
            "energy": draw(st.floats(min_value=0.0, max_value=1.0)),
            "valence": draw(st.floats(min_value=0.0, max_value=1.0)),
            "acousticness": draw(st.floats(min_value=0.0, max_value=1.0)),
            "instrumentalness": draw(st.floats(min_value=0.0, max_value=1.0)),
            "speechiness": draw(st.floats(min_value=0.0, max_value=1.0)),
            "tempo_normalized": draw(st.floats(min_value=0.0, max_value=1.0))
        }
    }


@st.composite
def room_data(draw):
    """Generate valid room data."""
    # Filter strategy to exclude surrogate characters and null bytes
    valid_text = st.characters(
        blacklist_categories=('Cs',),  # Exclude surrogates
        blacklist_characters=['\x00']  # Exclude null bytes
    )
    
    return {
        "name": draw(st.text(min_size=3, max_size=50, alphabet=valid_text)),
        "description": draw(st.text(max_size=300, alphabet=valid_text)),
        "genre_tags": draw(st.lists(st.text(min_size=1, max_size=50, alphabet=valid_text), min_size=1, max_size=10)),
        "taste_vector": {
            "danceability": draw(st.floats(min_value=0.0, max_value=1.0)),
            "energy": draw(st.floats(min_value=0.0, max_value=1.0)),
            "valence": draw(st.floats(min_value=0.0, max_value=1.0)),
            "acousticness": draw(st.floats(min_value=0.0, max_value=1.0)),
            "instrumentalness": draw(st.floats(min_value=0.0, max_value=1.0)),
            "speechiness": draw(st.floats(min_value=0.0, max_value=1.0)),
            "tempo_normalized": draw(st.floats(min_value=0.0, max_value=1.0))
        }
    }


# Property 36: User Data Persistence
# **Validates: Requirements 12.1**
@settings(max_examples=100)
@given(data=user_data())
def test_user_data_persistence(data):
    """
    Property 36: User Data Persistence
    
    For any user stored in the database, the record must contain non-null values 
    for spotify_id, display_name, access_token_encrypted, and taste_vector fields.
    """
    db_session = get_test_session()
    try:
        # Create user with generated data
        user = User(**data)
        db_session.add(user)
        db_session.commit()
        
        # Retrieve user from database
        retrieved_user = db_session.query(User).filter(User.id == user.id).first()
        
        # Assert all required fields are non-null
        assert retrieved_user is not None
        assert retrieved_user.spotify_id is not None
        assert retrieved_user.display_name is not None
        assert retrieved_user.access_token_encrypted is not None
        assert retrieved_user.taste_vector is not None
        
        # Assert values match
        assert retrieved_user.spotify_id == data["spotify_id"]
        assert retrieved_user.display_name == data["display_name"]
        assert retrieved_user.access_token_encrypted == data["access_token_encrypted"]
        assert retrieved_user.taste_vector == data["taste_vector"]
    finally:
        db_session.rollback()
        db_session.close()


# Property 37: Room Data Persistence
# **Validates: Requirements 12.2**
@settings(max_examples=100)
@given(user_data_val=user_data(), room_data_val=room_data())
def test_room_data_persistence(user_data_val, room_data_val):
    """
    Property 37: Room Data Persistence
    
    For any room stored in the database, the record must contain non-null values 
    for name, genre_tags, taste_vector, and owner_id fields.
    """
    db_session = get_test_session()
    try:
        # Create owner user first
        owner = User(**user_data_val)
        db_session.add(owner)
        db_session.commit()
        
        # Create room with generated data
        room = Room(owner_id=owner.id, **room_data_val)
        db_session.add(room)
        db_session.commit()
        
        # Retrieve room from database
        retrieved_room = db_session.query(Room).filter(Room.id == room.id).first()
        
        # Assert all required fields are non-null
        assert retrieved_room is not None
        assert retrieved_room.name is not None
        assert retrieved_room.genre_tags is not None
        assert retrieved_room.taste_vector is not None
        assert retrieved_room.owner_id is not None
        
        # Assert values match
        assert retrieved_room.name == room_data_val["name"]
        assert retrieved_room.genre_tags == room_data_val["genre_tags"]
        assert retrieved_room.taste_vector == room_data_val["taste_vector"]
        assert retrieved_room.owner_id == owner.id
    finally:
        db_session.rollback()
        db_session.close()


# Property 38: Message Data Persistence
# **Validates: Requirements 12.3**
@settings(max_examples=100)
@given(
    user_data_val=user_data(),
    room_data_val=room_data(),
    message_content=st.text(
        min_size=1, 
        max_size=500, 
        alphabet=st.characters(
            blacklist_categories=('Cs',),
            blacklist_characters=['\x00']
        )
    )
)
def test_message_data_persistence(user_data_val, room_data_val, message_content):
    """
    Property 38: Message Data Persistence
    
    For any message stored in the database, the record must contain non-null values 
    for room_id, user_id, content, and created_at fields.
    """
    db_session = get_test_session()
    try:
        # Create user and room first
        user = User(**user_data_val)
        db_session.add(user)
        db_session.commit()
        
        room = Room(owner_id=user.id, **room_data_val)
        db_session.add(room)
        db_session.commit()
        
        # Create message
        message = Message(
            room_id=room.id,
            user_id=user.id,
            content=message_content
        )
        db_session.add(message)
        db_session.commit()
        
        # Retrieve message from database
        retrieved_message = db_session.query(Message).filter(Message.id == message.id).first()
        
        # Assert all required fields are non-null
        assert retrieved_message is not None
        assert retrieved_message.room_id is not None
        assert retrieved_message.user_id is not None
        assert retrieved_message.content is not None
        assert retrieved_message.created_at is not None
        
        # Assert values match
        assert retrieved_message.room_id == room.id
        assert retrieved_message.user_id == user.id
        assert retrieved_message.content == message_content
    finally:
        db_session.rollback()
        db_session.close()


# Property 39: Membership Data Persistence
# **Validates: Requirements 12.4**
@settings(max_examples=100)
@given(user_data_val=user_data(), room_data_val=room_data())
def test_membership_data_persistence(user_data_val, room_data_val):
    """
    Property 39: Membership Data Persistence
    
    For any room membership stored in the database, the record must contain non-null 
    values for user_id, room_id, and joined_at fields.
    """
    db_session = get_test_session()
    try:
        # Create user and room first
        user = User(**user_data_val)
        db_session.add(user)
        db_session.commit()
        
        room = Room(owner_id=user.id, **room_data_val)
        db_session.add(room)
        db_session.commit()
        
        # Create membership
        membership = RoomMembership(
            user_id=user.id,
            room_id=room.id
        )
        db_session.add(membership)
        db_session.commit()
        
        # Retrieve membership from database
        retrieved_membership = db_session.query(RoomMembership).filter(
            RoomMembership.id == membership.id
        ).first()
        
        # Assert all required fields are non-null
        assert retrieved_membership is not None
        assert retrieved_membership.user_id is not None
        assert retrieved_membership.room_id is not None
        assert retrieved_membership.joined_at is not None
        
        # Assert values match
        assert retrieved_membership.user_id == user.id
        assert retrieved_membership.room_id == room.id
    finally:
        db_session.rollback()
        db_session.close()


# Property 40: Referential Integrity
# **Validates: Requirements 12.5**
@settings(max_examples=100)
@given(
    user_data_val=user_data(),
    room_data_val=room_data(),
    message_content=st.text(
        min_size=1, 
        max_size=500, 
        alphabet=st.characters(
            blacklist_categories=('Cs',),
            blacklist_characters=['\x00']
        )
    )
)
def test_referential_integrity(user_data_val, room_data_val, message_content):
    """
    Property 40: Referential Integrity
    
    For any message, room membership, or room record, if the referenced user_id or 
    room_id does not exist in the respective table, the database must reject the 
    insert/update with a foreign key constraint violation.
    """
    db_session = get_test_session()
    try:
        # Test 1: Try to create a message with non-existent room_id
        with pytest.raises(IntegrityError):
            invalid_message = Message(
                room_id=99999,  # Non-existent room
                user_id=1,
                content=message_content
            )
            db_session.add(invalid_message)
            db_session.commit()
        
        db_session.rollback()
        
        # Test 2: Try to create a room membership with non-existent user_id
        # First create a valid room
        user = User(**user_data_val)
        db_session.add(user)
        db_session.commit()
        
        room = Room(owner_id=user.id, **room_data_val)
        db_session.add(room)
        db_session.commit()
        
        with pytest.raises(IntegrityError):
            invalid_membership = RoomMembership(
                user_id=99999,  # Non-existent user
                room_id=room.id
            )
            db_session.add(invalid_membership)
            db_session.commit()
        
        db_session.rollback()
        
        # Test 3: Try to create a room membership with non-existent room_id
        with pytest.raises(IntegrityError):
            invalid_membership = RoomMembership(
                user_id=user.id,
                room_id=99999  # Non-existent room
            )
            db_session.add(invalid_membership)
            db_session.commit()
        
        db_session.rollback()
    finally:
        db_session.rollback()
        db_session.close()
