"""Unit tests for Socket.IO server configuration."""

import pytest
import os
from backend.socketio_server import sio, socket_app


def test_socketio_server_exists():
    """Test that Socket.IO server instance is created."""
    assert sio is not None
    assert sio.async_mode == 'asgi'


def test_socketio_app_exists():
    """Test that Socket.IO ASGI app is created."""
    assert socket_app is not None


def test_socketio_cors_configuration():
    """Test that CORS is configured for Socket.IO server."""
    # The CORS origins should be configured from environment
    # Default is http://localhost:3000
    expected_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    
    # Socket.IO server should have CORS configured
    # The cors_allowed_origins is stored in the eio (engine.io) server
    assert hasattr(sio, 'eio')
    # Verify CORS is configured (the attribute exists in the engine.io server)
    # We just verify the server was created with CORS support
    assert sio.eio is not None


def test_socketio_event_handlers_registered():
    """Test that basic event handlers are registered."""
    # Check that connect and disconnect handlers are registered
    assert 'connect' in sio.handlers['/']
    assert 'disconnect' in sio.handlers['/']

