"""jamr.io's own accounts: sign up and log in with a username and password.

Spotify is optional: people can connect it from their account page to see
artists they share with others (Spotify only allows a few test users, so
login can't depend on it).
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.auth import get_current_user, _default_taste_vector
from backend.database import get_db
from backend.models import User
from backend.rate_limiter import RateLimiter
from backend.serializers import serialize_user
from backend.sessions import hash_password, start_session, verify_password

router = APIRouter(prefix="/auth", tags=["Accounts"])

USERNAME_PATTERN = r"^[A-Za-z0-9_-]+$"

# Per-IP limits (in memory: reset on restart)
signup_limiter = RateLimiter(max_requests=5, window_seconds=3600)
login_limiter = RateLimiter(max_requests=10, window_seconds=600)


class SignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=24, pattern=USERNAME_PATTERN)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: Optional[str] = Field(default=None, max_length=50)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=24)
    password: str = Field(..., min_length=1, max_length=128)


class ProfileUpdate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=50)


class PasswordUpdate(BaseModel):
    # Required when the account has no username yet (e.g. made with Spotify)
    username: Optional[str] = Field(default=None, min_length=3, max_length=24, pattern=USERNAME_PATTERN)
    current_password: Optional[str] = Field(default=None, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


def _error(status: int, code: str, message: str, field: Optional[str] = None) -> HTTPException:
    error = {"code": code, "message": message}
    if field:
        error["field"] = field
    return HTTPException(status_code=status, detail={"error": error})


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _username_taken(db: Session, username: str, exclude_id: Optional[int] = None) -> bool:
    query = db.query(User.id).filter(func.lower(User.username) == username.lower())
    if exclude_id is not None:
        query = query.filter(User.id != exclude_id)
    return query.first() is not None


@router.post("/signup", status_code=201)
async def signup(body: SignupRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Create an account and log in."""
    if not signup_limiter.check_rate_limit(_client_ip(request)):
        raise _error(429, "RATE_LIMIT_EXCEEDED", "Too many sign-ups from here. Try again in an hour.")

    if _username_taken(db, body.username):
        raise _error(409, "USERNAME_TAKEN", "That username is taken.", "username")

    display_name = (body.display_name or "").strip() or body.username
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=display_name,
        taste_vector=_default_taste_vector()
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    start_session(db, user, response)
    return serialize_user(user)


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Log in with a username and password."""
    if not login_limiter.check_rate_limit(_client_ip(request)):
        raise _error(429, "RATE_LIMIT_EXCEEDED", "Too many tries. Wait a few minutes, then try again.")

    user = db.query(User).filter(func.lower(User.username) == body.username.strip().lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise _error(401, "INVALID_CREDENTIALS", "Wrong username or password.")

    start_session(db, user, response)
    return serialize_user(user)


@router.patch("/me")
async def update_profile(
    body: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change the name shown to others."""
    display_name = body.display_name.strip()
    if not display_name:
        raise _error(400, "VALIDATION_ERROR", "Display name can't be empty.", "display_name")

    current_user.display_name = display_name
    db.commit()
    return serialize_user(current_user)


@router.put("/me/password")
async def set_password(
    body: PasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Set or change the account's password. Accounts made with Spotify pick a
    username the first time, so they can log in without Spotify.
    """
    if current_user.password_hash:
        if not verify_password(body.current_password or "", current_user.password_hash):
            raise _error(400, "INVALID_CREDENTIALS", "Your current password is wrong.", "current_password")

    if not current_user.username:
        if not body.username:
            raise _error(400, "VALIDATION_ERROR", "Pick a username to log in with.", "username")
        if _username_taken(db, body.username, exclude_id=current_user.id):
            raise _error(409, "USERNAME_TAKEN", "That username is taken.", "username")
        current_user.username = body.username

    current_user.password_hash = hash_password(body.new_password)
    db.commit()
    return serialize_user(current_user)


@router.delete("/me/spotify")
async def disconnect_spotify(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Forget the connected Spotify account (needs a password, so the account stays reachable)."""
    if not current_user.password_hash:
        raise _error(400, "PASSWORD_REQUIRED", "Set a password first, or you won't be able to log in.")

    current_user.spotify_id = None
    current_user.access_token_encrypted = None
    current_user.refresh_token_encrypted = None
    current_user.token_expires_at = None
    current_user.top_artists = None
    db.commit()
    return serialize_user(current_user)
