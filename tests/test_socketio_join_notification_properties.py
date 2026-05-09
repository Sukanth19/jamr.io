"""Property-based tests for Socket.IO join notifications.

Feature: jamr-io-mvp
Tests join notification broadcast and user count update properties.
"""

import pytest
import asyncio
import uuid
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings
from unittest.mock import AsyncMock, MagicMock, patch
from backend.models import User, Room, RoomMembership, Session as SessionModel
from backend.socketio_server import join_room, active_connections, sio
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
def create_test_room(db_session, owner_id, name=None, initial_user_count=0):
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
        user_count=initial_user_count
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return room


# Property 15: Join Notification Broadcast
# **Validates: Requirements 6.3**
@settings(max_examples=100)
@given(
    username=st.text(min_size=3, max_size=50, alphabet=st.characters(min_codepoint=33, max_codepoint=126))
)
@pytest.mark.asyncio
async def test_property_15_join_notification_broadcast_single_user(username):
    """
    Property 15: Join Notification Broadcast (Part 1 - Single User Join)
    
    For any user joining a room, all currently connected users in that room must receive
    a `user_joined` Socket.IO event containing the joining user's ID and username.
    
    Feature: jamr-io-mvp, Property 15: Join Notification Broadcast
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room
        room = create_test_room(db_session, owner_id=owner.id)
        room_id = room.id
        
        # Create a user who will join the room
        joining_user = create_test_user(db_session, display_name=username.strip())
        user_id = joining_user.id
        username_clean = joining_user.display_name
        
        # Set up Socket.IO connection for the joining user
        sid = f"test_sid_{uuid.uuid4()}"
        active_connections[sid] = user_id
        
        # Mock sio.emit and sio.enter_room
        with patch('backend.socketio_server.sio') as mock_sio, \
             patch('backend.database.get_session_local') as mock_get_session:
            
            mock_sio.emit = AsyncMock()
            mock_sio.enter_room = AsyncMock()
            mock_get_session.return_value = lambda: db_session
            
            # Call join_room handler
            result = await join_room(sid, {'room_id': room_id})
            
            # Verify join was successful
            assert result.get('success') is True
            
            # Verify user_joined event was broadcast
            user_joined_calls = [
                call for call in mock_sio.emit.call_args_list
                if call[0][0] == 'user_joined'
            ]
            
            assert len(user_joined_calls) >= 1, "user_joined event must be broadcast"
            
            # Verify the event payload contains correct data
            user_joined_call = user_joined_calls[0]
            event_name = user_joined_call[0][0]
            event_payload = user_joined_call[0][1]
            event_room = user_joined_call[1].get('room')
            
            assert event_name == 'user_joined'
            assert event_payload['user_id'] == user_id
            assert event_payload['username'] == username_clean
            assert event_payload['room_id'] == room_id
            assert event_room == f'room_{room_id}'
            
    finally:
        # Clean up active connections
        if sid in active_connections:
            del active_connections[sid]
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    num_existing_users=st.integers(min_value=1, max_value=5)
)
@pytest.mark.asyncio
async def test_property_15_join_notification_broadcast_multiple_users(num_existing_users):
    """
    Property 15: Join Notification Broadcast (Part 2 - Multiple Existing Users)
    
    For any user joining a room with multiple existing users, all currently connected
    users in that room must receive a `user_joined` Socket.IO event.
    
    Feature: jamr-io-mvp, Property 15: Join Notification Broadcast
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room
        room = create_test_room(db_session, owner_id=owner.id, initial_user_count=num_existing_users)
        room_id = room.id
        
        # Create existing users in the room
        existing_users = []
        for i in range(num_existing_users):
            user = create_test_user(db_session, spotify_id=f"existing_user_{uuid.uuid4()}")
            membership = RoomMembership(user_id=user.id, room_id=room_id)
            db_session.add(membership)
            existing_users.append(user)
        
        db_session.commit()
        
        # Create a new user who will join the room
        joining_user = create_test_user(db_session, spotify_id=f"joining_user_{uuid.uuid4()}")
        user_id = joining_user.id
        username = joining_user.display_name
        
        # Set up Socket.IO connection for the joining user
        sid = f"test_sid_{uuid.uuid4()}"
        active_connections[sid] = user_id
        
        # Mock sio.emit and sio.enter_room
        with patch('backend.socketio_server.sio') as mock_sio, \
             patch('backend.database.get_session_local') as mock_get_session:
            
            mock_sio.emit = AsyncMock()
            mock_sio.enter_room = AsyncMock()
            mock_get_session.return_value = lambda: db_session
            
            # Call join_room handler
            result = await join_room(sid, {'room_id': room_id})
            
            # Verify join was successful
            assert result.get('success') is True
            
            # Verify user_joined event was broadcast to the room
            user_joined_calls = [
                call for call in mock_sio.emit.call_args_list
                if call[0][0] == 'user_joined'
            ]
            
            assert len(user_joined_calls) >= 1, "user_joined event must be broadcast"
            
            # Verify the event was sent to the correct room (all existing users receive it)
            user_joined_call = user_joined_calls[0]
            event_payload = user_joined_call[0][1]
            event_room = user_joined_call[1].get('room')
            
            assert event_payload['user_id'] == user_id
            assert event_payload['username'] == username
            assert event_payload['room_id'] == room_id
            assert event_room == f'room_{room_id}'
            
    finally:
        # Clean up active connections
        if sid in active_connections:
            del active_connections[sid]
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    num_sequential_joins=st.integers(min_value=2, max_value=5)
)
@pytest.mark.asyncio
async def test_property_15_join_notification_broadcast_sequential_joins(num_sequential_joins):
    """
    Property 15: Join Notification Broadcast (Part 3 - Sequential Joins)
    
    For any sequence of users joining a room, each join must trigger a separate
    `user_joined` Socket.IO event broadcast to all users in the room.
    
    Feature: jamr-io-mvp, Property 15: Join Notification Broadcast
    """
    db_session = get_test_session()
    sids = []
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room
        room = create_test_room(db_session, owner_id=owner.id)
        room_id = room.id
        
        # Track all user_joined events
        all_user_joined_events = []
        
        # Have multiple users join sequentially
        for i in range(num_sequential_joins):
            # Create a new user
            user = create_test_user(db_session, spotify_id=f"user_{uuid.uuid4()}")
            user_id = user.id
            username = user.display_name
            
            # Set up Socket.IO connection
            sid = f"test_sid_{uuid.uuid4()}"
            sids.append(sid)
            active_connections[sid] = user_id
            
            # Mock sio.emit and sio.enter_room
            with patch('backend.socketio_server.sio') as mock_sio, \
                 patch('backend.database.get_session_local') as mock_get_session:
                
                mock_sio.emit = AsyncMock()
                mock_sio.enter_room = AsyncMock()
                mock_get_session.return_value = lambda: db_session
                
                # Call join_room handler
                result = await join_room(sid, {'room_id': room_id})
                
                # Verify join was successful
                assert result.get('success') is True
                
                # Collect user_joined events
                user_joined_calls = [
                    call for call in mock_sio.emit.call_args_list
                    if call[0][0] == 'user_joined'
                ]
                
                # Each join should trigger exactly one user_joined event
                assert len(user_joined_calls) >= 1, f"Join {i+1} must broadcast user_joined event"
                
                # Verify the event contains correct data
                event_payload = user_joined_calls[0][0][1]
                assert event_payload['user_id'] == user_id
                assert event_payload['username'] == username
                assert event_payload['room_id'] == room_id
                
                all_user_joined_events.append(event_payload)
        
        # Verify we got one event per join
        assert len(all_user_joined_events) == num_sequential_joins
        
        # Verify each event has unique user_id
        user_ids = [event['user_id'] for event in all_user_joined_events]
        assert len(set(user_ids)) == num_sequential_joins, "Each join should have unique user_id"
        
    finally:
        # Clean up active connections
        for sid in sids:
            if sid in active_connections:
                del active_connections[sid]
        db_session.rollback()
        db_session.close()


