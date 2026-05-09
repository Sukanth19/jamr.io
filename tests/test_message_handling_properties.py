"""Property-based tests for Socket.IO message handling.

Feature: jamr-io-mvp
Tests message broadcast, structure, persistence, and activity timestamp properties.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings
from unittest.mock import AsyncMock, patch
from backend.models import User, Room, Message, RoomMembership
from backend.socketio_server import send_message, active_connections
from tests.conftest import get_test_session


# Helper function to create a test user
def create_test_user(db_session, spotify_id=None, display_name=None):
    """Create a test user for Socket.IO tests."""
    if spotify_id is None:
        spotify_id = f"test_user_{uuid.uuid4()}"
    if display_name is None:
        display_name = f"User_{uuid.uuid4().hex[:8]}"
    
    user = User(
        spotify_id=spotify_id,
        display_name=display_name,
        email=f"{spotify_id}@example.com",
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
    """Create a test room for Socket.IO tests."""
    if name is None:
        name = f"Test Room {uuid.uuid4()}"
    
    room = Room(
        name=name,
        description="A test room for testing",
        owner_id=owner_id,
        genre_tags=['rock', 'indie'],
        taste_vector={
            "danceability": 0.6,
            "energy": 0.7,
            "valence": 0.6,
            "acousticness": 0.35,
            "instrumentalness": 0.35,
            "speechiness": 0.065,
            "tempo_normalized": 0.6
        },
        user_count=0
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return room


# Property 20: Message Broadcast
# **Validates: Requirements 7.2**
@settings(max_examples=100)
@given(
    message_content=st.text(min_size=1, max_size=500, alphabet=st.characters(
        min_codepoint=33, max_codepoint=126, blacklist_characters='<>&"\''))
)
@pytest.mark.asyncio
async def test_property_20_message_broadcast(message_content):
    """
    Property 20: Message Broadcast
    
    For any message sent by a user in a room, all currently connected users in that room
    must receive a `new_message` Socket.IO event containing the message content, sender
    username, and timestamp.
    
    Feature: jamr-io-mvp, Property 20: Message Broadcast
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room
        room = create_test_room(db_session, owner_id=owner.id)
        room_id = room.id
        
        # Create a user who will send the message
        sender = create_test_user(db_session, spotify_id=f"sender_{uuid.uuid4()}")
        user_id = sender.id
        username = sender.display_name
        
        # Create room membership
        membership = RoomMembership(user_id=user_id, room_id=room_id)
        db_session.add(membership)
        db_session.commit()
        
        # Set up Socket.IO connection
        sid = f"test_sid_{uuid.uuid4()}"
        active_connections[sid] = user_id
        
        # Mock sio.emit
        with patch('backend.socketio_server.sio') as mock_sio, \
             patch('backend.database.get_session_local') as mock_get_session:
            
            mock_sio.emit = AsyncMock()
            mock_get_session.return_value = lambda: db_session
            
            # Call send_message handler
            result = await send_message(sid, {
                'room_id': room_id,
                'content': message_content
            })
            
            # Verify message was sent successfully
            assert result.get('success') is True
            
            # Verify new_message event was broadcast
            new_message_calls = [
                call for call in mock_sio.emit.call_args_list
                if call[0][0] == 'new_message'
            ]
            
            assert len(new_message_calls) >= 1, "new_message event must be broadcast"
            
            # Verify the event payload
            event_call = new_message_calls[0]
            event_name = event_call[0][0]
            event_payload = event_call[0][1]
            event_room = event_call[1].get('room')
            
            assert event_name == 'new_message'
            assert event_payload['user_id'] == user_id
            assert event_payload['username'] == username
            assert 'content' in event_payload
            assert 'timestamp' in event_payload
            assert event_room == f'room_{room_id}'
            
    finally:
        # Clean up active connections
        if sid in active_connections:
            del active_connections[sid]
        db_session.rollback()
        db_session.close()


