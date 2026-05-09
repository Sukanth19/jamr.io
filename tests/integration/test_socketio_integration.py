"""Integration tests for Socket.IO server with FastAPI."""

import pytest
from fastapi.testclient import TestClient
from backend.main import app


def test_socketio_endpoint_mounted():
    """Test that Socket.IO endpoint is mounted on FastAPI app."""
    client = TestClient(app)
    
    # The Socket.IO endpoint should be accessible
    # We expect a 400 or similar response for a GET request without proper Socket.IO handshake
    # but the endpoint should exist
    response = client.get("/socket.io/")
    
    # Socket.IO will respond with an error for invalid requests, but the endpoint exists
    # We just verify it doesn't return 404
    assert response.status_code != 404


def test_fastapi_health_endpoint_still_works():
    """Test that FastAPI endpoints still work after Socket.IO integration."""
    client = TestClient(app)
    
    response = client.get("/health")
    
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_fastapi_root_endpoint_still_works():
    """Test that FastAPI root endpoint still works after Socket.IO integration."""
    client = TestClient(app)
    
    response = client.get("/")
    
    assert response.status_code == 200
    assert "message" in response.json()
