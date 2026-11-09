"""Password hashing and login sessions, shared by password and Spotify login."""

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Response
from sqlalchemy.orm import Session

from backend.models import User, Session as SessionModel

SESSION_COOKIE = "session_token"
SESSION_DAYS = 7


def hash_password(password: str) -> str:
    """scrypt with a random salt (same parameters as Eidothea)."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: Optional[str]) -> bool:
    try:
        scheme, salt_hex, digest_hex = (stored or "").split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
    return hmac.compare_digest(digest.hex(), digest_hex)


def start_session(db: Session, user: User, response: Response) -> None:
    """Create a login session for the user and set the session cookie on the response."""
    token = secrets.token_urlsafe(32)
    db.add(SessionModel(
        user_id=user.id,
        token=token,
        expires_at=datetime.now() + timedelta(days=SESSION_DAYS)
    ))
    db.commit()

    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        secure=os.getenv("ENVIRONMENT", "development") == "production",  # HTTPS only in production
        samesite="lax"  # CSRF protection
    )


def user_for_session(db: Session, token: Optional[str]) -> Optional[User]:
    """The user a session cookie belongs to, or None if it's missing or expired."""
    if not token:
        return None
    session = db.query(SessionModel).filter(
        SessionModel.token == token,
        SessionModel.expires_at > datetime.now()
    ).first()
    return db.get(User, session.user_id) if session else None
