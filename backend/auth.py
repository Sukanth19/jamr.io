"""Authentication endpoints for Spotify OAuth flow."""

import os
import secrets
import httpx
from datetime import datetime, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Response, Depends, Cookie
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from typing import List
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from backend.database import get_db
from backend.models import User
from backend.recommendation_engine import (
    GENRE_VECTORS,
    map_spotify_genres,
    generate_taste_vector_from_genres,
    generate_room_taste_vector,
)
from backend.serializers import serialize_user

# Load environment variables
load_dotenv()

# Create router for auth endpoints
router = APIRouter(prefix="/auth", tags=["Authentication"])

# CSRF state is kept in a short-lived cookie (not server memory) so it
# survives server restarts and works with multiple workers
STATE_COOKIE = "oauth_state"
STATE_MAX_AGE = 10 * 60  # 10 minutes

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"

# Required Spotify scopes
SPOTIFY_SCOPES = [
    "user-read-email",
    "user-top-read"
]


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
    # Get Spotify configuration (read fresh from environment)
    spotify_client_id = os.getenv("SPOTIFY_CLIENT_ID")
    spotify_redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")
    
    # Validate Spotify configuration
    if not spotify_client_id:
        raise HTTPException(
            status_code=500,
            detail="Spotify client ID not configured"
        )
    
    if not spotify_redirect_uri:
        raise HTTPException(
            status_code=500,
            detail="Spotify redirect URI not configured"
        )
    
    # Generate random CSRF state parameter
    state = secrets.token_urlsafe(32)
    
    # Construct Spotify authorization URL
    auth_params = {
        "client_id": spotify_client_id,
        "response_type": "code",
        "redirect_uri": spotify_redirect_uri,
        "state": state,
        "scope": " ".join(SPOTIFY_SCOPES),
        "show_dialog": "false"  # Don't force approval screen on every login
    }
    
    authorization_url = f"{SPOTIFY_AUTH_URL}?{urlencode(auth_params)}"
    
    # Redirect user to Spotify authorization page, remembering the state
    # in a cookie that expires after 10 minutes
    response = RedirectResponse(url=authorization_url, status_code=302)
    response.set_cookie(
        key=STATE_COOKIE,
        value=state,
        httponly=True,
        max_age=STATE_MAX_AGE,
        secure=os.getenv("ENVIRONMENT", "development") == "production",
        samesite="lax"  # Sent on the top-level redirect back from Spotify
    )
    return response


def verify_state(state: str, expected_state: str) -> bool:
    """
    Verify CSRF state parameter against the value stored in the state cookie.
    
    Args:
        state: State parameter returned by Spotify
        expected_state: State stored in the oauth_state cookie (None if the
            cookie is missing or expired)
    
    Returns:
        bool: True if both are present and match, False otherwise
    """
    if not state or not expected_state:
        return False
    
    return secrets.compare_digest(state, expected_state)


