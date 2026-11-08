"""Tests for favorite genres: /auth/me endpoints and genre-based room matching."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.auth import get_current_user
from backend.database import get_db
from backend.models import User
from backend.recommendation_engine import (
    genre_match_score,
    get_recommended_rooms,
    generate_room_taste_vector,
    _default_taste_vector,
)


@pytest.fixture
def user(db_session):
    """Create a user without favorite genres and log them in."""
    user = User(
        spotify_id="genre_test_user",
        display_name="Genre Tester",
        access_token_encrypted="encrypted_token",
        taste_vector=_default_taste_vector()
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user
    yield user
    app.dependency_overrides.clear()


client = TestClient(app)


def test_get_me_returns_empty_genres_before_picking(user):
    response = client.get("/auth/me")
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user.id
    assert data["favorite_genres"] == []
    assert "access_token_encrypted" not in data


def test_set_genres_updates_genres_and_taste_vector(user):
    response = client.put("/auth/me/genres", json={"genres": ["Hip-Hop", "r&b", "hip-hop"]})
    
    assert response.status_code == 200
    # Normalized to lowercase, duplicates removed, order kept
    assert response.json()["favorite_genres"] == ["hip-hop", "r&b"]
    assert user.taste_vector == generate_room_taste_vector(["hip-hop", "r&b"])


def test_set_genres_rejects_unknown_genres(user):
    response = client.put("/auth/me/genres", json={"genres": ["rock", "vaporwave"]})
    
    assert response.status_code == 400
    assert "vaporwave" in response.text


@pytest.mark.parametrize("genres", [[], ["rock", "pop", "jazz", "metal", "indie", "folk"]])
def test_set_genres_rejects_wrong_count(user, genres):
    response = client.put("/auth/me/genres", json={"genres": genres})
    
    assert response.status_code == 400
    assert user.favorite_genres is None


def test_genre_match_exact_related_and_unrelated():
    assert genre_match_score(["hip-hop"], ["hip-hop"]) == 1.0
    # Closer genres score higher, but never as high as an exact match
    classical = genre_match_score(["hip-hop"], ["classical"])
    rock = genre_match_score(["hip-hop"], ["rock"])
    rnb = genre_match_score(["hip-hop"], ["r&b"])
    assert classical < rock < rnb < 0.7


def test_genre_match_unknown_genres_score_zero():
    assert genre_match_score([], ["rock"]) == 0.0
    assert genre_match_score(["rock"], ["vaporwave"]) == 0.0


def test_recommended_rooms_use_genres_when_picked():
    rooms = [
        {"id": 1, "genre_tags": ["classical"], "taste_vector": generate_room_taste_vector(["classical"])},
        {"id": 2, "genre_tags": ["hip-hop", "r&b"], "taste_vector": generate_room_taste_vector(["hip-hop", "r&b"])},
        {"id": 3, "genre_tags": ["rock"], "taste_vector": generate_room_taste_vector(["rock"])},
    ]
    
    ranked = get_recommended_rooms(_default_taste_vector(), rooms, user_genres=["hip-hop", "r&b"])
    
    assert [r["id"] for r in ranked] == [2, 3, 1]
    assert ranked[0]["highly_recommended"] is True
    assert ranked[0]["matched_genres"] == ["hip-hop", "r&b"]
    assert not any(r["highly_recommended"] for r in ranked[1:])
