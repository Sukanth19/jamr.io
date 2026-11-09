"""Tests for username/password accounts and optional Spotify connection."""

import pytest
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet

from backend.main import app
from backend.database import get_db
from backend.models import User, Session as SessionModel
from backend.sessions import hash_password, verify_password


@pytest.fixture
def client(db_session, monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def signup(client, username="newbie", password="correct horse", **extra):
    return client.post("/auth/signup", json={"username": username, "password": password, **extra})


# ---------- Passwords ----------

def test_password_hashes_are_salted_and_verify():
    first, second = hash_password("hunter22"), hash_password("hunter22")
    
    assert first != second
    assert first.startswith("scrypt$")
    assert verify_password("hunter22", first)
    assert not verify_password("wrong", first)
    assert not verify_password("hunter22", None)


# ---------- Sign up and log in ----------

def test_signup_creates_account_and_logs_in(client, db_session):
    response = signup(client, display_name="New Person")
    
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newbie"
    assert data["display_name"] == "New Person"
    assert data["has_password"] is True
    assert data["spotify_connected"] is False
    assert "password_hash" not in data
    assert "session_token" in response.cookies
    
    # The new session works
    assert client.get("/auth/me").json()["username"] == "newbie"


def test_signup_uses_username_as_default_display_name(client):
    assert signup(client, username="quiet_one").json()["display_name"] == "quiet_one"


def test_usernames_are_unique_regardless_of_case(client):
    assert signup(client, username="DJ_Night").status_code == 201
    client.cookies.clear()
    
    response = signup(client, username="dj_night")
    
    assert response.status_code == 409
    assert response.json()["detail"]["error"]["code"] == "USERNAME_TAKEN"


@pytest.mark.parametrize("username, password", [
    ("ab", "longenough"),            # username too short
    ("has space", "longenough"),     # invalid character
    ("fine_name", "short"),          # password too short
])
def test_signup_validation(client, username, password):
    assert signup(client, username=username, password=password).status_code == 422


def test_login_with_any_case_username(client):
    signup(client, username="MixedCase")
    client.cookies.clear()
    
    response = client.post("/auth/login", json={"username": "mixedcase", "password": "correct horse"})
    
    assert response.status_code == 200
    assert "session_token" in response.cookies


def test_login_rejects_wrong_password_and_unknown_user(client):
    signup(client)
    client.cookies.clear()
    
    for creds in ({"username": "newbie", "password": "nope nope"}, {"username": "ghost", "password": "whatever1"}):
        response = client.post("/auth/login", json=creds)
        assert response.status_code == 401
        assert response.json()["detail"]["error"]["message"] == "Wrong username or password."


def test_login_is_rate_limited(client):
    for _ in range(10):
        client.post("/auth/login", json={"username": "ghost", "password": "guess"})
    
    response = client.post("/auth/login", json={"username": "ghost", "password": "guess"})
    
    assert response.status_code == 429


# ---------- Account settings ----------

def test_update_display_name(client):
    signup(client)
    
    response = client.patch("/auth/me", json={"display_name": "  Night Owl  "})
    
    assert response.status_code == 200
    assert response.json()["display_name"] == "Night Owl"


def test_change_password_needs_current_password(client):
    signup(client)
    
    wrong = client.put("/auth/me/password", json={"current_password": "nope", "new_password": "brand new pass"})
    assert wrong.status_code == 400
    
    ok = client.put("/auth/me/password", json={"current_password": "correct horse", "new_password": "brand new pass"})
    assert ok.status_code == 200
    
    client.cookies.clear()
    assert client.post("/auth/login", json={"username": "newbie", "password": "brand new pass"}).status_code == 200


def spotify_only_user(db_session, client):
    """A Spotify-made account (no username/password), logged in."""
    user = User(spotify_id="spotify_only", display_name="Spotty", access_token_encrypted="x", taste_vector={})
    db_session.add(user)
    db_session.commit()
    db_session.add(SessionModel(user_id=user.id, token="spotty-session",
                                expires_at=__import__("datetime").datetime(2999, 1, 1)))
    db_session.commit()
    client.cookies.set("session_token", "spotty-session")
    return user


def test_spotify_account_sets_username_and_password(client, db_session):
    user = spotify_only_user(db_session, client)
    
    missing = client.put("/auth/me/password", json={"new_password": "now i have one"})
    assert missing.status_code == 400
    
    response = client.put("/auth/me/password", json={"username": "spotty", "new_password": "now i have one"})
    assert response.status_code == 200
    assert response.json()["username"] == "spotty"
    
    client.cookies.clear()
    assert client.post("/auth/login", json={"username": "spotty", "password": "now i have one"}).status_code == 200


def test_disconnect_spotify_needs_a_password(client, db_session):
    user = spotify_only_user(db_session, client)
    
    assert client.delete("/auth/me/spotify").status_code == 400
    
    client.put("/auth/me/password", json={"username": "spotty2", "new_password": "now i have one"})
    response = client.delete("/auth/me/spotify")
    
    assert response.status_code == 200
    assert response.json()["spotify_connected"] is False
    db_session.refresh(user)
    assert user.spotify_id is None and user.access_token_encrypted is None and user.top_artists is None


# ---------- Connecting Spotify through the OAuth callback ----------

class FakeSpotify:
    """Stands in for httpx.AsyncClient talking to Spotify."""
    
    def __init__(self, spotify_id):
        self.spotify_id = spotify_id
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        return False
    
    async def post(self, url, data=None):
        return FakeResponse(200, {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600})
    
    async def get(self, url, headers=None):
        if url.endswith("/v1/me"):
            return FakeResponse(200, {"id": self.spotify_id, "display_name": "Spotify Name", "images": []})
        if "/me/top/artists" in url:
            return FakeResponse(200, {"items": [{"id": "sza", "name": "SZA", "images": []}]})
        if "/me/top/tracks" in url:
            return FakeResponse(200, {"items": []})
        return FakeResponse(403, {})


class FakeResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data
    
    def json(self):
        return self._data


@pytest.fixture
def spotify(monkeypatch, db_session):
    """Route the callback's Spotify calls and DB session to fakes; returns a setter for the Spotify ID."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "secret")
    monkeypatch.setenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/auth/callback")
    monkeypatch.setattr("backend.auth.get_db", lambda: iter([db_session]))
    db_session.close = lambda: None  # the callback closes its session
    
    def use(spotify_id):
        monkeypatch.setattr("backend.auth.httpx.AsyncClient", lambda: FakeSpotify(spotify_id))
    return use


def callback(client):
    client.cookies.set("oauth_state", "st")
    return client.get("/auth/callback?code=c&state=st", follow_redirects=False)


def test_logged_in_user_connects_spotify(client, db_session, spotify):
    signup(client, username="linker", display_name="Linker")
    spotify("spotify_linker")
    
    response = callback(client)
    
    assert response.status_code == 302
    assert response.headers["location"] == "/account?spotify=connected"
    user = db_session.query(User).filter(User.username == "linker").one()
    assert user.spotify_id == "spotify_linker"
    assert user.display_name == "Linker"  # keeps the name they chose
    assert user.top_artists == [{"id": "sza", "name": "SZA", "image": None}]
    assert db_session.query(User).count() == 1  # no second account


def test_connecting_a_spotify_account_used_by_someone_else_is_refused(client, db_session, spotify):
    db_session.add(User(spotify_id="already_used", display_name="Other", access_token_encrypted="x", taste_vector={}))
    db_session.commit()
    signup(client, username="latecomer")
    spotify("already_used")
    
    response = callback(client)
    
    assert response.headers["location"] == "/account?spotify=taken"
    assert db_session.query(User).filter(User.username == "latecomer").one().spotify_id is None


def test_spotify_login_without_session_still_creates_account(client, db_session, spotify):
    spotify("brand_new_spotify")
    
    response = callback(client)
    
    assert response.headers["location"] == "/discover"
    assert "session_token" in response.cookies
    assert db_session.query(User).filter(User.spotify_id == "brand_new_spotify").one().display_name == "Spotify Name"