@router.get("/callback")
async def spotify_oauth_callback(
    code: str = None,
    state: str = None,
    error: str = None,
    oauth_state: str = Cookie(None, alias=STATE_COOKIE)
):
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
    if not verify_state(state, oauth_state):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_STATE",
                    "message": (
                        "Login session expired or was started from a different address. "
                        "Open the app at the same address as SPOTIFY_REDIRECT_URI "
                        "(e.g. http://127.0.0.1:8000) and log in again."
                    )
                }
            }
        )
    
    # Validate Spotify configuration
    spotify_client_id = os.getenv("SPOTIFY_CLIENT_ID")
    spotify_redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")
    
    if not spotify_client_id:
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
    
    if not spotify_redirect_uri:
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
        "redirect_uri": spotify_redirect_uri,
        "client_id": spotify_client_id,
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
            
            # Fall back to top artists' genres (audio-features returns 403
            # for Spotify apps created after November 2024)
            if not taste_vector:
                top_artists_response = await client.get(
                    "https://api.spotify.com/v1/me/top/artists?limit=50&time_range=medium_term",
                    headers={"Authorization": f"Bearer {access_token}"}
                )

                if top_artists_response.status_code == 200:
                    spotify_genres = [
                        genre
                        for artist in top_artists_response.json().get("items", [])
                        for genre in artist.get("genres", [])
                    ]
                    if map_spotify_genres(spotify_genres):
                        taste_vector = generate_taste_vector_from_genres(spotify_genres)

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
                    # Keep the taste derived from genres the user picked
                    if not existing_user.favorite_genres:
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
                
                # State is single-use: clear the cookie
                response.delete_cookie(STATE_COOKIE)
                
                # Get environment (default to development)
                environment = os.getenv("ENVIRONMENT", "development")
                is_production = environment == "production"
                
                # Set HTTP-only cookie with session token
                response.set_cookie(
                    key="session_token",
                    value=session_token,
                    httponly=True,
                    max_age=7 * 24 * 60 * 60,  # 7 days in seconds
                    secure=is_production,  # Only send over HTTPS in production
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
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
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


def get_current_user(
    session_token: str = Cookie(None, alias="session_token"),
    db: Session = Depends(get_db)
) -> User:
    """
    Authentication middleware dependency function.
    
    Validates session token from cookie and returns the authenticated user.
    
    **Validates: Requirements 13.3, 13.4**
    
    Args:
        session_token: Session token from HTTP-only cookie
        db: Database session dependency
    
    Returns:
        User: The authenticated user object
    
    Raises:
        HTTPException: 401 if token is missing, invalid, or expired
    """
    from backend.models import User, Session as SessionModel
    
    # Check if session token is provided
    if not session_token:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "MISSING_SESSION_TOKEN",
                    "message": "Authentication required"
                }
            }
        )
    
    # Query session from database
    session = db.query(SessionModel).filter(
        SessionModel.token == session_token
    ).first()
    
    # Check if session exists
    if not session:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "INVALID_SESSION_TOKEN",
                    "message": "Invalid session token"
                }
            }
        )
    
    # Check if session has expired
    if session.expires_at < datetime.now():
        # Delete expired session
        db.delete(session)
        db.commit()
        
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "SESSION_EXPIRED",
                    "message": "Session has expired, please log in again"
                }
            }
        )
    
    # Fetch and return the user
    user = db.query(User).filter(User.id == session.user_id).first()
    
    if not user:
        # Session exists but user doesn't (should not happen with proper FK constraints)
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "USER_NOT_FOUND",
                    "message": "User not found"
                }
            }
        )
    
    return user


@router.post("/logout")
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    session_token: str = Cookie(None, alias="session_token"),
    db: Session = Depends(get_db)
):
    """
    Log out the current user.
    
    Deletes the session token from the database and clears the session cookie.
    
    **Validates: Requirements 13.6**
    
    Args:
        response: FastAPI response object for setting cookies
        current_user: The authenticated user (from dependency)
        session_token: Session token from HTTP-only cookie
        db: Database session dependency
    
    Returns:
        dict: Success message
    """
    from backend.models import Session as SessionModel
    
    # Delete session from database
    session = db.query(SessionModel).filter(
        SessionModel.token == session_token
    ).first()
    
    if session:
        db.delete(session)
        db.commit()
    
    # Get environment (default to development)
    environment = os.getenv("ENVIRONMENT", "development")
    is_production = environment == "production"
    
    # Clear session cookie by setting it with expired max_age
    response.set_cookie(
        key="session_token",
        value="",
        httponly=True,
        max_age=0,  # Expire immediately
        secure=is_production,  # Only send over HTTPS in production
        samesite="lax"
    )
    
    return {
        "message": "Successfully logged out"
    }


# Limits for the genres a user can pick
MIN_FAVORITE_GENRES = 1
MAX_FAVORITE_GENRES = 5


class FavoriteGenresRequest(BaseModel):
    """Request model for setting a user's favorite genres."""
    genres: List[str] = Field(..., description="Genres the user likes (1-5)")


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Get the logged-in user's profile.
    
    Returns:
        dict: Serialized user, including favorite_genres ([] if not picked yet)
    """
    return serialize_user(current_user)


@router.put("/me/genres")
async def set_favorite_genres(
    genres_data: FavoriteGenresRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Set the logged-in user's favorite genres and rebuild their taste vector.
    
    Spotify no longer exposes genres or audio features, so the genres a user
    picks are what room recommendations are based on.
    
    Raises:
        HTTPException: 400 if the list is empty, too long, or has unknown genres
    """
    genres = list(dict.fromkeys(g.strip().lower() for g in genres_data.genres if g.strip()))
    
    unknown = [g for g in genres if g not in GENRE_VECTORS]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"Unknown genres: {', '.join(unknown)}",
                    "field": "genres"
                }
            }
        )
    
    if not MIN_FAVORITE_GENRES <= len(genres) <= MAX_FAVORITE_GENRES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"Pick between {MIN_FAVORITE_GENRES} and {MAX_FAVORITE_GENRES} genres",
                    "field": "genres"
                }
            }
        )
    
    current_user.favorite_genres = genres
    current_user.taste_vector = generate_room_taste_vector(genres)
    current_user.updated_at = datetime.now()
    db.commit()
    db.refresh(current_user)
    
    return serialize_user(current_user)
