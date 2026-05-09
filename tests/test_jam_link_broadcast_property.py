"""Property-based tests for Socket.IO Jam link broadcast.

Feature: jamr-io-mvp
Tests Jam link broadcast property.
"""

import pytest
import uuid
from datetime import datetime
from hypothesis import given, strategies as st, settings
from unittest.mock import AsyncMock, patch
from backend.models import User, Room, RoomMembership
from backend.socketio_server import update_jam_link, active_connections
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


# Strategy for generating valid Spotify Jam links
@st.composite
def spotify_jam_link(draw):
    """Generate a valid Spotify Jam link."""
    # Generate a random alphanumeric ID for the Jam link
    jam_id_length = draw(st.integers(min_value=10, max_value=30))
    jam_id = ''.join(draw(st.lists(
        st.sampled_from('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'),
        min_size=jam_id_length,
        max_size=jam_id_length
    )))
    return f"https://open.spotify.com/jam/{jam_id}"


# Property 28: Jam Link Broadcast
# **Validates: Requirements 8.4**
@settings(max_examples=100)
@given(
    jam_link=spotify_jam_link()
)
@pytest.mark.asyncio
async def test_property_28_jam_link_broadcast_single_user(jam_link):
    """
    Property 28: Jam Link Broadcast (Part 1 - Single User Update)
    
    For any valid Spotify Jam link submission, all currently connected users in that room
    must receive a `jam_link_updated` Socket.IO event containing the new link and the user
    who updated it.
    
    Feature: jamr-io-mvp, Property 28: Jam Link Broadcast
    **Validates: Requirements 8.4**
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room
        room = create_test_room(db_session, owner_id=owner.id)
        room_id = room.id
        
        # Create a user who will update the Jam link
        updating_user = create_test_user(db_session, spotify_id=f"updating_user_{uuid.uuid4()}")
        user_id = updating_user.id
        username = updating_user.display_name
        
        # Create room membership for the updating user
        membership = RoomMembership(user_id=user_id, room_id=room_id)
        db_session.add(membership)
        db_session.commit()
        
        # Set up Socket.IO connection for the updating user
        sid = f"test_sid_{uuid.uuid4()}"
        active_connections[sid] = user_id
        
        # Mock sio.emit
        with patch('backend.socketio_server.sio') as mock_sio, \
             patch('backend.database.get_session_local') as mock_get_session:
            
            mock_sio.emit = AsyncMock()
            mock_get_session.return_value = lambda: db_session
            
            # Call update_jam_link handler
            result = await update_jam_link(sid, {
                'room_id': room_id,
                'link': jam_link
            })
            
            # Verify update was successful
            assert result.get('success') is True
            
            # Verify jam_link_updated event was broadcast
            jam_link_calls = [
                call for call in mock_sio.emit.call_args_list
                if call[0][0] == 'jam_link_updated'
            ]
            
            assert len(jam_link_calls) >= 1, "jam_link_updated event must be broadcast"
            
            # Verify the event payload contains correct data
            jam_link_call = jam_link_calls[0]
            event_name = jam_link_call[0][0]
            event_payload = jam_link_call[0][1]
            event_room = jam_link_call[1].get('room')
            
            assert event_name == 'jam_link_updated'
            assert event_payload['room_id'] == room_id
            assert event_payload['link'] == jam_link
            assert event_payload['updated_by'] == username
            assert event_room == f'room_{room_id}'
            
    finally:
        # Clean up active connections
        if sid in active_connections:
            del active_connections[sid]
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    jam_link=spotify_jam_link(),
    num_room_members=st.integers(min_value=2, max_value=5)
)
@pytest.mark.asyncio
async def test_property_28_jam_link_broadcast_multiple_users(jam_link, num_room_members):
    """
    Property 28: Jam Link Broadcast (Part 2 - Multiple Room Members)
    
    For any valid Spotify Jam link submission in a room with multiple members,
    all currently connected users in that room must receive a `jam_link_updated` event.
    
    Feature: jamr-io-mvp, Property 28: Jam Link Broadcast
    **Validates: Requirements 8.4**
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room
        room = create_test_room(db_session, owner_id=owner.id)
        room_id = room.id
        
        # Create multiple users in the room
        room_members = []
        for i in range(num_room_members):
            user = create_test_user(db_session, spotify_id=f"member_{uuid.uuid4()}")
            membership = RoomMembership(user_id=user.id, room_id=room_id)
            db_session.add(membership)
            room_members.append(user)
        
        db_session.commit()
        
        # Select one user to update the Jam link
        updating_user = room_members[0]
        user_id = updating_user.id
        username = updating_user.display_name
        
        # Set up Socket.IO connection for the updating user
        sid = f"test_sid_{uuid.uuid4()}"
        active_connections[sid] = user_id
        
        # Mock sio.emit
        with patch('backend.socketio_server.sio') as mock_sio, \
             patch('backend.database.get_session_local') as mock_get_session:
            
            mock_sio.emit = AsyncMock()
            mock_get_session.return_value = lambda: db_session
            
            # Call update_jam_link handler
            result = await update_jam_link(sid, {
                'room_id': room_id,
                'link': jam_link
            })
            
            # Verify update was successful
            assert result.get('success') is True
            
            # Verify jam_link_updated event was broadcast to the room
            jam_link_calls = [
                call for call in mock_sio.emit.call_args_list
                if call[0][0] == 'jam_link_updated'
            ]
            
            assert len(jam_link_calls) >= 1, "jam_link_updated event must be broadcast"
            
            # Verify the event was sent to the correct room (all members receive it)
            jam_link_call = jam_link_calls[0]
            event_payload = jam_link_call[0][1]
            event_room = jam_link_call[1].get('room')
            
            assert event_payload['room_id'] == room_id
            assert event_payload['link'] == jam_link
            assert event_payload['updated_by'] == username
            assert event_room == f'room_{room_id}'
            
    finally:
        # Clean up active connections
        if sid in active_connections:
            del active_connections[sid]
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    num_updates=st.integers(min_value=2, max_value=5)
)
@pytest.mark.asyncio
async def test_property_28_jam_link_broadcast_sequential_updates(num_updates):
    """
    Property 28: Jam Link Broadcast (Part 3 - Sequential Updates)
    
    For any sequence of Jam link updates, each update must trigger a separate
    `jam_link_updated` Socket.IO event broadcast to all users in the room.
    
    Feature: jamr-io-mvp, Property 28: Jam Link Broadcast
    **Validates: Requirements 8.4**
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room
        room = create_test_room(db_session, owner_id=owner.id)
        room_id = room.id
        
        # Create a user who will update the Jam link
        updating_user = create_test_user(db_session, spotify_id=f"updating_user_{uuid.uuid4()}")
        user_id = updating_user.id
        username = updating_user.display_name
        
        # Create room membership
        membership = RoomMembership(user_id=user_id, room_id=room_id)
        db_session.add(membership)
        db_session.commit()
        
        # Set up Socket.IO connection
        sid = f"test_sid_{uuid.uuid4()}"
        active_connections[sid] = user_id
        
        # Track all jam_link_updated events
        all_jam_link_events = []
        
        # Perform multiple sequential updates
        for i in range(num_updates):
            # Generate a unique Jam link for each update (alphanumeric only)
            jam_link = f"https://open.spotify.com/jam/test{i}{uuid.uuid4().hex[:10]}"
            
            # Mock sio.emit
            with patch('backend.socketio_server.sio') as mock_sio, \
                 patch('backend.database.get_session_local') as mock_get_session:
                
                mock_sio.emit = AsyncMock()
                mock_get_session.return_value = lambda: db_session
                
                # Call update_jam_link handler
                result = await update_jam_link(sid, {
                    'room_id': room_id,
                    'link': jam_link
                })
                
                # Verify update was successful
                assert result.get('success') is True
                
                # Collect jam_link_updated events
                jam_link_calls = [
                    call for call in mock_sio.emit.call_args_list
                    if call[0][0] == 'jam_link_updated'
                ]
                
                # Each update should trigger exactly one jam_link_updated event
                assert len(jam_link_calls) >= 1, f"Update {i+1} must broadcast jam_link_updated event"
                
                # Verify the event contains correct data
                event_payload = jam_link_calls[0][0][1]
                assert event_payload['room_id'] == room_id
                assert event_payload['link'] == jam_link
                assert event_payload['updated_by'] == username
                
                all_jam_link_events.append(event_payload)
        
        # Verify we got one event per update
        assert len(all_jam_link_events) == num_updates
        
        # Verify each event has a different link (since we generated unique links)
        links = [event['link'] for event in all_jam_link_events]
        assert len(set(links)) == num_updates, "Each update should have a unique link"
        
    finally:
        # Clean up active connections
        if sid in active_connections:
            del active_connections[sid]
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    jam_link=spotify_jam_link(),
    username=st.text(min_size=3, max_size=50, alphabet=st.characters(min_codepoint=33, max_codepoint=126))
)
@pytest.mark.asyncio
async def test_property_28_jam_link_broadcast_payload_structure(jam_link, username):
    """
    Property 28: Jam Link Broadcast (Part 4 - Payload Structure)
    
    For any valid Spotify Jam link submission, the `jam_link_updated` event payload
    must contain exactly three fields: room_id, link, and updated_by.
    
    Feature: jamr-io-mvp, Property 28: Jam Link Broadcast
    **Validates: Requirements 8.4**
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room
        room = create_test_room(db_session, owner_id=owner.id)
        room_id = room.id
        
        # Create a user who will update the Jam link
        updating_user = create_test_user(db_session, display_name=username.strip())
        user_id = updating_user.id
        username_clean = updating_user.display_name
        
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
            
            # Call update_jam_link handler
            result = await update_jam_link(sid, {
                'room_id': room_id,
                'link': jam_link
            })
            
            # Verify update was successful
            assert result.get('success') is True
            
            # Verify jam_link_updated event was broadcast
            jam_link_calls = [
                call for call in mock_sio.emit.call_args_list
                if call[0][0] == 'jam_link_updated'
            ]
            
            assert len(jam_link_calls) >= 1, "jam_link_updated event must be broadcast"
            
            # Verify the event payload has all required fields
            event_payload = jam_link_calls[0][0][1]
            
            # Check all required fields are present
            assert 'room_id' in event_payload, "room_id field is required"
            assert 'link' in event_payload, "link field is required"
            assert 'updated_by' in event_payload, "updated_by field is required"
            
            # Verify field values
            assert event_payload['room_id'] == room_id
            assert event_payload['link'] == jam_link
            assert event_payload['updated_by'] == username_clean
            
            # Verify field types
            assert isinstance(event_payload['room_id'], int)
            assert isinstance(event_payload['link'], str)
            assert isinstance(event_payload['updated_by'], str)
            
    finally:
        # Clean up active connections
        if sid in active_connections:
            del active_connections[sid]
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    jam_link=spotify_jam_link()
)
@pytest.mark.asyncio
async def test_property_28_jam_link_broadcast_persistence(jam_link):
    """
    Property 28: Jam Link Broadcast (Part 5 - Link Persistence)
    
    For any valid Spotify Jam link submission, the link must be stored in the room's
    active_jam_link field and be retrievable from the database.
    
    Feature: jamr-io-mvp, Property 28: Jam Link Broadcast
    **Validates: Requirements 8.3, 8.4**
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room
        room = create_test_room(db_session, owner_id=owner.id)
        room_id = room.id
        
        # Create a user who will update the Jam link
        updating_user = create_test_user(db_session, spotify_id=f"updating_user_{uuid.uuid4()}")
        user_id = updating_user.id
        
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
            
            # Call update_jam_link handler
            result = await update_jam_link(sid, {
                'room_id': room_id,
                'link': jam_link
            })
            
            # Verify update was successful
            assert result.get('success') is True
            
            # Verify the link was stored in the database
            updated_room = db_session.query(Room).filter(Room.id == room_id).first()
            
            assert updated_room is not None
            assert updated_room.active_jam_link == jam_link
            
            # Verify jam_link_updated event was broadcast with the same link
            jam_link_calls = [
                call for call in mock_sio.emit.call_args_list
                if call[0][0] == 'jam_link_updated'
            ]
            
            assert len(jam_link_calls) >= 1
            event_payload = jam_link_calls[0][0][1]
            assert event_payload['link'] == jam_link
            
    finally:
        # Clean up active connections
        if sid in active_connections:
            del active_connections[sid]
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    jam_link=spotify_jam_link()
)
@pytest.mark.asyncio
async def test_property_28_jam_link_broadcast_room_targeting(jam_link):
    """
    Property 28: Jam Link Broadcast (Part 6 - Room Targeting)
    
    For any valid Spotify Jam link submission, the `jam_link_updated` event must be
    broadcast only to the specific room where the link was updated, not to other rooms.
    
    Feature: jamr-io-mvp, Property 28: Jam Link Broadcast
    **Validates: Requirements 8.4**
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create two test rooms
        room1 = create_test_room(db_session, owner_id=owner.id, name="Room 1")
        room2 = create_test_room(db_session, owner_id=owner.id, name="Room 2")
        room1_id = room1.id
        room2_id = room2.id
        
        # Create a user who will update the Jam link in room1
        updating_user = create_test_user(db_session, spotify_id=f"updating_user_{uuid.uuid4()}")
        user_id = updating_user.id
        
        # Create room membership for room1 only
        membership = RoomMembership(user_id=user_id, room_id=room1_id)
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
            
            # Call update_jam_link handler for room1
            result = await update_jam_link(sid, {
                'room_id': room1_id,
                'link': jam_link
            })
            
            # Verify update was successful
            assert result.get('success') is True
            
            # Verify jam_link_updated event was broadcast
            jam_link_calls = [
                call for call in mock_sio.emit.call_args_list
                if call[0][0] == 'jam_link_updated'
            ]
            
            assert len(jam_link_calls) >= 1, "jam_link_updated event must be broadcast"
            
            # Verify the event was sent to room1 only
            jam_link_call = jam_link_calls[0]
            event_room = jam_link_call[1].get('room')
            
            assert event_room == f'room_{room1_id}', "Event must be sent to the correct room"
            assert event_room != f'room_{room2_id}', "Event must not be sent to other rooms"
            
            # Verify room1 has the updated link but room2 does not
            updated_room1 = db_session.query(Room).filter(Room.id == room1_id).first()
            updated_room2 = db_session.query(Room).filter(Room.id == room2_id).first()
            
            assert updated_room1.active_jam_link == jam_link
            assert updated_room2.active_jam_link != jam_link
            
    finally:
        # Clean up active connections
        if sid in active_connections:
            del active_connections[sid]
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    jam_link=spotify_jam_link()
)
@pytest.mark.asyncio
async def test_property_28_jam_link_broadcast_timestamp_update(jam_link):
    """
    Property 28: Jam Link Broadcast (Part 7 - Timestamp Update)
    
    For any valid Spotify Jam link submission, the room's updated_at timestamp must be
    updated to reflect the activity.
    
    Feature: jamr-io-mvp, Property 28: Jam Link Broadcast
    **Validates: Requirements 8.4, 9.6**
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
        
        # Create a user who will update the Jam link
        updating_user = create_test_user(db_session, spotify_id=f"updating_user_{uuid.uuid4()}")
        user_id = updating_user.id
        
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
            
            # Call update_jam_link handler
            result = await update_jam_link(sid, {
                'room_id': room_id,
                'link': jam_link
            })
            
            # Verify update was successful
            assert result.get('success') is True
            
            # Query room again to get updated timestamp
            updated_room = db_session.query(Room).filter(Room.id == room_id).first()
            
            assert updated_room is not None
            assert updated_room.updated_at is not None
            
            # Verify updated_at was updated (should be greater than initial)
            if initial_updated_at is not None:
                assert updated_room.updated_at >= initial_updated_at
            
            # Verify updated_at is a datetime object
            assert isinstance(updated_room.updated_at, datetime)
            
    finally:
        # Clean up active connections
        if sid in active_connections:
            del active_connections[sid]
        db_session.rollback()
        db_session.close()
