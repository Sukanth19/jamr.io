"""Authentication endpoints for Spotify OAuth flow."""

import os
import secrets
import httpx
from datetime import datetime, timedelta
from typing import Dict
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
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


@router.get("/callback")
async def spotify_oauth_callback(code: str = None, state: str = None, error: str = None):
    """
    Handle Spotify OAuth callback.
    
    Exchanges authorization code for access token, retrieves user profile,
    generates taste vector, and creates user session.
    
    **Validates: Requirements 1.3, 1.4**
    
    Args:
        code: Authorization code from Spotify
        state: CSRF state parameter
        error: Error from Spotify (if authorization failed)
    
    Returns:
        RedirectResponse: Redirect to room discovery page on success
    
    Raises:
        HTTPException: If state verification fails, code exchange fails, or other errors occur
    """
    from backend.database import get_db
    from backend.models import User
    from backend.encryption import get_encryptor
    
    # Check if user denied authorization
    if error:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "AUTHORIZATION_DENIED",
                    "message": f"Spotify authorization failed: {error}"
                }
            }
        )
    
    # Validate required parameters
    if not code:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "MISSING_CODE",
                    "message": "Authorization code is required"
                }
            }
        )
    
    if not state:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "MISSING_STATE",
                    "message": "State parameter is required"
                }
            }
        )
    
    # Verify CSRF state parameter
    if not verify_state(state):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_STATE",
                    "message": "Invalid or expired state parameter"
                }
            }
        )
    
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
    
    spotify_client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    if not spotify_client_secret:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "CONFIGURATION_ERROR",
                    "message": "Spotify client secret not configured"
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
    
    # Exchange authorization code for access token
    token_url = "https://accounts.spotify.com/api/token"
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": spotify_client_secret
    }
    
    try:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=token_data)
            
            if token_response.status_code != 200:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "TOKEN_EXCHANGE_FAILED",
                            "message": "Failed to exchange authorization code for access token"
                        }
                    }
                )
            
            token_json = token_response.json()
            access_token = token_json.get("access_token")
            refresh_token = token_json.get("refresh_token")
            expires_in = token_json.get("expires_in", 3600)
            
            if not access_token:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "MISSING_ACCESS_TOKEN",
                            "message": "Access token not returned by Spotify"
                        }
                    }
                )
            
            # Calculate token expiration time
            token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            # Fetch user profile from Spotify
            profile_response = await client.get(
                "https://api.spotify.com/v1/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if profile_response.status_code != 200:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "PROFILE_FETCH_FAILED",
                            "message": "Failed to fetch user profile from Spotify"
                        }
                    }
                )
            
            profile_data = profile_response.json()
            spotify_id = profile_data.get("id")
            display_name = profile_data.get("display_name") or profile_data.get("id")
            email = profile_data.get("email")
            profile_image_url = None
            if profile_data.get("images") and len(profile_data["images"]) > 0:
                profile_image_url = profile_data["images"][0].get("url")
            
            # Fetch top tracks for taste vector generation
            top_tracks_response = await client.get(
                "https://api.spotify.com/v1/me/top/tracks?limit=50&time_range=medium_term",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if top_tracks_response.status_code != 200:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "TOP_TRACKS_FETCH_FAILED",
                            "message": "Failed to fetch top tracks from Spotify"
                        }
                    }
                )
            
            top_tracks_data = top_tracks_response.json()
            track_ids = [track["id"] for track in top_tracks_data.get("items", [])]
            
            # Fetch audio features for top tracks
            taste_vector = {}
            if track_ids:
                audio_features_response = await client.get(
                    f"https://api.spotify.com/v1/audio-features?ids={','.join(track_ids)}",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if audio_features_response.status_code == 200:
                    audio_features_data = audio_features_response.json()
                    audio_features = audio_features_data.get("audio_features", [])
                    
                    # Generate taste vector from audio features
                    taste_vector = _generate_taste_vector(audio_features)
            
            # If no taste vector generated, use default
            if not taste_vector:
                taste_vector = _default_taste_vector()
            
            # Encrypt tokens
            encryptor = get_encryptor()
            access_token_encrypted = encryptor.encrypt(access_token)
            refresh_token_encrypted = encryptor.encrypt(refresh_token) if refresh_token else None
            
            # Store user in database
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Check if user already exists
                existing_user = db.query(User).filter(User.spotify_id == spotify_id).first()
                
                if existing_user:
                    # Update existing user
                    existing_user.display_name = display_name
                    existing_user.email = email
                    existing_user.profile_image_url = profile_image_url
                    existing_user.access_token_encrypted = access_token_encrypted
                    existing_user.refresh_token_encrypted = refresh_token_encrypted
                    existing_user.token_expires_at = token_expires_at
                    existing_user.taste_vector = taste_vector
                    existing_user.updated_at = datetime.now()
                    db.commit()
                    user = existing_user
                else:
                    # Create new user
                    user = User(
                        spotify_id=spotify_id,
                        display_name=display_name,
                        email=email,
                        profile_image_url=profile_image_url,
                        access_token_encrypted=access_token_encrypted,
                        refresh_token_encrypted=refresh_token_encrypted,
                        token_expires_at=token_expires_at,
                        taste_vector=taste_vector
                    )
                    db.add(user)
                    db.commit()
                    db.refresh(user)
                
                # Generate unique session token
                session_token = secrets.token_urlsafe(32)
                
                # Calculate session expiration (7 days from now)
                session_expires_at = datetime.now() + timedelta(days=7)
                
                # Store session in database
                from backend.models import Session as SessionModel
                
                session = SessionModel(
                    user_id=user.id,
                    token=session_token,
                    expires_at=session_expires_at
                )
                db.add(session)
                db.commit()
                
                # Create redirect response
                response = RedirectResponse(url="/discover", status_code=302)
                
                # Set HTTP-only cookie with session token
                response.set_cookie(
                    key="session_token",
                    value=session_token,
                    httponly=True,
                    max_age=7 * 24 * 60 * 60,  # 7 days in seconds
                    secure=True,  # Only send over HTTPS
                    samesite="lax"  # CSRF protection
                )
                
                return response
                
            finally:
                db.close()
    
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "NETWORK_ERROR",
                    "message": f"Network error during Spotify API request: {str(e)}"
                }
            }
        )
    except Exception as e:
        # Log the error (in production, use proper logging)
        print(f"OAuth callback error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An error occurred during authentication"
                }
            }
        )


