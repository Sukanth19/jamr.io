"""Integration tests for Socket.IO server with FastAPI."""

import pytest
from fastapi.testclient import TestClient
from backend.main import app


def test_socketio_endpoint_mounted():
    """Test that Socket.IO endpoint is mounted on FastAPI app."""
    client = TestClient(app)
    
    # An Engine.IO polling handshake at /socket.io/ (the path the browser
    # client uses) should succeed and return a session id
    response = client.get("/socket.io/?EIO=4&transport=polling")
    
    assert response.status_code == 200
    assert '"sid"' in response.text


def test_fastapi_health_endpoint_still_works():
    """Test that FastAPI endpoints still work after Socket.IO integration."""
    client = TestClient(app)
    
    response = client.get("/health")
    
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_fastapi_root_endpoint_still_works():
    """Test that FastAPI root endpoint still serves the landing page after Socket.IO integration."""
    client = TestClient(app)
    
    response = client.get("/")
    
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
