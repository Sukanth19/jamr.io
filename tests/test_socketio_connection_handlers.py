"""Unit tests for Socket.IO connection and disconnection handlers.

**Validates: Requirements 14.4**
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from backend.socketio_server import connect, disconnect, active_connections
from backend.models import User, Room, RoomMembership, Session as SessionModel


@pytest.fixture
def mock_environ_with_cookie():
    """Create a mock environ dict with session cookie."""
    return {
        'HTTP_COOKIE': 'session_token=test_token_123'
    }


@pytest.fixture
def mock_environ_with_asgi_cookie():
    """Create a mock environ dict with ASGI scope cookies."""
    return {
        'asgi.scope': {
            'cookies': {
                'session_token': 'test_token_456'
            }
        }
    }


@pytest.fixture
def mock_environ_no_cookie():
    """Create a mock environ dict without session cookie."""
    return {}


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
def test_session(db_session, test_user):
    """Create a test session."""
    session = SessionModel(
        user_id=test_user.id,
        token="test_token_123",
        expires_at=datetime.now() + timedelta(days=7)
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


@pytest.fixture
def test_room(db_session, test_user):
    """Create a test room."""
    room = Room(
        name="Test Room",
        description="A test room",
        owner_id=test_user.id,
        genre_tags=["rock"],
        taste_vector={"danceability": 0.5},
        user_count=1
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return room


@pytest.fixture
def test_membership(db_session, test_user, test_room):
    """Create a test room membership."""
    membership = RoomMembership(
        user_id=test_user.id,
        room_id=test_room.id
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(membership)
    return membership


@pytest.mark.asyncio
async def test_connect_with_valid_session(mock_environ_with_cookie, test_session, db_session):
    """Test connection with valid session token."""
    sid = "test_sid_123"
    
    with patch('backend.database.get_session_local') as mock_get_session:
        mock_get_session.return_value = lambda: db_session
        
        result = await connect(sid, mock_environ_with_cookie)
        
        # Connection should be accepted
        assert result is True
        
        # sid → user_id mapping should be stored
        assert sid in active_connections
        assert active_connections[sid] == test_session.user_id


@pytest.mark.asyncio
async def test_connect_with_asgi_cookie(mock_environ_with_asgi_cookie, db_session, test_user):
    """Test connection with session token in ASGI scope."""
    sid = "test_sid_456"
    
    # Store user_id before session operations
    user_id = test_user.id
    
    # Create session with token from ASGI scope
    session = SessionModel(
        user_id=user_id,
        token="test_token_456",
        expires_at=datetime.now() + timedelta(days=7)
    )
    db_session.add(session)
    db_session.commit()
    
    with patch('backend.database.get_session_local') as mock_get_session:
        mock_get_session.return_value = lambda: db_session
        
        result = await connect(sid, mock_environ_with_asgi_cookie)
        
        # Connection should be accepted
        assert result is True
        assert sid in active_connections
        assert active_connections[sid] == user_id


@pytest.mark.asyncio
async def test_connect_without_session_token(mock_environ_no_cookie, db_session):
    """Test connection rejection when no session token is provided."""
    sid = "test_sid_no_token"
    
    with patch('backend.database.get_session_local') as mock_get_session:
        mock_get_session.return_value = lambda: db_session
        
        result = await connect(sid, mock_environ_no_cookie)
        
        # Connection should be rejected
        assert result is False
        
        # No mapping should be stored
        assert sid not in active_connections


@pytest.mark.asyncio
async def test_connect_with_invalid_session_token(mock_environ_with_cookie, db_session):
    """Test connection rejection when session token is invalid."""
    sid = "test_sid_invalid"
    
    # No session exists in database with this token
    with patch('backend.database.get_session_local') as mock_get_session:
        mock_get_session.return_value = lambda: db_session
        
        result = await connect(sid, mock_environ_with_cookie)
        
        # Connection should be rejected
        assert result is False
        
        # No mapping should be stored
        assert sid not in active_connections


@pytest.mark.asyncio
async def test_connect_with_expired_session(mock_environ_with_cookie, db_session, test_user):
    """Test connection rejection when session token is expired."""
    sid = "test_sid_expired"
    
    # Create expired session
    expired_session = SessionModel(
        user_id=test_user.id,
        token="test_token_123",
        expires_at=datetime.now() - timedelta(days=1)  # Expired
    )
    db_session.add(expired_session)
    db_session.commit()
    
    with patch('backend.database.get_session_local') as mock_get_session:
        mock_get_session.return_value = lambda: db_session
        
        result = await connect(sid, mock_environ_with_cookie)
        
        # Connection should be rejected
        assert result is False
        
        # No mapping should be stored
        assert sid not in active_connections
        
        # Expired session should be deleted
        remaining_session = db_session.query(SessionModel).filter(
            SessionModel.token == "test_token_123"
        ).first()
        assert remaining_session is None


@pytest.mark.asyncio
async def test_disconnect_cleans_up_user_state(test_user, test_room, test_membership, db_session):
    """Test that disconnect handler cleans up user state properly."""
    sid = "test_sid_disconnect"
    
    # Store all values before session operations
    user_id = test_user.id
    username = test_user.display_name
    room_id = test_room.id
    
    # Set up active connection
    active_connections[sid] = user_id
    
    # Mock sio.emit and sio.leave_room
    with patch('backend.socketio_server.sio') as mock_sio, \
         patch('backend.database.get_session_local') as mock_get_session:
        
        mock_sio.emit = AsyncMock()
        mock_sio.leave_room = AsyncMock()
        mock_get_session.return_value = lambda: db_session
        
        await disconnect(sid)
        
        # Verify room membership was deleted
        membership = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == user_id,
            RoomMembership.room_id == room_id
        ).first()
        assert membership is None
        
        # Verify room user count was decremented
        room = db_session.query(Room).filter(Room.id == room_id).first()
        assert room.user_count == 0
        
        # Verify user_left event was broadcast
        mock_sio.emit.assert_any_call(
            'user_left',
            {
                'user_id': user_id,
                'username': username,
                'room_id': room_id
            },
            room=f'room_{room_id}'
        )
        
        # Verify user_count_updated event was broadcast
        mock_sio.emit.assert_any_call(
            'user_count_updated',
            {
                'room_id': room_id,
                'count': 0
            },
            room=f'room_{room_id}'
        )
        
        # Verify Socket.IO room was left
        mock_sio.leave_room.assert_called_once_with(sid, f'room_{room_id}')
        
        # Verify sid mapping was cleaned up
        assert sid not in active_connections


@pytest.mark.asyncio
async def test_disconnect_with_multiple_rooms(test_user, db_session):
    """Test that disconnect handler removes user from all rooms."""
    sid = "test_sid_multi_room"
    
    # Store user_id before session operations
    user_id = test_user.id
    
    # Create multiple rooms and memberships
    room1 = Room(
        name="Room 1",
        owner_id=user_id,
        genre_tags=["rock"],
        taste_vector={"danceability": 0.5},
        user_count=1
    )
    room2 = Room(
        name="Room 2",
        owner_id=user_id,
        genre_tags=["jazz"],
        taste_vector={"danceability": 0.6},
        user_count=1
    )
    db_session.add_all([room1, room2])
    db_session.commit()
    
    # Store room IDs after commit
    room1_id = room1.id
    room2_id = room2.id
    
    membership1 = RoomMembership(user_id=user_id, room_id=room1_id)
    membership2 = RoomMembership(user_id=user_id, room_id=room2_id)
    db_session.add_all([membership1, membership2])
    db_session.commit()
    
    # Set up active connection
    active_connections[sid] = user_id
    
    with patch('backend.socketio_server.sio') as mock_sio, \
         patch('backend.database.get_session_local') as mock_get_session:
        
        mock_sio.emit = AsyncMock()
        mock_sio.leave_room = AsyncMock()
        mock_get_session.return_value = lambda: db_session
        
        await disconnect(sid)
        
        # Verify both memberships were deleted
        memberships = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == user_id
        ).all()
        assert len(memberships) == 0
        
        # Verify both rooms had user count decremented
        room1_updated = db_session.query(Room).filter(Room.id == room1_id).first()
        room2_updated = db_session.query(Room).filter(Room.id == room2_id).first()
        assert room1_updated.user_count == 0
        assert room2_updated.user_count == 0
        
        # Verify events were broadcast for both rooms
        assert mock_sio.emit.call_count == 4  # 2 user_left + 2 user_count_updated
        assert mock_sio.leave_room.call_count == 2


@pytest.mark.asyncio
async def test_disconnect_without_active_connection(db_session):
    """Test disconnect handler when no active connection exists."""
    sid = "test_sid_no_connection"
    
    with patch('backend.database.get_session_local') as mock_get_session:
        mock_get_session.return_value = lambda: db_session
        
        # Should not raise an error
        await disconnect(sid)
        
        # No error should occur
        assert sid not in active_connections


@pytest.mark.asyncio
async def test_disconnect_with_nonexistent_user(db_session):
    """Test disconnect handler when user doesn't exist in database."""
    sid = "test_sid_no_user"
    
    # Set up active connection with non-existent user
    active_connections[sid] = 99999
    
    with patch('backend.database.get_session_local') as mock_get_session:
        mock_get_session.return_value = lambda: db_session
        
        await disconnect(sid)
        
        # Mapping should still be cleaned up
        assert sid not in active_connections