def _generate_taste_vector(audio_features: list) -> dict:
    """
    Generate taste vector from Spotify audio features.
    
    Args:
        audio_features: List of audio feature dictionaries from Spotify API
    
    Returns:
        dict: Taste vector with normalized feature values
    """
    if not audio_features:
        return _default_taste_vector()
    
    # Filter out None values (Spotify sometimes returns null for unavailable features)
    valid_features = [f for f in audio_features if f is not None]
    
    if not valid_features:
        return _default_taste_vector()
    
    # Aggregate features
    feature_keys = ['danceability', 'energy', 'valence', 'acousticness', 
                    'instrumentalness', 'speechiness', 'tempo']
    
    aggregated = {key: [] for key in feature_keys}
    
    for feature in valid_features:
        for key in feature_keys:
            if key in feature and feature[key] is not None:
                aggregated[key].append(feature[key])
    
    # Calculate averages
    taste_vector = {}
    for key, values in aggregated.items():
        if values:
            avg = sum(values) / len(values)
            if key == 'tempo':
                # Normalize tempo to 0-1 range (assume max 200 BPM)
                taste_vector['tempo_normalized'] = min(avg / 200.0, 1.0)
            else:
                taste_vector[key] = avg
    
    # Ensure all required keys are present
    required_keys = ['danceability', 'energy', 'valence', 'acousticness', 
                     'instrumentalness', 'speechiness', 'tempo_normalized']
    
    for key in required_keys:
        if key not in taste_vector:
            taste_vector[key] = 0.5  # Default to middle value
    
    return taste_vector


def _default_taste_vector() -> dict:
    """
    Return a default taste vector.
    
    Returns:
        dict: Default taste vector with neutral values
    """
    return {
        'danceability': 0.5,
        'energy': 0.5,
        'valence': 0.5,
        'acousticness': 0.5,
        'instrumentalness': 0.5,
        'speechiness': 0.5,
        'tempo_normalized': 0.5
    }