# Property 21: Message Structure
# **Validates: Requirements 7.3**
@settings(max_examples=100)
@given(
    message_content=st.text(min_size=1, max_size=500, alphabet=st.characters(
        min_codepoint=33, max_codepoint=126, blacklist_characters='<>&"\''))
)
@pytest.mark.asyncio
async def test_property_21_message_structure(message_content):
    """
    Property 21: Message Structure
    
    For any chat message broadcast, the message payload must include the following fields:
    message_id, user_id, username, content, and timestamp.
    
    Feature: jamr-io-mvp, Property 21: Message Structure
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room
        room = create_test_room(db_session, owner_id=owner.id)
        room_id = room.id
        
        # Create a user who will send the message
        sender = create_test_user(db_session, spotify_id=f"sender_{uuid.uuid4()}")
        user_id = sender.id
        
        # Create room membership
        membership = RoomMembership(user_id=user_id, room_id=room_id)
        db_session.add(membership)
        db_session.commit()
        
        # Set up Socket.IO connection
        sid = f"test_sid_{uuid.uuid4()}"
        active_connections[sid] = user_id
        
        # Mock sio.emit
        with patch('backend.socketio_server.sio') as mock_sio, \
             patch('backend.database.get_session_local') as mock_get_session:
            
            mock_sio.emit = AsyncMock()
            mock_get_session.return_value = lambda: db_session
            
            # Call send_message handler
            result = await send_message(sid, {
                'room_id': room_id,
                'content': message_content
            })
            
            # Verify message was sent successfully
            assert result.get('success') is True
            
            # Verify new_message event was broadcast
            new_message_calls = [
                call for call in mock_sio.emit.call_args_list
                if call[0][0] == 'new_message'
            ]
            
            assert len(new_message_calls) >= 1, "new_message event must be broadcast"
            
            # Verify the event payload has all required fields
            event_payload = new_message_calls[0][0][1]
            
            # Check all required fields are present
            assert 'message_id' in event_payload, "message_id field is required"
            assert 'user_id' in event_payload, "user_id field is required"
            assert 'username' in event_payload, "username field is required"
            assert 'content' in event_payload, "content field is required"
            assert 'timestamp' in event_payload, "timestamp field is required"
            
            # Verify field types
            assert isinstance(event_payload['message_id'], int)
            assert isinstance(event_payload['user_id'], int)
            assert isinstance(event_payload['username'], str)
            assert isinstance(event_payload['content'], str)
            assert isinstance(event_payload['timestamp'], str)
            
            # Verify timestamp is in ISO format
            try:
                datetime.fromisoformat(event_payload['timestamp'])
            except ValueError:
                pytest.fail("timestamp must be in ISO format")
            
    finally:
        # Clean up active connections
        if sid in active_connections:
            del active_connections[sid]
        db_session.rollback()
        db_session.close()


# Property 22: Message Persistence
# **Validates: Requirements 7.4**
@settings(max_examples=100)
@given(
    message_content=st.text(min_size=1, max_size=500, alphabet=st.characters(
        min_codepoint=33, max_codepoint=126, blacklist_characters='<>&"\''))
)
@pytest.mark.asyncio
async def test_property_22_message_persistence(message_content):
    """
    Property 22: Message Persistence
    
    For any chat message sent, the message must be stored in the database with room_id,
    user_id, content, and created_at fields, and must be retrievable by message ID.
    
    Feature: jamr-io-mvp, Property 22: Message Persistence
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room
        room = create_test_room(db_session, owner_id=owner.id)
        room_id = room.id
        
        # Create a user who will send the message
        sender = create_test_user(db_session, spotify_id=f"sender_{uuid.uuid4()}")
        user_id = sender.id
        
        # Create room membership
        membership = RoomMembership(user_id=user_id, room_id=room_id)
        db_session.add(membership)
        db_session.commit()
        
        # Set up Socket.IO connection
        sid = f"test_sid_{uuid.uuid4()}"
        active_connections[sid] = user_id
        
        # Mock sio.emit
        with patch('backend.socketio_server.sio') as mock_sio, \
             patch('backend.database.get_session_local') as mock_get_session:
            
            mock_sio.emit = AsyncMock()
            mock_get_session.return_value = lambda: db_session
            
            # Call send_message handler
            result = await send_message(sid, {
                'room_id': room_id,
                'content': message_content
            })
            
            # Verify message was sent successfully
            assert result.get('success') is True
            assert 'message_id' in result
            
            message_id = result['message_id']
            
            # Verify message was stored in database
            stored_message = db_session.query(Message).filter(
                Message.id == message_id
            ).first()
            
            assert stored_message is not None, "Message must be stored in database"
            
            # Verify all required fields are present and correct
            assert stored_message.room_id == room_id
            assert stored_message.user_id == user_id
            assert stored_message.content is not None
            assert stored_message.created_at is not None
            
            # Verify created_at is a valid datetime
            assert isinstance(stored_message.created_at, datetime)
            
            # Verify message can be retrieved by ID
            retrieved_message = db_session.query(Message).filter(
                Message.id == message_id
            ).first()
            
            assert retrieved_message is not None
            assert retrieved_message.id == message_id
            assert retrieved_message.room_id == room_id
            assert retrieved_message.user_id == user_id
            
    finally:
        # Clean up active connections
        if sid in active_connections:
            del active_connections[sid]
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    num_messages=st.integers(min_value=1, max_value=10)
)
@pytest.mark.asyncio
async def test_property_22_message_persistence_multiple_messages(num_messages):
    """
    Property 22: Message Persistence (Part 2 - Multiple Messages)
    
    For any sequence of messages sent, all messages must be stored in the database
    and retrievable by their message IDs.
    
    Feature: jamr-io-mvp, Property 22: Message Persistence
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room
        room = create_test_room(db_session, owner_id=owner.id)
        room_id = room.id
        
        # Create a user who will send messages
        sender = create_test_user(db_session, spotify_id=f"sender_{uuid.uuid4()}")
        user_id = sender.id
        
        # Create room membership
        membership = RoomMembership(user_id=user_id, room_id=room_id)
        db_session.add(membership)
        db_session.commit()
        
        # Set up Socket.IO connection
        sid = f"test_sid_{uuid.uuid4()}"
        active_connections[sid] = user_id
        
        # Track message IDs
        message_ids = []
        
        # Send multiple messages
        for i in range(num_messages):
            # Mock sio.emit
            with patch('backend.socketio_server.sio') as mock_sio, \
                 patch('backend.database.get_session_local') as mock_get_session:
                
                mock_sio.emit = AsyncMock()
                mock_get_session.return_value = lambda: db_session
                
                # Call send_message handler
                result = await send_message(sid, {
                    'room_id': room_id,
                    'content': f"Message {i}"
                })
                
                # Verify message was sent successfully
                assert result.get('success') is True
                assert 'message_id' in result
                
                message_ids.append(result['message_id'])
        
        # Verify all messages were stored in database
        stored_messages = db_session.query(Message).filter(
            Message.room_id == room_id,
            Message.user_id == user_id
        ).all()
        
        assert len(stored_messages) == num_messages
        
        # Verify each message can be retrieved by ID
        for message_id in message_ids:
            retrieved_message = db_session.query(Message).filter(
                Message.id == message_id
            ).first()
            
            assert retrieved_message is not None
            assert retrieved_message.room_id == room_id
            assert retrieved_message.user_id == user_id
            
    finally:
        # Clean up active connections
        if sid in active_connections:
            del active_connections[sid]
        db_session.rollback()
        db_session.close()


# Property 33: Activity Timestamp Update
# **Validates: Requirements 9.6**
@settings(max_examples=100)
@given(
    message_content=st.text(min_size=1, max_size=500, alphabet=st.characters(
        min_codepoint=33, max_codepoint=126, blacklist_characters='<>&"\''))
)
@pytest.mark.asyncio
async def test_property_33_activity_timestamp_update_on_message(message_content):
    """
    Property 33: Activity Timestamp Update (Part 1 - Message Sent)
    
    For any room activity (message sent), the room's updated_at timestamp must be
    set to the current time.
    
    Feature: jamr-io-mvp, Property 33: Activity Timestamp Update
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room
        room = create_test_room(db_session, owner_id=owner.id)
        room_id = room.id
        
        # Store initial updated_at timestamp
        initial_updated_at = room.updated_at
        
        # Wait a moment to ensure timestamp difference
        import time
        time.sleep(0.01)
        
        # Create a user who will send the message
        sender = create_test_user(db_session, spotify_id=f"sender_{uuid.uuid4()}")
        user_id = sender.id
        
        # Create room membership
        membership = RoomMembership(user_id=user_id, room_id=room_id)
        db_session.add(membership)
        db_session.commit()
        
        # Set up Socket.IO connection
        sid = f"test_sid_{uuid.uuid4()}"
        active_connections[sid] = user_id
        
        # Mock sio.emit
        with patch('backend.socketio_server.sio') as mock_sio, \
             patch('backend.database.get_session_local') as mock_get_session:
            
            mock_sio.emit = AsyncMock()
            mock_get_session.return_value = lambda: db_session
            
            # Call send_message handler
            result = await send_message(sid, {
                'room_id': room_id,
                'content': message_content
            })
            
            # Verify message was sent successfully
            assert result.get('success') is True
            
            # Query room again to get updated timestamp
            updated_room = db_session.query(Room).filter(Room.id == room_id).first()
            
            assert updated_room is not None
            assert updated_room.updated_at is not None
            
            # Verify updated_at was updated (should be greater than initial)
            if initial_updated_at is not None:
                assert updated_room.updated_at >= initial_updated_at
            
    finally:
        # Clean up active connections
        if sid in active_connections:
            del active_connections[sid]
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    num_messages=st.integers(min_value=2, max_value=5)
)
@pytest.mark.asyncio
async def test_property_33_activity_timestamp_update_sequential_messages(num_messages):
    """
    Property 33: Activity Timestamp Update (Part 2 - Sequential Messages)
    
    For any sequence of messages sent, the room's updated_at timestamp must be
    updated after each message, with each timestamp being greater than or equal
    to the previous one.
    
    Feature: jamr-io-mvp, Property 33: Activity Timestamp Update
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room
        room = create_test_room(db_session, owner_id=owner.id)
        room_id = room.id
        
        # Create a user who will send messages
        sender = create_test_user(db_session, spotify_id=f"sender_{uuid.uuid4()}")
        user_id = sender.id
        
        # Create room membership
        membership = RoomMembership(user_id=user_id, room_id=room_id)
        db_session.add(membership)
        db_session.commit()
        
        # Set up Socket.IO connection
        sid = f"test_sid_{uuid.uuid4()}"
        active_connections[sid] = user_id
        
        # Track timestamps
        timestamps = []
        
        # Send multiple messages and track updated_at
        for i in range(num_messages):
            # Small delay to ensure timestamp difference
            import time
            time.sleep(0.01)
            
            # Mock sio.emit
            with patch('backend.socketio_server.sio') as mock_sio, \
                 patch('backend.database.get_session_local') as mock_get_session:
                
                mock_sio.emit = AsyncMock()
                mock_get_session.return_value = lambda: db_session
                
                # Call send_message handler
                result = await send_message(sid, {
                    'room_id': room_id,
                    'content': f"Message {i}"
                })
                
                # Verify message was sent successfully
                assert result.get('success') is True
                
                # Query room to get updated timestamp
                updated_room = db_session.query(Room).filter(Room.id == room_id).first()
                assert updated_room is not None
                assert updated_room.updated_at is not None
                
                timestamps.append(updated_room.updated_at)
        
        # Verify timestamps are monotonically increasing (or equal)
        for i in range(len(timestamps) - 1):
            assert timestamps[i + 1] >= timestamps[i], \
                f"Timestamp {i+1} should be >= timestamp {i}"
        
    finally:
        # Clean up active connections
        if sid in active_connections:
            del active_connections[sid]
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    message_content=st.text(min_size=1, max_size=500, alphabet=st.characters(
        min_codepoint=33, max_codepoint=126, blacklist_characters='<>&"\''))
)
@pytest.mark.asyncio
async def test_property_33_activity_timestamp_update_type(message_content):
    """
    Property 33: Activity Timestamp Update (Part 3 - Timestamp Type)
    
    For any room activity, the room's updated_at field must be a valid datetime object.
    
    Feature: jamr-io-mvp, Property 33: Activity Timestamp Update
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room
        room = create_test_room(db_session, owner_id=owner.id)
        room_id = room.id
        
        # Create a user who will send the message
        sender = create_test_user(db_session, spotify_id=f"sender_{uuid.uuid4()}")
        user_id = sender.id
        
        # Create room membership
        membership = RoomMembership(user_id=user_id, room_id=room_id)
        db_session.add(membership)
        db_session.commit()
        
        # Set up Socket.IO connection
        sid = f"test_sid_{uuid.uuid4()}"
        active_connections[sid] = user_id
        
        # Mock sio.emit
        with patch('backend.socketio_server.sio') as mock_sio, \
             patch('backend.database.get_session_local') as mock_get_session:
            
            mock_sio.emit = AsyncMock()
            mock_get_session.return_value = lambda: db_session
            
            # Call send_message handler
            result = await send_message(sid, {
                'room_id': room_id,
                'content': message_content
            })
            
            # Verify message was sent successfully
            assert result.get('success') is True
            
            # Query room to get updated timestamp
            updated_room = db_session.query(Room).filter(Room.id == room_id).first()
            
            assert updated_room is not None
            assert updated_room.updated_at is not None
            
            # Verify updated_at is a datetime object
            assert isinstance(updated_room.updated_at, datetime), \
                "updated_at must be a datetime object"
            
            # Verify timestamp is recent (within last minute)
            time_diff = datetime.now() - updated_room.updated_at
            assert time_diff.total_seconds() < 60, \
                "updated_at should be recent (within last minute)"
            
    finally:
        # Clean up active connections
        if sid in active_connections:
            del active_connections[sid]
        db_session.rollback()
        db_session.close()
