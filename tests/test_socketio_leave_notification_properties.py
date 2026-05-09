"""Property-based tests for Socket.IO leave notifications.

Feature: jamr-io-mvp
Tests leave notification broadcast property.
"""

import pytest
import asyncio
import uuid
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings
from unittest.mock import AsyncMock, MagicMock, patch
from backend.models import User, Room, RoomMembership, Session as SessionModel
from backend.socketio_server import leave_room, active_connections, sio
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


# Property 18: Leave Notification Broadcast
# **Validates: Requirements 6.6**
@settings(max_examples=100)
@given(
    username=st.text(min_size=3, max_size=50, alphabet=st.characters(min_codepoint=33, max_codepoint=126))
)
@pytest.mark.asyncio
async def test_property_18_leave_notification_broadcast_single_user(username):
    """
    Property 18: Leave Notification Broadcast (Part 1 - Single User Leave)
    
    For any user leaving a room, all currently connected users in that room must receive
    a `user_left` Socket.IO event containing the leaving user's ID and username.
    
    Feature: jamr-io-mvp, Property 18: Leave Notification Broadcast
    **Validates: Requirements 6.6**
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room with initial user count
        room = create_test_room(db_session, owner_id=owner.id, initial_user_count=1)
        room_id = room.id
        
        # Create a user who is already in the room and will leave
        leaving_user = create_test_user(db_session, display_name=username.strip())
        user_id = leaving_user.id
        username_clean = leaving_user.display_name
        
        # Create room membership for the leaving user
        membership = RoomMembership(user_id=user_id, room_id=room_id)
        db_session.add(membership)
        db_session.commit()
        
        # Set up Socket.IO connection for the leaving user
        sid = f"test_sid_{uuid.uuid4()}"
        active_connections[sid] = user_id
        
        # Mock sio.emit and sio.leave_room
        with patch('backend.socketio_server.sio') as mock_sio, \
             patch('backend.database.get_session_local') as mock_get_session:
            
            mock_sio.emit = AsyncMock()
            mock_sio.leave_room = AsyncMock()
            mock_get_session.return_value = lambda: db_session
            
            # Call leave_room handler
            result = await leave_room(sid, {'room_id': room_id})
            
            # Verify leave was successful
            assert result.get('success') is True
            
            # Verify user_left event was broadcast
            user_left_calls = [
                call for call in mock_sio.emit.call_args_list
                if call[0][0] == 'user_left'
            ]
            
            assert len(user_left_calls) >= 1, "user_left event must be broadcast"
            
            # Verify the event payload contains correct data
            user_left_call = user_left_calls[0]
            event_name = user_left_call[0][0]
            event_payload = user_left_call[0][1]
            event_room = user_left_call[1].get('room')
            
            assert event_name == 'user_left'
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
    num_remaining_users=st.integers(min_value=1, max_value=5)
)
@pytest.mark.asyncio
async def test_property_18_leave_notification_broadcast_multiple_users(num_remaining_users):
    """
    Property 18: Leave Notification Broadcast (Part 2 - Multiple Remaining Users)
    
    For any user leaving a room with multiple remaining users, all currently connected
    users in that room must receive a `user_left` Socket.IO event.
    
    Feature: jamr-io-mvp, Property 18: Leave Notification Broadcast
    **Validates: Requirements 6.6**
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room with initial user count (leaving user + remaining users)
        room = create_test_room(db_session, owner_id=owner.id, initial_user_count=num_remaining_users + 1)
        room_id = room.id
        
        # Create remaining users in the room
        remaining_users = []
        for i in range(num_remaining_users):
            user = create_test_user(db_session, spotify_id=f"remaining_user_{uuid.uuid4()}")
            membership = RoomMembership(user_id=user.id, room_id=room_id)
            db_session.add(membership)
            remaining_users.append(user)
        
        # Create a user who will leave the room
        leaving_user = create_test_user(db_session, spotify_id=f"leaving_user_{uuid.uuid4()}")
        user_id = leaving_user.id
        username = leaving_user.display_name
        
        # Create room membership for the leaving user
        membership = RoomMembership(user_id=user_id, room_id=room_id)
        db_session.add(membership)
        db_session.commit()
        
        # Set up Socket.IO connection for the leaving user
        sid = f"test_sid_{uuid.uuid4()}"
        active_connections[sid] = user_id
        
        # Mock sio.emit and sio.leave_room
        with patch('backend.socketio_server.sio') as mock_sio, \
             patch('backend.database.get_session_local') as mock_get_session:
            
            mock_sio.emit = AsyncMock()
            mock_sio.leave_room = AsyncMock()
            mock_get_session.return_value = lambda: db_session
            
            # Call leave_room handler
            result = await leave_room(sid, {'room_id': room_id})
            
            # Verify leave was successful
            assert result.get('success') is True
            
            # Verify user_left event was broadcast to the room
            user_left_calls = [
                call for call in mock_sio.emit.call_args_list
                if call[0][0] == 'user_left'
            ]
            
            assert len(user_left_calls) >= 1, "user_left event must be broadcast"
            
            # Verify the event was sent to the correct room (all remaining users receive it)
            user_left_call = user_left_calls[0]
            event_payload = user_left_call[0][1]
            event_room = user_left_call[1].get('room')
            
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
    num_sequential_leaves=st.integers(min_value=2, max_value=5)
)
@pytest.mark.asyncio
async def test_property_18_leave_notification_broadcast_sequential_leaves(num_sequential_leaves):
    """
    Property 18: Leave Notification Broadcast (Part 3 - Sequential Leaves)
    
    For any sequence of users leaving a room, each leave must trigger a separate
    `user_left` Socket.IO event broadcast to all remaining users in the room.
    
    Feature: jamr-io-mvp, Property 18: Leave Notification Broadcast
    **Validates: Requirements 6.6**
    """
    db_session = get_test_session()
    sids = []
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room with initial user count
        room = create_test_room(db_session, owner_id=owner.id, initial_user_count=num_sequential_leaves)
        room_id = room.id
        
        # Create users who will be in the room
        users = []
        for i in range(num_sequential_leaves):
            user = create_test_user(db_session, spotify_id=f"user_{uuid.uuid4()}")
            membership = RoomMembership(user_id=user.id, room_id=room_id)
            db_session.add(membership)
            users.append(user)
        
        db_session.commit()
        
        # Track all user_left events
        all_user_left_events = []
        
        # Have multiple users leave sequentially
        for i, user in enumerate(users):
            user_id = user.id
            username = user.display_name
            
            # Set up Socket.IO connection
            sid = f"test_sid_{uuid.uuid4()}"
            sids.append(sid)
            active_connections[sid] = user_id
            
            # Mock sio.emit and sio.leave_room
            with patch('backend.socketio_server.sio') as mock_sio, \
                 patch('backend.database.get_session_local') as mock_get_session:
                
                mock_sio.emit = AsyncMock()
                mock_sio.leave_room = AsyncMock()
                mock_get_session.return_value = lambda: db_session
                
                # Call leave_room handler
                result = await leave_room(sid, {'room_id': room_id})
                
                # Verify leave was successful
                assert result.get('success') is True
                
                # Collect user_left events
                user_left_calls = [
                    call for call in mock_sio.emit.call_args_list
                    if call[0][0] == 'user_left'
                ]
                
                # Each leave should trigger exactly one user_left event
                assert len(user_left_calls) >= 1, f"Leave {i+1} must broadcast user_left event"
                
                # Verify the event contains correct data
                event_payload = user_left_calls[0][0][1]
                assert event_payload['user_id'] == user_id
                assert event_payload['username'] == username
                assert event_payload['room_id'] == room_id
                
                all_user_left_events.append(event_payload)
        
        # Verify we got one event per leave
        assert len(all_user_left_events) == num_sequential_leaves
        
        # Verify each event has unique user_id
        user_ids = [event['user_id'] for event in all_user_left_events]
        assert len(set(user_ids)) == num_sequential_leaves, "Each leave should have unique user_id"
        
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
    initial_count=st.integers(min_value=1, max_value=50)
)
@pytest.mark.asyncio
async def test_property_18_leave_notification_broadcast_consistency(username, initial_count):
    """
    Property 18: Leave Notification Broadcast (Part 4 - Consistency Check)
    
    For any user leaving a room, the `user_left` event must be broadcast
    to the same room as the `user_count_updated` event, ensuring all users receive both updates.
    
    Feature: jamr-io-mvp, Property 18: Leave Notification Broadcast
    **Validates: Requirements 6.6**
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room
        room = create_test_room(db_session, owner_id=owner.id, initial_user_count=initial_count)
        room_id = room.id
        
        # Create a user who will leave the room
        leaving_user = create_test_user(db_session, display_name=username.strip())
        user_id = leaving_user.id
        
        # Create room membership for the leaving user
        membership = RoomMembership(user_id=user_id, room_id=room_id)
        db_session.add(membership)
        db_session.commit()
        
        # Set up Socket.IO connection
        sid = f"test_sid_{uuid.uuid4()}"
        active_connections[sid] = user_id
        
        # Mock sio.emit and sio.leave_room
        with patch('backend.socketio_server.sio') as mock_sio, \
             patch('backend.database.get_session_local') as mock_get_session:
            
            mock_sio.emit = AsyncMock()
            mock_sio.leave_room = AsyncMock()
            mock_get_session.return_value = lambda: db_session
            
            # Call leave_room handler
            result = await leave_room(sid, {'room_id': room_id})
            
            # Verify leave was successful
            assert result.get('success') is True
            
            # Collect all emit calls
            all_emit_calls = mock_sio.emit.call_args_list
            
            # Find user_left and user_count_updated events
            user_left_calls = [
                call for call in all_emit_calls
                if call[0][0] == 'user_left'
            ]
            user_count_calls = [
                call for call in all_emit_calls
                if call[0][0] == 'user_count_updated'
            ]
            
            # Both events must be broadcast
            assert len(user_left_calls) >= 1, "user_left event must be broadcast"
            assert len(user_count_calls) >= 1, "user_count_updated event must be broadcast"
            
            # Verify both events are sent to the same room
            user_left_room = user_left_calls[0][1].get('room')
            user_count_room = user_count_calls[0][1].get('room')
            
            assert user_left_room == f'room_{room_id}'
            assert user_count_room == f'room_{room_id}'
            assert user_left_room == user_count_room, "Both events must be sent to the same room"
            
            # Verify both events reference the same room_id in their payloads
            user_left_payload = user_left_calls[0][0][1]
            user_count_payload = user_count_calls[0][0][1]
            
            assert user_left_payload['room_id'] == room_id
            assert user_count_payload['room_id'] == room_id
            
    finally:
        # Clean up active connections
        if sid in active_connections:
            del active_connections[sid]
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    initial_count=st.integers(min_value=1, max_value=50)
)
@pytest.mark.asyncio
async def test_property_18_leave_notification_user_count_decrement(initial_count):
    """
    Property 18: Leave Notification Broadcast (Part 5 - User Count Decrement)
    
    For any user leaving a room, the room's user_count must decrease by exactly 1,
    and the `user_count_updated` event must reflect this change.
    
    Feature: jamr-io-mvp, Property 18: Leave Notification Broadcast
    **Validates: Requirements 6.6, 6.7**
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room with initial user count
        room = create_test_room(db_session, owner_id=owner.id, initial_user_count=initial_count)
        room_id = room.id
        
        # Create a user who will leave the room
        leaving_user = create_test_user(db_session, spotify_id=f"leaving_user_{uuid.uuid4()}")
        user_id = leaving_user.id
        
        # Create room membership for the leaving user
        membership = RoomMembership(user_id=user_id, room_id=room_id)
        db_session.add(membership)
        db_session.commit()
        
        # Set up Socket.IO connection
        sid = f"test_sid_{uuid.uuid4()}"
        active_connections[sid] = user_id
        
        # Mock sio.emit and sio.leave_room
        with patch('backend.socketio_server.sio') as mock_sio, \
             patch('backend.database.get_session_local') as mock_get_session:
            
            mock_sio.emit = AsyncMock()
            mock_sio.leave_room = AsyncMock()
            mock_get_session.return_value = lambda: db_session
            
            # Call leave_room handler
            result = await leave_room(sid, {'room_id': room_id})
            
            # Verify leave was successful
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
            assert event_payload['count'] == initial_count - 1, "Count should be decremented by 1"
            assert event_room == f'room_{room_id}'
            
            # Verify the room's user_count was actually decremented in the database
            updated_room = db_session.query(Room).filter(Room.id == room_id).first()
            assert updated_room is not None
            assert updated_room.user_count == initial_count - 1
            
    finally:
        # Clean up active connections
        if sid in active_connections:
            del active_connections[sid]
        db_session.rollback()
        db_session.close()
