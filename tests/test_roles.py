"""Tests for roles: permission rules, moderation endpoints, the control panel API and suspensions."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from backend.main import app
from backend.auth import get_current_user
from backend.database import get_db
from backend.models import User, Room, Message, RoomMembership
from backend.permissions import (
    FOREVER, assignable_roles, can_change_role, can_delete_message, can_manage_room, can_moderate_user,
)
from backend.socketio_server import sio, active_connections


def make_user(db_session, name, role="user", suspended_until=None):
    user = User(spotify_id=f"roles_{name}", display_name=name, access_token_encrypted="x",
                taste_vector={}, role=role, suspended_until=suspended_until)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def make_room(db_session, owner):
    room = Room(name=f"{owner.display_name}'s room", owner_id=owner.id, genre_tags=["rock"], taste_vector={})
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return room


def make_message(db_session, room, author, content="hi"):
    message = Message(room_id=room.id, user_id=author.id, content=content)
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)
    return message


@pytest.fixture
def act_as(db_session):
    """Call the API as a given user."""
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    def _act_as(user):
        app.dependency_overrides[get_current_user] = lambda: user
        return client

    with patch('backend.socketio_server.sio.emit', new=AsyncMock()):
        yield _act_as
    app.dependency_overrides.clear()


# ---------- Permission rules ----------

def r(role, uid=1):
    return User(id=uid, role=role)


def test_only_admins_and_up_assign_roles_and_never_overseer():
    assert assignable_roles(r("user")) == []
    assert assignable_roles(r("mod")) == []
    assert assignable_roles(r("admin")) == ["user", "mod"]
    assert assignable_roles(r("overseer")) == ["user", "mod", "admin"]


def test_role_changes_need_to_outrank_the_target():
    assert can_change_role(r("admin", 1), r("user", 2), "mod")
    assert not can_change_role(r("admin", 1), r("admin", 2), "user")
    assert not can_change_role(r("admin", 1), r("user", 2), "admin")
    assert not can_change_role(r("overseer", 1), r("overseer", 1), "user")  # not on yourself


def test_staff_moderate_only_people_below_them():
    assert can_moderate_user(r("mod", 1), r("user", 2))
    assert not can_moderate_user(r("mod", 1), r("mod", 2))
    assert not can_moderate_user(r("user", 1), r("user", 2))


def test_message_deletion_rules():
    room = Room(id=1, owner_id=10)
    owner, author, mod = r("user", 10), r("user", 20), r("mod", 30)

    assert can_delete_message(author, 20, "user", room)          # own message
    assert can_delete_message(owner, 20, "user", room)           # room owner
    assert can_delete_message(mod, 20, "user", room)             # staff above the author
    assert not can_delete_message(r("user", 40), 20, "user", room)
    assert not can_delete_message(owner, 30, "mod", room)        # author outranks the owner
    assert not can_delete_message(mod, 50, "admin", room)


def test_room_management_rules():
    room = Room(id=1, owner_id=10)
    assert can_manage_room(r("user", 10), room, "user")
    assert can_manage_room(r("mod", 30), room, "user")
    assert not can_manage_room(r("mod", 30), room, "mod")
    assert not can_manage_room(r("user", 40), room, "user")


def test_only_one_overseer_allowed(db_session):
    make_user(db_session, "first_overseer", role="overseer")
    with pytest.raises(IntegrityError):
        make_user(db_session, "second_overseer", role="overseer")
    db_session.rollback()


# ---------- Moderation endpoints ----------

def test_room_owner_deletes_message_in_their_room(db_session, act_as):
    owner, author = make_user(db_session, "owner"), make_user(db_session, "author")
    room = make_room(db_session, owner)
    message = make_message(db_session, room, author)

    response = act_as(owner).delete(f"/api/rooms/{room.id}/messages/{message.id}")

    assert response.status_code == 204
    assert db_session.get(Message, message.id) is None


def test_user_cannot_delete_someone_elses_message(db_session, act_as):
    owner, author, other = make_user(db_session, "o"), make_user(db_session, "a"), make_user(db_session, "x")
    room = make_room(db_session, owner)
    message = make_message(db_session, room, author)

    response = act_as(other).delete(f"/api/rooms/{room.id}/messages/{message.id}")

    assert response.status_code == 403
    assert db_session.get(Message, message.id) is not None


def test_mod_deletes_room_of_a_user_but_not_of_an_admin(db_session, act_as):
    mod = make_user(db_session, "mod", role="mod")
    user_room = make_room(db_session, make_user(db_session, "plain"))
    admin_room = make_room(db_session, make_user(db_session, "boss", role="admin"))
    make_message(db_session, user_room, mod)

    assert act_as(mod).delete(f"/api/rooms/{admin_room.id}").status_code == 403
    assert act_as(mod).delete(f"/api/rooms/{user_room.id}").status_code == 204
    assert db_session.get(Room, user_room.id) is None


def test_owner_clears_jam_link(db_session, act_as):
    owner = make_user(db_session, "dj")
    room = make_room(db_session, owner)
    room.active_jam_link = "https://open.spotify.com/socialsession/abc"
    db_session.commit()

    assert act_as(make_user(db_session, "guest")).delete(f"/api/rooms/{room.id}/jam-link").status_code == 403
    assert act_as(owner).delete(f"/api/rooms/{room.id}/jam-link").status_code == 204
    db_session.refresh(room)
    assert room.active_jam_link is None


# ---------- Control panel API ----------

def test_control_panel_is_staff_only(db_session, act_as):
    assert act_as(make_user(db_session, "nobody")).get("/api/admin/users").status_code == 403

    response = act_as(make_user(db_session, "moddy", role="mod")).get("/api/admin/users")
    assert response.status_code == 200
    assert response.json()["viewer_role"] == "mod"


def test_admin_promotes_to_mod_but_not_admin(db_session, act_as):
    admin, user = make_user(db_session, "adm", role="admin"), make_user(db_session, "fan")
    client = act_as(admin)

    assert client.put(f"/api/admin/users/{user.id}/role", json={"role": "admin"}).status_code == 403
    response = client.put(f"/api/admin/users/{user.id}/role", json={"role": "mod"})
    assert response.status_code == 200
    assert response.json()["role"] == "mod"


def test_overseer_role_cannot_be_assigned_through_the_api(db_session, act_as):
    overseer, user = make_user(db_session, "boss_o", role="overseer"), make_user(db_session, "fan2")

    response = act_as(overseer).put(f"/api/admin/users/{user.id}/role", json={"role": "overseer"})

    assert response.status_code == 422


def test_mod_cannot_change_roles(db_session, act_as):
    mod, user = make_user(db_session, "m2", role="mod"), make_user(db_session, "u2")

    assert act_as(mod).put(f"/api/admin/users/{user.id}/role", json={"role": "mod"}).status_code == 403


def test_suspend_and_unsuspend(db_session, act_as):
    mod, user = make_user(db_session, "m3", role="mod"), make_user(db_session, "u3")
    client = act_as(mod)

    response = client.post(f"/api/admin/users/{user.id}/suspend", json={"hours": 24})
    assert response.status_code == 200
    assert response.json()["suspended"] is True

    forever = client.post(f"/api/admin/users/{user.id}/suspend", json={})
    assert forever.status_code == 200
    db_session.refresh(user)
    assert user.suspended_until == FOREVER

    assert client.delete(f"/api/admin/users/{user.id}/suspend").json()["suspended"] is False
    assert act_as(user).post(f"/api/admin/users/{mod.id}/suspend", json={}).status_code == 403


# ---------- Suspended users can't post ----------

def test_suspended_user_cannot_create_rooms(db_session, act_as):
    user = make_user(db_session, "muted", suspended_until=datetime.now() + timedelta(hours=1))

    response = act_as(user).post("/api/rooms", json={"name": "Nope", "genre_tags": ["rock"]})

    assert response.status_code == 403
    assert response.json()["detail"]["error"]["code"] == "SUSPENDED"


def test_expired_suspension_no_longer_applies(db_session, act_as):
    user = make_user(db_session, "was_muted", suspended_until=datetime.now() - timedelta(minutes=1))

    response = act_as(user).post("/api/rooms", json={"name": "Back again", "genre_tags": ["rock"]})

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_suspended_user_cannot_send_messages(db_session):
    user = make_user(db_session, "muted_chat", suspended_until=FOREVER)
    room = make_room(db_session, user)
    db_session.add(RoomMembership(user_id=user.id, room_id=room.id))
    db_session.commit()
    active_connections["sid_muted"] = user.id

    with patch('backend.database.get_session_local', return_value=lambda: db_session), \
         patch('backend.socketio_server.sio.emit', new=AsyncMock()):
        result = await sio.handlers['/']['send_message']("sid_muted", {"room_id": room.id, "content": "hello?"})

    assert "suspended" in result["error"]
    assert db_session.query(Message).filter(Message.room_id == room.id).count() == 0
