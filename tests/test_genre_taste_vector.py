"""Tests for building taste vectors from Spotify artist genres."""

from backend.recommendation_engine import (
    GENRE_VECTORS,
    map_spotify_genres,
    generate_taste_vector_from_genres,
    generate_room_taste_vector,
    _default_taste_vector,
)


def test_maps_compound_genres_to_base_genres():
    assert map_spotify_genres(["indie rock"]) == ["indie", "rock"]


def test_maps_aliases():
    assert map_spotify_genres(["uk hip hop", "edm", "rnb"]) == ["hip-hop", "electronic", "r&b"]


def test_unknown_genres_are_ignored():
    assert map_spotify_genres(["vaporwave", "chillwave"]) == []


def test_vector_matches_room_vector_for_same_genres():
    assert generate_taste_vector_from_genres(["jazz", "classical"]) == generate_room_taste_vector(["jazz", "classical"])


def test_frequent_genres_weigh_more():
    vector = generate_taste_vector_from_genres(["metal", "metal", "metal", "folk"])
    assert vector["energy"] > (GENRE_VECTORS["metal"]["energy"] + GENRE_VECTORS["folk"]["energy"]) / 2


def test_no_genres_returns_default():
    assert generate_taste_vector_from_genres([]) == _default_taste_vector()
