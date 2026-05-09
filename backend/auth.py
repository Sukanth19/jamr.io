"""Authentication endpoints for Spotify OAuth flow."""

import os
import secrets
from datetime import datetime, timedelta
from typing import Dict
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create router for auth endpoints
router = APIRouter(prefix="/auth", tags=["Authentication"])

# In-memory storage for CSRF state tokens (for MVP)
# In production, use Redis or database with expiration
_state_store: Dict[str, datetime] = {}

# Spotify OAuth configuration
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"

# Required Spotify scopes
SPOTIFY_SCOPES = [
    "user-read-email",
    "user-top-read"
]


def _cleanup_expired_states():
    """Remove expired state tokens from storage."""
    now = datetime.now()
    expired_keys = [
        state for state, expires_at in _state_store.items()
        if expires_at < now
    ]
    for key in expired_keys:
        del _state_store[key]


@router.get("/spotify")
async def spotify_oauth_redirect():
    """
    Initiate Spotify OAuth flow.
    
    Generates a CSRF state parameter, stores it temporarily, and redirects
    the user to Spotify's authorization page with required scopes.
    
    **Validates: Requirements 1.1, 1.2**
    
    Returns:
        RedirectResponse: Redirect to Spotify authorization URL
    
    Raises:
        HTTPException: If Spotify client configuration is missing
    """
    # Validate Spotify configuration
    if not SPOTIFY_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "CONFIGURATION_ERROR",
                    "message": "Spotify client ID not configured"
                }
            }
        )
    
    if not SPOTIFY_REDIRECT_URI:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "CONFIGURATION_ERROR",
                    "message": "Spotify redirect URI not configured"
                }
            }
        )
    
    # Clean up expired state tokens
    _cleanup_expired_states()
    
    # Generate random CSRF state parameter (32 bytes = 64 hex characters)
    state = secrets.token_urlsafe(32)
    
    # Store state with 10-minute expiration
    expires_at = datetime.now() + timedelta(minutes=10)
    _state_store[state] = expires_at
    
    # Construct Spotify authorization URL
    auth_params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "state": state,
        "scope": " ".join(SPOTIFY_SCOPES),
        "show_dialog": "false"  # Don't force approval screen on every login
    }
    
    authorization_url = f"{SPOTIFY_AUTH_URL}?{urlencode(auth_params)}"
    
    # Redirect user to Spotify authorization page
    return RedirectResponse(url=authorization_url, status_code=302)


def verify_state(state: str) -> bool:
    """
    Verify CSRF state parameter.
    
    Args:
        state: State parameter to verify
    
    Returns:
        bool: True if state is valid and not expired, False otherwise
    """
    _cleanup_expired_states()
    
    if state not in _state_store:
        return False
    
    # Check if state has expired
    if _state_store[state] < datetime.now():
        del _state_store[state]
        return False
    
    # State is valid, remove it (one-time use)
    del _state_store[state]
    return True
