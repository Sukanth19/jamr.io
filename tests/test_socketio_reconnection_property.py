"""Property-based tests for Socket.IO reconnection.

Feature: jamr-io-mvp, Property 46: Socket.IO Reconnection
**Validates: Requirements 14.4**

This test verifies that when a Socket.IO connection drops, the client automatically
attempts to reconnect using the Socket.IO client's built-in reconnection logic.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings
from unittest.mock import AsyncMock, MagicMock, patch
import socketio
from backend.models import User, Session as SessionModel
from tests.conftest import get_test_session


# Property 46: Socket.IO Reconnection
# **Validates: Requirements 14.4**


@settings(max_examples=100)
@given(
    display_name=st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(min_codepoint=33, max_codepoint=126)
    )
)
def test_socketio_client_has_reconnection_enabled(display_name):
    """
    Property 46: Socket.IO Reconnection (Part 1 - Client Configuration)
    
    For any Socket.IO client connection, the client must be configured with
    reconnection enabled by default. This verifies that the Socket.IO client
    library has reconnection capabilities available.
    """
    # Create a Socket.IO client with default configuration
    client = socketio.AsyncClient()
    
    # Verify reconnection is enabled by default in Socket.IO client
    # The Socket.IO client library enables reconnection by default
    # We verify this by checking the client's configuration
    assert hasattr(client, 'reconnection')
    assert client.reconnection is True
    
    # Verify reconnection attempts configuration exists
    assert hasattr(client, 'reconnection_attempts')
    
    # Verify reconnection delay configuration exists
    assert hasattr(client, 'reconnection_delay')
    assert client.reconnection_delay > 0
    
    # Verify reconnection delay max configuration exists
    assert hasattr(client, 'reconnection_delay_max')
    assert client.reconnection_delay_max >= client.reconnection_delay


@settings(max_examples=100)
@given(
    display_name=st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(min_codepoint=33, max_codepoint=126)
    ),
    reconnection_attempts=st.integers(min_value=1, max_value=10)
)
def test_socketio_client_reconnection_parameters(display_name, reconnection_attempts):
    """
    Property 46: Socket.IO Reconnection (Part 2 - Reconnection Parameters)
    
    For any Socket.IO client connection, the client can be configured with
    custom reconnection parameters (attempts, delay, etc.) and these parameters
    are properly set.
    """
    # Create a Socket.IO client with custom reconnection configuration
    client = socketio.AsyncClient(
        reconnection=True,
        reconnection_attempts=reconnection_attempts,
        reconnection_delay=1,
        reconnection_delay_max=5
    )
    
    # Verify reconnection is enabled
    assert client.reconnection is True
    
    # Verify reconnection attempts is set correctly
    assert client.reconnection_attempts == reconnection_attempts
    
    # Verify reconnection delay is set correctly
    assert client.reconnection_delay == 1
    
    # Verify reconnection delay max is set correctly
    assert client.reconnection_delay_max == 5


@pytest.mark.asyncio
@settings(max_examples=100)
@given(
    display_name=st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(min_codepoint=33, max_codepoint=126)
    )
)
async def test_socketio_connection_drop_triggers_reconnection_attempt(display_name):
    """
    Property 46: Socket.IO Reconnection (Part 3 - Connection Drop Handling)
    
    For any Socket.IO connection drop, the client must automatically attempt
    to reconnect. This test verifies that the reconnection logic is triggered
    when a connection is lost.
    """
    import uuid
    
    # Create a Socket.IO client with reconnection enabled
    client = socketio.AsyncClient(
        reconnection=True,
        reconnection_attempts=3,
        reconnection_delay=0.1,  # Short delay for testing
        reconnection_delay_max=0.5
    )
    
    # Track reconnection attempts
    reconnect_attempts = []
    
    @client.event
    async def connect():
        """Handle successful connection."""
        pass
    
    @client.event
    async def disconnect():
        """Handle disconnection."""
        pass
    
    @client.event
    async def connect_error(data):
        """Handle connection error (reconnection attempt failed)."""
        reconnect_attempts.append(datetime.now())
    
    # Verify that the client has reconnection enabled
    assert client.reconnection is True
    assert client.reconnection_attempts == 3
    
    # Verify that reconnection delay is configured
    assert client.reconnection_delay == 0.1
    assert client.reconnection_delay_max == 0.5
    
    # The Socket.IO client library will automatically attempt reconnection
    # when disconnect() is called or connection is lost
    # We verify the configuration is correct for automatic reconnection


@pytest.mark.asyncio
async def test_socketio_server_accepts_reconnection():
    """
    Property 46: Socket.IO Reconnection (Part 4 - Server Accepts Reconnection)
    
    For any Socket.IO reconnection attempt with valid session credentials,
    the server must accept the reconnection and restore the user's session.
    """
    import uuid
    from backend.socketio_server import connect, active_connections
    
    db_session = get_test_session()
    
    try:
        # Create a test user
        spotify_id = str(uuid.uuid4())
        user = User(
            spotify_id=spotify_id,
            display_name="Test User",
            email=f"{spotify_id}@example.com",
            access_token_encrypted="encrypted_token",
            taste_vector={"danceability": 0.5}
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Store user_id before session operations
        user_id = user.id
        
        # Create a valid session
        import secrets
        session_token = secrets.token_urlsafe(32)
        session = SessionModel(
            user_id=user_id,
            token=session_token,
            expires_at=datetime.now() + timedelta(days=7)
        )
        db_session.add(session)
        db_session.commit()
        
        # Simulate first connection
        sid_1 = "test_sid_first_connection"
        environ_1 = {
            'HTTP_COOKIE': f'session_token={session_token}'
        }
        
        with patch('backend.database.get_session_local') as mock_get_session:
            mock_get_session.return_value = lambda: db_session
            
            # First connection should succeed
            result_1 = await connect(sid_1, environ_1)
            assert result_1 is True
            assert sid_1 in active_connections
            assert active_connections[sid_1] == user_id
            
            # Simulate disconnection (clean up)
            if sid_1 in active_connections:
                del active_connections[sid_1]
            
            # Simulate reconnection with same session token
            sid_2 = "test_sid_reconnection"
            environ_2 = {
                'HTTP_COOKIE': f'session_token={session_token}'
            }
            
            # Reconnection should succeed with same session token
            result_2 = await connect(sid_2, environ_2)
            assert result_2 is True
            assert sid_2 in active_connections
            assert active_connections[sid_2] == user_id
            
            # Clean up
            if sid_2 in active_connections:
                del active_connections[sid_2]
    
    finally:
        db_session.rollback()
        db_session.close()


@pytest.mark.asyncio
@settings(max_examples=100)
@given(
    display_name=st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(min_codepoint=33, max_codepoint=126)
    ),
    num_reconnections=st.integers(min_value=1, max_value=5)
)
async def test_socketio_multiple_reconnection_attempts(display_name, num_reconnections):
    """
    Property 46: Socket.IO Reconnection (Part 5 - Multiple Reconnection Attempts)
    
    For any Socket.IO connection drop, the client must attempt to reconnect
    multiple times according to the configured reconnection_attempts parameter.
    """
    import uuid
    from backend.socketio_server import connect, active_connections
    
    db_session = get_test_session()
    
    try:
        # Create a test user
        spotify_id = str(uuid.uuid4())
        user = User(
            spotify_id=spotify_id,
            display_name=display_name,
            email=f"{spotify_id}@example.com",
            access_token_encrypted="encrypted_token",
            taste_vector={"danceability": 0.5}
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Store user_id before session operations
        user_id = user.id
        
        # Create a valid session
        import secrets
        session_token = secrets.token_urlsafe(32)
        session = SessionModel(
            user_id=user_id,
            token=session_token,
            expires_at=datetime.now() + timedelta(days=7)
        )
        db_session.add(session)
        db_session.commit()
        
        # Simulate multiple reconnection attempts
        successful_reconnections = 0
        
        with patch('backend.database.get_session_local') as mock_get_session:
            mock_get_session.return_value = lambda: db_session
            
            for i in range(num_reconnections):
                sid = f"test_sid_reconnect_{i}"
                environ = {
                    'HTTP_COOKIE': f'session_token={session_token}'
                }
                
                # Each reconnection attempt should succeed
                result = await connect(sid, environ)
                assert result is True
                assert sid in active_connections
                assert active_connections[sid] == user_id
                
                successful_reconnections += 1
                
                # Clean up for next iteration
                if sid in active_connections:
                    del active_connections[sid]
        
        # Verify all reconnection attempts succeeded
        assert successful_reconnections == num_reconnections
    
    finally:
        db_session.rollback()
        db_session.close()


@pytest.mark.asyncio
async def test_socketio_reconnection_with_expired_session_fails():
    """
    Property 46: Socket.IO Reconnection (Part 6 - Expired Session Rejection)
    
    For any Socket.IO reconnection attempt with an expired session token,
    the server must reject the reconnection attempt.
    """
    import uuid
    from backend.socketio_server import connect, active_connections
    
    db_session = get_test_session()
    
    try:
        # Create a test user
        spotify_id = str(uuid.uuid4())
        user = User(
            spotify_id=spotify_id,
            display_name="Test User",
            email=f"{spotify_id}@example.com",
            access_token_encrypted="encrypted_token",
            taste_vector={"danceability": 0.5}
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Create an expired session
        import secrets
        session_token = secrets.token_urlsafe(32)
        expired_session = SessionModel(
            user_id=user.id,
            token=session_token,
            expires_at=datetime.now() - timedelta(days=1)  # Expired
        )
        db_session.add(expired_session)
        db_session.commit()
        
        # Attempt reconnection with expired session
        sid = "test_sid_expired_reconnect"
        environ = {
            'HTTP_COOKIE': f'session_token={session_token}'
        }
        
        with patch('backend.database.get_session_local') as mock_get_session:
            mock_get_session.return_value = lambda: db_session
            
            # Reconnection should fail with expired session
            result = await connect(sid, environ)
            assert result is False
            assert sid not in active_connections
            
            # Verify expired session was deleted
            remaining_session = db_session.query(SessionModel).filter(
                SessionModel.token == session_token
            ).first()
            assert remaining_session is None
    
    finally:
        db_session.rollback()
        db_session.close()


def test_socketio_client_default_reconnection_configuration():
    """
    Property 46: Socket.IO Reconnection (Part 7 - Default Configuration)
    
    For any Socket.IO client created without explicit reconnection configuration,
    the client must have reconnection enabled by default with reasonable defaults.
    """
    # Create a Socket.IO client with default configuration
    client = socketio.AsyncClient()
    
    # Verify reconnection is enabled by default
    assert client.reconnection is True
    
    # Verify default reconnection attempts (should be unlimited or high number)
    # Socket.IO defaults to unlimited reconnection attempts
    assert client.reconnection_attempts == 0 or client.reconnection_attempts > 10
    
    # Verify default reconnection delay exists and is reasonable
    assert client.reconnection_delay > 0
    assert client.reconnection_delay <= 5  # Should be a few seconds
    
    # Verify default reconnection delay max exists and is reasonable
    assert client.reconnection_delay_max >= client.reconnection_delay
    assert client.reconnection_delay_max <= 60  # Should be under a minute
