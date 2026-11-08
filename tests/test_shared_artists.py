"""Tests for shared-artist matching between a user and the people in rooms."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.auth import get_current_user, _summarize_artist
from backend.database import get_db
from backend.models import User, Room, Message, RoomMembership
from backend.recommendation_engine import find_shared_artists, generate_room_taste_vector


def artists(*names):
    """Build top-artist entries using the name as the Spotify ID."""
    return [{"id": name.lower(), "name": name, "image": None} for name in names]


def test_find_shared_artists_keeps_user_ranking_order():
    mine = artists("SZA", "Drake", "Frank Ocean", "Kendrick Lamar")
    others = [artists("Kendrick Lamar", "Adele"), artists("Drake"), None]
    
    assert find_shared_artists(mine, others) == ["Drake", "Kendrick Lamar"]


def test_find_shared_artists_handles_missing_data():
    assert find_shared_artists(None, [artists("Drake")]) == []
    assert find_shared_artists(artists("Drake"), []) == []


def test_summarize_artist_keeps_id_name_and_smallest_image():
    artist = {
        "id": "abc", "name": "SZA", "type": "artist",
        "images": [{"url": "https://img/640"}, {"url": "https://img/160"}]
    }
    
    assert _summarize_artist(artist) == {"id": "abc", "name": "SZA", "image": "https://img/160"}
    assert _summarize_artist({"id": "x", "name": "No Pics", "images": []})["image"] is None


def make_user(db_session, spotify_id, top_artists):
    user = User(
        spotify_id=spotify_id,
        display_name=spotify_id,
        access_token_encrypted="encrypted_token",
        taste_vector=generate_room_taste_vector(["hip-hop"]),
        favorite_genres=["hip-hop"],
        top_artists=top_artists
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def make_room(db_session, name, owner_id):
    room = Room(
        name=name,
        owner_id=owner_id,
        genre_tags=["hip-hop"],
        taste_vector=generate_room_taste_vector(["hip-hop"]),
        user_count=0
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return room


def test_rooms_include_shared_artists_and_rank_by_them(db_session):
    me = make_user(db_session, "shared_me", artists("SZA", "Drake", "Frank Ocean"))
    owner = make_user(db_session, "shared_owner", artists("Drake"))
    member = make_user(db_session, "shared_member", artists("SZA", "Adele"))
    chatter = make_user(db_session, "shared_chatter", artists("Frank Ocean"))
    stranger = make_user(db_session, "shared_stranger", artists("Adele"))
    
    # Same genres, so rooms differ only in how many artists are shared
    busy = make_room(db_session, "Busy Room", owner.id)
    db_session.add(RoomMembership(user_id=member.id, room_id=busy.id))
    db_session.add(Message(room_id=busy.id, user_id=chatter.id, content="hi"))
    quiet = make_room(db_session, "Quiet Room", stranger.id)
    db_session.commit()
    
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: me
    try:
        response = TestClient(app).get("/api/rooms")
    finally:
        app.dependency_overrides.clear()
    
    assert response.status_code == 200
    rooms = {r["id"]: r for r in response.json()["rooms"]}
    
    # Owner, member and message author all count, in my ranking order
    assert rooms[busy.id]["shared_artists"] == ["SZA", "Drake", "Frank Ocean"]
    assert rooms[quiet.id]["shared_artists"] == []
    
    ids = [r["id"] for r in response.json()["rooms"]]
    assert ids.index(busy.id) < ids.index(quiet.id)
