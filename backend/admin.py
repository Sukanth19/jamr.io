"""Control panel API: staff manage people's roles and suspensions.

Mods and up can see everyone and suspend people below them. Admins and up can
also change roles of people below them (never to overseer).
"""

from datetime import datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import User
from backend.permissions import (
    FOREVER, assignable_roles, can_change_role, can_moderate_user, forbidden, is_staff, is_suspended,
)
from backend.serializers import utc_isoformat

router = APIRouter(prefix="/api/admin", tags=["Admin"])


class RoleChange(BaseModel):
    role: Literal["user", "mod", "admin"]


class SuspendRequest(BaseModel):
    # None suspends until staff lift it
    hours: Optional[int] = Field(default=None, ge=1, le=24 * 365)


def require_staff(current_user: User = Depends(get_current_user)) -> User:
    if not is_staff(current_user):
        raise forbidden("Only moderators and up can open the control panel.")
    return current_user


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "No such user."}})
    return user


def _user_row(actor: User, user: User) -> dict:
    """A user as staff see them, with what the viewer may do to them."""
    return {
        "id": user.id,
        "display_name": user.display_name,
        "username": user.username,
        "profile_image_url": user.profile_image_url,
        "role": user.role,
        "suspended": is_suspended(user),
        "suspended_until": utc_isoformat(user.suspended_until) if is_suspended(user) else None,
        "created_at": utc_isoformat(user.created_at),
        "can_moderate": can_moderate_user(actor, user),
        "assignable_roles": assignable_roles(actor) if can_change_role(actor, user, "user") else [],
    }


@router.get("/users")
async def list_users(actor: User = Depends(require_staff), db: Session = Depends(get_db)):
    """Everyone, staff first, then newest."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    rank = {"overseer": 0, "admin": 1, "mod": 2, "user": 3}
    users.sort(key=lambda u: rank[u.role])
    return {"users": [_user_row(actor, u) for u in users], "viewer_role": actor.role}


@router.put("/users/{user_id}/role")
async def change_role(
    user_id: int,
    body: RoleChange,
    actor: User = Depends(require_staff),
    db: Session = Depends(get_db)
):
    target = _get_user_or_404(db, user_id)
    if not can_change_role(actor, target, body.role):
        raise forbidden("You can only give roles below your own, to people below you.")
    
    target.role = body.role
    db.commit()
    return _user_row(actor, target)


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: int,
    body: SuspendRequest,
    actor: User = Depends(require_staff),
    db: Session = Depends(get_db)
):
    target = _get_user_or_404(db, user_id)
    if not can_moderate_user(actor, target):
        raise forbidden("You can only suspend people ranked below you.")
    
    target.suspended_until = datetime.now() + timedelta(hours=body.hours) if body.hours else FOREVER
    db.commit()
    return _user_row(actor, target)


@router.delete("/users/{user_id}/suspend")
async def unsuspend_user(
    user_id: int,
    actor: User = Depends(require_staff),
    db: Session = Depends(get_db)
):
    target = _get_user_or_404(db, user_id)
    if not can_moderate_user(actor, target):
        raise forbidden("You can only lift suspensions for people ranked below you.")
    
    target.suspended_until = None
    db.commit()
    return _user_row(actor, target)