# Property 30: User Count Broadcast
# **Validates: Requirements 9.1**
@settings(max_examples=100)
@given(
    initial_count=st.integers(min_value=0, max_value=50)
)
@pytest.mark.asyncio
async def test_property_30_user_count_broadcast_on_join(initial_count):
    """
    Property 30: User Count Broadcast (Part 1 - Join Updates Count)
    
    For any user joining a room, all currently connected users in that room must receive
    a `user_count_updated` Socket.IO event containing the updated count.
    
    Feature: jamr-io-mvp, Property 30: User Count Broadcast
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room with initial user count
        room = create_test_room(db_session, owner_id=owner.id, initial_user_count=initial_count)
        room_id = room.id
        
        # Create a user who will join the room
        joining_user = create_test_user(db_session, spotify_id=f"joining_user_{uuid.uuid4()}")
        user_id = joining_user.id
        
        # Set up Socket.IO connection
        sid = f"test_sid_{uuid.uuid4()}"
        active_connections[sid] = user_id
        
        # Mock sio.emit and sio.enter_room
        with patch('backend.socketio_server.sio') as mock_sio, \
             patch('backend.database.get_session_local') as mock_get_session:
            
            mock_sio.emit = AsyncMock()
            mock_sio.enter_room = AsyncMock()
            mock_get_session.return_value = lambda: db_session
            
            # Call join_room handler
            result = await join_room(sid, {'room_id': room_id})
            
            # Verify join was successful
            assert result.get('success') is True
            
            # Verify user_count_updated event was broadcast
            user_count_calls = [
                call for call in mock_sio.emit.call_args_list
                if call[0][0] == 'user_count_updated'
            ]
            
            assert len(user_count_calls) >= 1, "user_count_updated event must be broadcast"
            
            # Verify the event payload contains correct data
            user_count_call = user_count_calls[0]
            event_name = user_count_call[0][0]
            event_payload = user_count_call[0][1]
            event_room = user_count_call[1].get('room')
            
            assert event_name == 'user_count_updated'
            assert event_payload['room_id'] == room_id
            assert event_payload['count'] == initial_count + 1, "Count should be incremented by 1"
            assert event_room == f'room_{room_id}'
            
            # Verify the room's user_count was actually incremented in the database
            # Query the room again to get the updated state
            updated_room = db_session.query(Room).filter(Room.id == room_id).first()
            assert updated_room is not None
            assert updated_room.user_count == initial_count + 1
            
    finally:
        # Clean up active connections
        if sid in active_connections:
            del active_connections[sid]
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    initial_count=st.integers(min_value=0, max_value=20),
    num_joins=st.integers(min_value=1, max_value=5)
)
@pytest.mark.asyncio
async def test_property_30_user_count_broadcast_multiple_joins(initial_count, num_joins):
    """
    Property 30: User Count Broadcast (Part 2 - Multiple Joins)
    
    For any sequence of users joining a room, each join must trigger a `user_count_updated`
    event with the correctly incremented count.
    
    Feature: jamr-io-mvp, Property 30: User Count Broadcast
    """
    db_session = get_test_session()
    sids = []
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room with initial user count
        room = create_test_room(db_session, owner_id=owner.id, initial_user_count=initial_count)
        room_id = room.id
        
        # Track expected count
        expected_count = initial_count
        
        # Have multiple users join sequentially
        for i in range(num_joins):
            # Create a new user
            user = create_test_user(db_session, spotify_id=f"user_{uuid.uuid4()}")
            user_id = user.id
            
            # Set up Socket.IO connection
            sid = f"test_sid_{uuid.uuid4()}"
            sids.append(sid)
            active_connections[sid] = user_id
            
            # Increment expected count
            expected_count += 1
            
            # Mock sio.emit and sio.enter_room
            with patch('backend.socketio_server.sio') as mock_sio, \
                 patch('backend.database.get_session_local') as mock_get_session:
                
                mock_sio.emit = AsyncMock()
                mock_sio.enter_room = AsyncMock()
                mock_get_session.return_value = lambda: db_session
                
                # Call join_room handler
                result = await join_room(sid, {'room_id': room_id})
                
                # Verify join was successful
                assert result.get('success') is True
                
                # Verify user_count_updated event was broadcast
                user_count_calls = [
                    call for call in mock_sio.emit.call_args_list
                    if call[0][0] == 'user_count_updated'
                ]
                
                assert len(user_count_calls) >= 1, f"Join {i+1} must broadcast user_count_updated event"
                
                # Verify the event contains correct count
                event_payload = user_count_calls[0][0][1]
                assert event_payload['room_id'] == room_id
                assert event_payload['count'] == expected_count, f"Count should be {expected_count} after join {i+1}"
        
        # Verify final count in database
        # Query the room again to get the updated state
        updated_room = db_session.query(Room).filter(Room.id == room_id).first()
        assert updated_room is not None
        assert updated_room.user_count == initial_count + num_joins
        
    finally:
        # Clean up active connections
        for sid in sids:
            if sid in active_connections:
                del active_connections[sid]
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    username=st.text(min_size=3, max_size=50, alphabet=st.characters(min_codepoint=33, max_codepoint=126)),
    initial_count=st.integers(min_value=0, max_value=50)
)
@pytest.mark.asyncio
async def test_property_30_user_count_broadcast_consistency(username, initial_count):
    """
    Property 30: User Count Broadcast (Part 3 - Consistency Check)
    
    For any user joining a room, the `user_count_updated` event must be broadcast
    to the same room as the `user_joined` event, ensuring all users receive both updates.
    
    Feature: jamr-io-mvp, Property 30: User Count Broadcast
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room
        room = create_test_room(db_session, owner_id=owner.id, initial_user_count=initial_count)
        room_id = room.id
        
        # Create a user who will join the room
        joining_user = create_test_user(db_session, display_name=username.strip())
        user_id = joining_user.id
        
        # Set up Socket.IO connection
        sid = f"test_sid_{uuid.uuid4()}"
        active_connections[sid] = user_id
        
        # Mock sio.emit and sio.enter_room
        with patch('backend.socketio_server.sio') as mock_sio, \
             patch('backend.database.get_session_local') as mock_get_session:
            
            mock_sio.emit = AsyncMock()
            mock_sio.enter_room = AsyncMock()
            mock_get_session.return_value = lambda: db_session
            
            # Call join_room handler
            result = await join_room(sid, {'room_id': room_id})
            
            # Verify join was successful
            assert result.get('success') is True
            
            # Collect all emit calls
            all_emit_calls = mock_sio.emit.call_args_list
            
            # Find user_joined and user_count_updated events
            user_joined_calls = [
                call for call in all_emit_calls
                if call[0][0] == 'user_joined'
            ]
            user_count_calls = [
                call for call in all_emit_calls
                if call[0][0] == 'user_count_updated'
            ]
            
            # Both events must be broadcast
            assert len(user_joined_calls) >= 1, "user_joined event must be broadcast"
            assert len(user_count_calls) >= 1, "user_count_updated event must be broadcast"
            
            # Verify both events are sent to the same room
            user_joined_room = user_joined_calls[0][1].get('room')
            user_count_room = user_count_calls[0][1].get('room')
            
            assert user_joined_room == f'room_{room_id}'
            assert user_count_room == f'room_{room_id}'
            assert user_joined_room == user_count_room, "Both events must be sent to the same room"
            
            # Verify both events reference the same room_id in their payloads
            user_joined_payload = user_joined_calls[0][0][1]
            user_count_payload = user_count_calls[0][0][1]
            
            assert user_joined_payload['room_id'] == room_id
            assert user_count_payload['room_id'] == room_id
            
    finally:
        # Clean up active connections
        if sid in active_connections:
            del active_connections[sid]
        db_session.rollback()
        db_session.close()
