"""Roles and who may do what.

Roles, lowest to highest: user, mod, admin, overseer (the same hierarchy as
Eidothea). Staff (mod and up) can only act on people ranked below them. There
is one overseer, created with create_overseer.py, never through the website.

Room owners (whoever created a room) also moderate their own room: they can
delete any message in it and clear its Jam link, unless the author outranks
them on the site.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException

from backend.models import User, Room

ROLE_LEVEL = {"user": 0, "mod": 1, "admin": 2, "overseer": 3}

# A suspension with no end date, until staff lift it
FOREVER = datetime(9999, 12, 31)


def level(user: Optional[User]) -> int:
    return ROLE_LEVEL[user.role] if user else -1


def is_staff(user: Optional[User]) -> bool:
    return level(user) >= ROLE_LEVEL["mod"]


def outranks(actor: User, target_role: str) -> bool:
    return level(actor) > ROLE_LEVEL.get(target_role, 0)


def is_suspended(user: Optional[User]) -> bool:
    return bool(user and user.suspended_until and user.suspended_until > datetime.now())


def require_not_suspended(user: User) -> None:
    """Suspended people can read and browse, but not post."""
    if is_suspended(user):
        until = user.suspended_until
        when = "until staff lift it" if until >= FOREVER else f"until {until:%b %d, %H:%M}"
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "SUSPENDED", "message": f"You're suspended from posting {when}."}}
        )


def can_manage_room(actor: User, room: Room, owner_role: Optional[str]) -> bool:
    """Edit or delete a room: its owner, or staff who outrank the owner."""
    if room.owner_id == actor.id:
        return True
    return is_staff(actor) and outranks(actor, owner_role or "user")


def can_delete_message(actor: User, author_id: Optional[int], author_role: Optional[str], room: Room) -> bool:
    """
    Delete a message: its author, the room's owner, or staff, as long as
    neither the owner nor staff are outranked by the author.
    """
    if author_id == actor.id:
        return True
    author_role = author_role or "user"  # Messages from deleted accounts
    if room.owner_id == actor.id and level(actor) >= ROLE_LEVEL[author_role]:
        return True
    return is_staff(actor) and outranks(actor, author_role)


def can_moderate_user(actor: User, target: User) -> bool:
    """Suspend or unsuspend: staff, on people below them."""
    return is_staff(actor) and level(target) < level(actor)


def assignable_roles(actor: User) -> List[str]:
    """Roles an actor may hand out: admins and up, below their own rank. Never overseer."""
    if level(actor) < ROLE_LEVEL["admin"]:
        return []
    return [role for role, lvl in ROLE_LEVEL.items() if lvl < level(actor) and role != "overseer"]


def can_change_role(actor: User, target: User, new_role: str) -> bool:
    return (
        target.id != actor.id
        and level(target) < level(actor)
        and new_role in assignable_roles(actor)
    )


def forbidden(message: str) -> HTTPException:
    return HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": message}})
