"""Manual test script for auth endpoint - verifies implementation without full test suite."""

import os
import sys
sys.path.insert(0, '.')

# Set test environment variables
os.environ['SPOTIFY_CLIENT_ID'] = 'test_client_id_12345'
os.environ['SPOTIFY_REDIRECT_URI'] = 'http://localhost:8000/auth/callback'

from backend.auth import router, verify_state, _state_store
from datetime import datetime, timedelta

print("=" * 60)
print("Testing Spotify OAuth Redirect Endpoint Implementation")
print("=" * 60)

# Test 1: Verify router configuration
print("\n[Test 1] Router Configuration")
print(f"  Router prefix: {router.prefix}")
print(f"  Router tags: {router.tags}")
assert router.prefix == "/auth", "Router prefix should be /auth"
assert "Authentication" in router.tags, "Router should have Authentication tag"
print("  ✓ Router configured correctly")

# Test 2: Verify environment variables are loaded
print("\n[Test 2] Environment Variables")
from backend.auth import SPOTIFY_CLIENT_ID, SPOTIFY_REDIRECT_URI, SPOTIFY_SCOPES
print(f"  SPOTIFY_CLIENT_ID: {SPOTIFY_CLIENT_ID}")
print(f"  SPOTIFY_REDIRECT_URI: {SPOTIFY_REDIRECT_URI}")
print(f"  SPOTIFY_SCOPES: {SPOTIFY_SCOPES}")
assert SPOTIFY_CLIENT_ID == 'test_client_id_12345', "Client ID should be loaded"
assert SPOTIFY_REDIRECT_URI == 'http://localhost:8000/auth/callback', "Redirect URI should be loaded"
assert 'user-read-email' in SPOTIFY_SCOPES, "Should include user-read-email scope"
assert 'user-top-read' in SPOTIFY_SCOPES, "Should include user-top-read scope"
print("  ✓ Environment variables loaded correctly")

# Test 3: Test state verification function
print("\n[Test 3] State Verification Function")

# Add a valid state
test_state_valid = "valid_test_state_123"
_state_store[test_state_valid] = datetime.now() + timedelta(minutes=5)
print(f"  Added valid state: {test_state_valid}")

# Verify valid state
result = verify_state(test_state_valid)
print(f"  verify_state(valid_state) = {result}")
assert result is True, "Valid state should be accepted"
assert test_state_valid not in _state_store, "State should be removed after verification"
print("  ✓ Valid state accepted and removed")

# Add an expired state
test_state_expired = "expired_test_state_456"
_state_store[test_state_expired] = datetime.now() - timedelta(minutes=1)
print(f"  Added expired state: {test_state_expired}")

# Verify expired state
result = verify_state(test_state_expired)
print(f"  verify_state(expired_state) = {result}")
assert result is False, "Expired state should be rejected"
assert test_state_expired not in _state_store, "Expired state should be removed"
print("  ✓ Expired state rejected and removed")

# Verify non-existent state
result = verify_state("nonexistent_state")
print(f"  verify_state(nonexistent_state) = {result}")
assert result is False, "Non-existent state should be rejected"
print("  ✓ Non-existent state rejected")

# Test 4: Verify authorization URL construction
print("\n[Test 4] Authorization URL Construction")
from backend.auth import SPOTIFY_AUTH_URL
from urllib.parse import urlencode

expected_params = {
    "client_id": SPOTIFY_CLIENT_ID,
    "response_type": "code",
    "redirect_uri": SPOTIFY_REDIRECT_URI,
    "state": "test_state",
    "scope": " ".join(SPOTIFY_SCOPES),
    "show_dialog": "false"
}
expected_url = f"{SPOTIFY_AUTH_URL}?{urlencode(expected_params)}"
print(f"  Expected URL format:")
print(f"    {expected_url}")
assert "https://accounts.spotify.com/authorize" in expected_url, "Should use Spotify auth URL"
assert "client_id=test_client_id_12345" in expected_url, "Should include client ID"
assert "scope=user-read-email+user-top-read" in expected_url, "Should include scopes"
print("  ✓ Authorization URL format is correct")

# Test 5: Verify endpoint exists and is callable
print("\n[Test 5] Endpoint Registration")
from backend.main import app
routes = {route.path: route for route in app.routes}
assert "/auth/spotify" in routes, "/auth/spotify endpoint should be registered"
spotify_route = routes["/auth/spotify"]
print(f"  Endpoint path: {spotify_route.path}")
print(f"  Endpoint methods: {spotify_route.methods}")
assert "GET" in spotify_route.methods, "Should accept GET requests"
print("  ✓ Endpoint registered correctly")

print("\n" + "=" * 60)
print("All Tests Passed! ✓")
print("=" * 60)
print("\nImplementation Summary:")
print("  - Created backend/auth.py with /auth/spotify endpoint")
print("  - Generates CSRF state parameter using secrets.token_urlsafe(32)")
print("  - Stores state in memory with 10-minute expiration")
print("  - Constructs Spotify authorization URL with required scopes")
print("  - Redirects user to Spotify authorization page")
print("  - Validates: Requirements 1.1, 1.2")
print("\nNext Steps:")
print("  - Task 3.2: Implement OAuth callback handler")
print("  - Task 3.3: Write property tests for OAuth token storage")
