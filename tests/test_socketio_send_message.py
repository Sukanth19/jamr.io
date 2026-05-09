"""Unit tests for Socket.IO send_message event handler.

Feature: jamr-io-mvp
Tests the send_message event handler implementation.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
from backend.models import User, Room, Message, Session as SessionModel, RoomMembership
from backend.socketio_server import sio, active_connections


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(
        spotify_id="test_spotify_id",
        display_name="Test User",
        email="test@example.com",
        access_token_encrypted="encrypted_token",
        taste_vector={"danceability": 0.5}
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_room(db_session, test_user):
    """Create a test room."""
    room = Room(
        name="Test Room",
        description="A test room",
        owner_id=test_user.id,
        genre_tags=["rock"],
        taste_vector={"danceability": 0.5},
        user_count=0
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return room


@pytest.mark.asyncio
async def test_send_message_success(db_session, test_user, test_room):
    """
    Test that send_message successfully stores and broadcasts a message.
    
    Validates: Requirements 7.2, 7.3, 7.4, 7.6, 7.7, 9.6
    """
    # Create a room membership
    membership = RoomMembership(
        user_id=test_user.id,
        room_id=test_room.id
    )
    db_session.add(membership)
    db_session.commit()
    
    # Simulate active connection
    sid = "test_sid_123"
    active_connections[sid] = test_user.id
    
    # Store IDs before handler call (to avoid detached instance issues)
    room_id = test_room.id
    user_id = test_user.id
    
    # Prepare message data
    message_content = "Hello, world!"
    data = {
        'room_id': room_id,
        'content': message_content
    }
    
    # Mock database session and Socket.IO emit
    with patch('backend.database.get_session_local') as mock_get_session, \
         patch('backend.socketio_server.sio') as mock_sio:
        
        mock_get_session.return_value = lambda: db_session
        mock_sio.emit = AsyncMock()
        
        # Call send_message handler
        result = await sio.handlers['/']['send_message'](sid, data)
    
    # Verify success response
    assert result['success'] is True
    assert 'message_id' in result
    
    # Verify message was stored in database
    message = db_session.query(Message).filter(Message.id == result['message_id']).first()
    assert message is not None
    assert message.room_id == room_id
    assert message.user_id == user_id
    assert message.content == message_content
    
    # Verify room updated_at was updated (query fresh from database)
    room = db_session.query(Room).filter(Room.id == room_id).first()
    assert room.updated_at is not None
    
    # Cleanup
    del active_connections[sid]


@pytest.mark.asyncio
async def test_send_message_validates_length(db_session, test_user, test_room):
    """
    Test that send_message rejects messages exceeding 500 characters.
    
    Validates: Requirements 7.7
    """
    # Simulate active connection
    sid = "test_sid_456"
    active_connections[sid] = test_user.id
    
    # Prepare message data with content > 500 chars
    message_content = "A" * 501
    data = {
        'room_id': test_room.id,
        'content': message_content
    }
    
    # Call send_message handler
    result = await sio.handlers['/']['send_message'](sid, data)
    
    # Verify error response
    assert 'error' in result
    assert '500' in result['error']
    
    # Verify message was NOT stored in database
    message_count = db_session.query(Message).filter(
        Message.room_id == test_room.id,
        Message.user_id == test_user.id
    ).count()
    assert message_count == 0
    
    # Cleanup
    del active_connections[sid]


@pytest.mark.asyncio
async def test_send_message_sanitizes_html(db_session, test_user, test_room):
    """
    Test that send_message sanitizes HTML content to prevent XSS.
    
    Validates: Requirements 7.6
    """
    # Create a room membership
    membership = RoomMembership(
        user_id=test_user.id,
        room_id=test_room.id
    )
    db_session.add(membership)
    db_session.commit()
    
    # Simulate active connection
    sid = "test_sid_789"
    active_connections[sid] = test_user.id
    
    # Store IDs before handler call
    room_id = test_room.id
    
    # Prepare message data with HTML content
    message_content = "<script>alert('xss')</script>"
    data = {
        'room_id': room_id,
        'content': message_content
    }
    
    # Mock database session and Socket.IO emit
    with patch('backend.database.get_session_local') as mock_get_session, \
         patch('backend.socketio_server.sio') as mock_sio:
        
        mock_get_session.return_value = lambda: db_session
        mock_sio.emit = AsyncMock()
        
        # Call send_message handler
        result = await sio.handlers['/']['send_message'](sid, data)
    
    # Verify success response
    assert result['success'] is True
    
    # Verify message was sanitized in database
    message = db_session.query(Message).filter(Message.id == result['message_id']).first()
    assert message is not None
    assert '<script>' not in message.content
    assert '&lt;script&gt;' in message.content
    
    # Cleanup
    del active_connections[sid]


@pytest.mark.asyncio
async def test_send_message_requires_authentication(db_session, test_room):
    """
    Test that send_message rejects unauthenticated requests.
    """
    # Prepare message data without active connection
    sid = "test_sid_unauth"
    data = {
        'room_id': test_room.id,
        'content': "Hello"
    }
    
    # Call send_message handler
    result = await sio.handlers['/']['send_message'](sid, data)
    
    # Verify error response
    assert 'error' in result
    assert 'authenticated' in result['error'].lower()


@pytest.mark.asyncio
async def test_send_message_requires_room_id(db_session, test_user):
    """
    Test that send_message requires room_id in data.
    """
    # Simulate active connection
    sid = "test_sid_no_room"
    active_connections[sid] = test_user.id
    
    # Prepare message data without room_id
    data = {
        'content': "Hello"
    }
    
    # Call send_message handler
    result = await sio.handlers['/']['send_message'](sid, data)
    
    # Verify error response
    assert 'error' in result
    assert 'room_id' in result['error'].lower()
    
    # Cleanup
    del active_connections[sid]


@pytest.mark.asyncio
async def test_send_message_requires_content(db_session, test_user, test_room):
    """
    Test that send_message requires content in data.
    """
    # Simulate active connection
    sid = "test_sid_no_content"
    active_connections[sid] = test_user.id
    
    # Prepare message data without content
    data = {
        'room_id': test_room.id
    }
    
    # Call send_message handler
    result = await sio.handlers['/']['send_message'](sid, data)
    
    # Verify error response
    assert 'error' in result
    assert 'content' in result['error'].lower()
    
    # Cleanup
    del active_connections[sid]
