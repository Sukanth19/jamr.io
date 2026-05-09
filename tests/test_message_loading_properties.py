"""Property-based tests for message loading.

Feature: jamr-io-mvp
Tests recent messages loading property.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings
from backend.models import Room, User, Message
from backend.recommendation_engine import generate_room_taste_vector
from tests.conftest import get_test_session


# Helper function to create a test user
def create_test_user(db_session, spotify_id=None):
    """Create a test user for message loading tests."""
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


# Helper function to create a test room
def create_test_room(db_session, owner_id, name=None):
    """Create a test room for message loading tests."""
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


# Helper function to create a test message
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


# Property 23: Recent Messages Loading
# **Validates: Requirements 7.5**
@settings(max_examples=100)
@given(
    num_messages=st.integers(min_value=1, max_value=50)
)
def test_property_23_recent_messages_loading_within_limit(num_messages):
    """
    Property 23: Recent Messages Loading (Part 1 - Within Limit)
    
    For any user joining a room with messages <= 50, the platform must return
    all messages for that room, ordered by created_at descending.
    
    Feature: jamr-io-mvp, Property 23: Recent Messages Loading
    """
    db_session = get_test_session()
    try:
        # Create a test user and room
        user = create_test_user(db_session)
        room = create_test_room(db_session, owner_id=user.id)
        
        # Create messages with incrementing timestamps
        base_time = datetime.now()
        created_messages = []
        for i in range(num_messages):
            # Create messages with timestamps that increase
            timestamp = base_time + timedelta(seconds=i)
            message = create_test_message(
                db_session,
                room_id=room.id,
                user_id=user.id,
                content=f"Message {i}",
                created_at=timestamp
            )
            created_messages.append(message)
        
        # Query messages as the endpoint would
        retrieved_messages = db_session.query(Message).filter(
            Message.room_id == room.id
        ).order_by(
            Message.created_at.desc()
        ).limit(50).all()
        
        # Verify all messages were returned (since num_messages <= 50)
        assert len(retrieved_messages) == num_messages
        
        # Verify messages are ordered by created_at descending (newest first)
        for i in range(len(retrieved_messages) - 1):
            assert retrieved_messages[i].created_at >= retrieved_messages[i + 1].created_at
        
        # Verify the first message is the most recent one
        assert retrieved_messages[0].content == f"Message {num_messages - 1}"
        
        # Verify the last message is the oldest one
        assert retrieved_messages[-1].content == "Message 0"
        
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100, deadline=None)
@given(
    num_messages=st.integers(min_value=51, max_value=200)
)
def test_property_23_recent_messages_loading_exceeds_limit(num_messages):
    """
    Property 23: Recent Messages Loading (Part 2 - Exceeds Limit)
    
    For any user joining a room with messages > 50, the platform must return
    only the most recent 50 messages, ordered by created_at descending.
    
    Feature: jamr-io-mvp, Property 23: Recent Messages Loading
    """
    db_session = get_test_session()
    try:
        # Create a test user and room
        user = create_test_user(db_session)
        room = create_test_room(db_session, owner_id=user.id)
        
        # Create messages with incrementing timestamps
        base_time = datetime.now()
        created_messages = []
        for i in range(num_messages):
            timestamp = base_time + timedelta(seconds=i)
            message = create_test_message(
                db_session,
                room_id=room.id,
                user_id=user.id,
                content=f"Message {i}",
                created_at=timestamp
            )
            created_messages.append(message)
        
        # Query messages as the endpoint would (limit 50)
        retrieved_messages = db_session.query(Message).filter(
            Message.room_id == room.id
        ).order_by(
            Message.created_at.desc()
        ).limit(50).all()
        
        # Verify exactly 50 messages were returned
        assert len(retrieved_messages) == 50
        
        # Verify messages are ordered by created_at descending
        for i in range(len(retrieved_messages) - 1):
            assert retrieved_messages[i].created_at >= retrieved_messages[i + 1].created_at
        
        # Verify the first message is the most recent one
        assert retrieved_messages[0].content == f"Message {num_messages - 1}"
        
        # Verify the last message is the 50th most recent
        # (num_messages - 50) is the index of the 50th most recent message
        assert retrieved_messages[-1].content == f"Message {num_messages - 50}"
        
        # Verify older messages are not included
        # The oldest message (Message 0) should not be in the results
        message_contents = [msg.content for msg in retrieved_messages]
        assert "Message 0" not in message_contents
        
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    num_messages=st.integers(min_value=0, max_value=0)
)
def test_property_23_recent_messages_loading_empty_room(num_messages):
    """
    Property 23: Recent Messages Loading (Part 3 - Empty Room)
    
    For any user joining a room with no messages, the platform must return
    an empty list of messages.
    
    Feature: jamr-io-mvp, Property 23: Recent Messages Loading
    """
    db_session = get_test_session()
    try:
        # Create a test user and room
        user = create_test_user(db_session)
        room = create_test_room(db_session, owner_id=user.id)
        
        # Don't create any messages
        
        # Query messages as the endpoint would
        retrieved_messages = db_session.query(Message).filter(
            Message.room_id == room.id
        ).order_by(
            Message.created_at.desc()
        ).limit(50).all()
        
        # Verify no messages were returned
        assert len(retrieved_messages) == 0
        
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    num_messages_room1=st.integers(min_value=1, max_value=30),
    num_messages_room2=st.integers(min_value=1, max_value=30)
)
def test_property_23_recent_messages_loading_multiple_rooms(num_messages_room1, num_messages_room2):
    """
    Property 23: Recent Messages Loading (Part 4 - Multiple Rooms)
    
    For any user joining a room, the platform must return only messages for
    that specific room, not messages from other rooms.
    
    Feature: jamr-io-mvp, Property 23: Recent Messages Loading
    """
    db_session = get_test_session()
    try:
        # Create a test user
        user = create_test_user(db_session)
        
        # Create two rooms
        room1 = create_test_room(db_session, owner_id=user.id, name="Room 1")
        room2 = create_test_room(db_session, owner_id=user.id, name="Room 2")
        
        # Create messages for room 1
        base_time = datetime.now()
        for i in range(num_messages_room1):
            timestamp = base_time + timedelta(seconds=i)
            create_test_message(
                db_session,
                room_id=room1.id,
                user_id=user.id,
                content=f"Room1 Message {i}",
                created_at=timestamp
            )
        
        # Create messages for room 2
        for i in range(num_messages_room2):
            timestamp = base_time + timedelta(seconds=i)
            create_test_message(
                db_session,
                room_id=room2.id,
                user_id=user.id,
                content=f"Room2 Message {i}",
                created_at=timestamp
            )
        
        # Query messages for room 1
        room1_messages = db_session.query(Message).filter(
            Message.room_id == room1.id
        ).order_by(
            Message.created_at.desc()
        ).limit(50).all()
        
        # Verify only room 1 messages were returned
        assert len(room1_messages) == num_messages_room1
        for message in room1_messages:
            assert message.room_id == room1.id
            assert "Room1" in message.content
            assert "Room2" not in message.content
        
        # Query messages for room 2
        room2_messages = db_session.query(Message).filter(
            Message.room_id == room2.id
        ).order_by(
            Message.created_at.desc()
        ).limit(50).all()
        
        # Verify only room 2 messages were returned
        assert len(room2_messages) == num_messages_room2
        for message in room2_messages:
            assert message.room_id == room2.id
            assert "Room2" in message.content
            assert "Room1" not in message.content
        
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    num_messages=st.integers(min_value=10, max_value=50)
)
def test_property_23_recent_messages_loading_with_user_info(num_messages):
    """
    Property 23: Recent Messages Loading (Part 5 - With User Information)
    
    For any user joining a room, the platform must return messages with
    user information (user_id and username) for each message.
    
    Feature: jamr-io-mvp, Property 23: Recent Messages Loading
    """
    db_session = get_test_session()
    try:
        # Create multiple test users
        user1 = create_test_user(db_session, spotify_id=f"user1_{uuid.uuid4()}")
        user2 = create_test_user(db_session, spotify_id=f"user2_{uuid.uuid4()}")
        
        # Create a room
        room = create_test_room(db_session, owner_id=user1.id)
        
        # Create messages from different users
        base_time = datetime.now()
        for i in range(num_messages):
            # Alternate between users
            sender = user1 if i % 2 == 0 else user2
            timestamp = base_time + timedelta(seconds=i)
            create_test_message(
                db_session,
                room_id=room.id,
                user_id=sender.id,
                content=f"Message {i}",
                created_at=timestamp
            )
        
        # Query messages as the endpoint would
        retrieved_messages = db_session.query(Message).filter(
            Message.room_id == room.id
        ).order_by(
            Message.created_at.desc()
        ).limit(50).all()
        
        # Verify all messages have user_id
        for message in retrieved_messages:
            assert message.user_id is not None
            assert message.user_id in [user1.id, user2.id]
            
            # Verify we can retrieve user information
            user = db_session.query(User).filter(User.id == message.user_id).first()
            assert user is not None
            assert user.display_name is not None
        
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    num_messages=st.integers(min_value=5, max_value=50)
)
def test_property_23_recent_messages_loading_ordering_consistency(num_messages):
    """
    Property 23: Recent Messages Loading (Part 6 - Ordering Consistency)
    
    For any user joining a room multiple times, the platform must return
    messages in the same order (created_at descending) each time.
    
    Feature: jamr-io-mvp, Property 23: Recent Messages Loading
    """
    db_session = get_test_session()
    try:
        # Create a test user and room
        user = create_test_user(db_session)
        room = create_test_room(db_session, owner_id=user.id)
        
        # Create messages with specific timestamps
        base_time = datetime.now()
        for i in range(num_messages):
            timestamp = base_time + timedelta(seconds=i)
            create_test_message(
                db_session,
                room_id=room.id,
                user_id=user.id,
                content=f"Message {i}",
                created_at=timestamp
            )
        
        # Query messages multiple times
        first_query = db_session.query(Message).filter(
            Message.room_id == room.id
        ).order_by(
            Message.created_at.desc()
        ).limit(50).all()
        
        second_query = db_session.query(Message).filter(
            Message.room_id == room.id
        ).order_by(
            Message.created_at.desc()
        ).limit(50).all()
        
        # Verify both queries return the same number of messages
        assert len(first_query) == len(second_query)
        assert len(first_query) == num_messages
        
        # Verify both queries return messages in the same order
        for i in range(len(first_query)):
            assert first_query[i].id == second_query[i].id
            assert first_query[i].content == second_query[i].content
            assert first_query[i].created_at == second_query[i].created_at
        
    finally:
        db_session.rollback()
        db_session.close()
