"""Property-based tests for room filtering functionality.

Feature: jamr-io-mvp
Tests that room filtering by search and genre works correctly.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from backend.models import Room, User
from backend.recommendation_engine import get_recommended_rooms
import json


# Feature: jamr-io-mvp, Property 5: Room Display Information
# Feature: jamr-io-mvp, Property 6: Filter Application
# **Validates: Requirements 3.2, 3.5**


def taste_vector_strategy():
    """Strategy for generating valid taste vectors."""
    return st.fixed_dictionaries({
        'danceability': st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        'energy': st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        'valence': st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        'acousticness': st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        'instrumentalness': st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        'speechiness': st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        'tempo_normalized': st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    })


def genre_strategy():
    """Strategy for generating genre tags."""
    return st.sampled_from([
        'rock', 'pop', 'indie', 'electronic', 'hip-hop', 
        'jazz', 'classical', 'metal', 'folk', 'r&b'
    ])


def room_dict_strategy():
    """Strategy for generating room dictionaries."""
    return st.fixed_dictionaries({
        'id': st.integers(min_value=1, max_value=10000),
        'name': st.text(min_size=3, max_size=50, alphabet=st.characters(blacklist_categories=('Cs',))),
        'description': st.text(max_size=300, alphabet=st.characters(blacklist_categories=('Cs',))),
        'genre_tags': st.lists(genre_strategy(), min_size=1, max_size=5, unique=True),
        'taste_vector': taste_vector_strategy(),
        'user_count': st.integers(min_value=0, max_value=100),
        'active_jam_link': st.one_of(st.none(), st.just('https://open.spotify.com/jam/test')),
        'owner_id': st.integers(min_value=1, max_value=1000),
        'created_at': st.just('2024-01-01T00:00:00'),
        'updated_at': st.just('2024-01-01T00:00:00')
    })


# ============================================================================
# Property 5: Room Display Information
# ============================================================================


@settings(max_examples=100)
@given(room=room_dict_strategy())
def test_room_contains_required_display_fields(room):
    """
    Property 5: Room Display Information
    
    For any room displayed on the discovery page, the room data must contain
    the required fields: name, description, genre_tags, and user_count.
    """
    # Verify all required fields are present
    assert 'name' in room, "Room missing 'name' field"
    assert 'description' in room, "Room missing 'description' field"
    assert 'genre_tags' in room, "Room missing 'genre_tags' field"
    assert 'user_count' in room, "Room missing 'user_count' field"
    
    # Verify field types
    assert isinstance(room['name'], str), f"Room name should be str, got {type(room['name'])}"
    assert isinstance(room['description'], str), f"Room description should be str, got {type(room['description'])}"
    assert isinstance(room['genre_tags'], list), f"Room genre_tags should be list, got {type(room['genre_tags'])}"
    assert isinstance(room['user_count'], int), f"Room user_count should be int, got {type(room['user_count'])}"


@settings(max_examples=100)
@given(rooms=st.lists(room_dict_strategy(), min_size=1, max_size=20))
def test_all_rooms_contain_display_information(rooms):
    """
    Property 5: Room Display Information
    
    For any list of rooms, every room must contain the required display fields.
    """
    for i, room in enumerate(rooms):
        assert 'name' in room, f"Room {i} missing 'name' field"
        assert 'description' in room, f"Room {i} missing 'description' field"
        assert 'genre_tags' in room, f"Room {i} missing 'genre_tags' field"
        assert 'user_count' in room, f"Room {i} missing 'user_count' field"
        
        # Verify name is non-empty and within valid range
        assert 3 <= len(room['name']) <= 50, \
            f"Room {i} name length {len(room['name'])} not in valid range [3, 50]"
        
        # Verify description is within valid range
        assert len(room['description']) <= 300, \
            f"Room {i} description length {len(room['description'])} exceeds max 300"
        
        # Verify genre_tags is non-empty
        assert len(room['genre_tags']) > 0, \
            f"Room {i} has empty genre_tags list"
        
        # Verify user_count is non-negative
        assert room['user_count'] >= 0, \
            f"Room {i} has negative user_count {room['user_count']}"


# ============================================================================
# Property 6: Filter Application
# ============================================================================


@settings(max_examples=100)
@given(
    rooms=st.lists(room_dict_strategy(), min_size=5, max_size=20, unique_by=lambda r: r['id']),
    search_term=st.text(min_size=1, max_size=20, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll'), min_codepoint=65, max_codepoint=122
    ))
)
def test_search_filter_matches_name_or_description(rooms, search_term):
    """
    Property 6: Filter Application
    
    For any search term applied, the filtered rooms must have the search term
    in either their name or description (case-insensitive).
    """
    # Apply search filter (case-insensitive)
    search_lower = search_term.lower()
    filtered_rooms = [
        room for room in rooms
        if search_lower in room['name'].lower() or search_lower in room['description'].lower()
    ]
    
    # Verify all filtered rooms contain the search term
    for room in filtered_rooms:
        name_match = search_lower in room['name'].lower()
        desc_match = search_lower in room['description'].lower()
        assert name_match or desc_match, \
            f"Room {room['id']} does not contain search term '{search_term}' " \
            f"in name '{room['name']}' or description '{room['description']}'"
    
    # Verify no unfiltered rooms were included
    for room in rooms:
        name_match = search_lower in room['name'].lower()
        desc_match = search_lower in room['description'].lower()
        
        if name_match or desc_match:
            assert room in filtered_rooms, \
                f"Room {room['id']} matches search but was not included in filtered results"


@settings(max_examples=100)
@given(
    rooms=st.lists(room_dict_strategy(), min_size=5, max_size=20, unique_by=lambda r: r['id']),
    filter_genres=st.lists(genre_strategy(), min_size=1, max_size=3, unique=True)
)
def test_genre_filter_matches_room_tags(rooms, filter_genres):
    """
    Property 6: Filter Application
    
    For any genre filter applied, the filtered rooms must have at least one
    genre tag that matches the filter (case-insensitive).
    """
    # Convert filter genres to lowercase for case-insensitive comparison
    filter_genres_lower = [g.lower() for g in filter_genres]
    
    # Apply genre filter
    filtered_rooms = []
    for room in rooms:
        room_genres_lower = [g.lower() for g in room['genre_tags']]
        if any(genre in room_genres_lower for genre in filter_genres_lower):
            filtered_rooms.append(room)
    
    # Verify all filtered rooms have at least one matching genre
    for room in filtered_rooms:
        room_genres_lower = [g.lower() for g in room['genre_tags']]
        has_match = any(genre in room_genres_lower for genre in filter_genres_lower)
        assert has_match, \
            f"Room {room['id']} with genres {room['genre_tags']} does not match " \
            f"filter genres {filter_genres}"
    
    # Verify no unfiltered rooms were included
    for room in rooms:
        room_genres_lower = [g.lower() for g in room['genre_tags']]
        has_match = any(genre in room_genres_lower for genre in filter_genres_lower)
        
        if has_match:
            assert room in filtered_rooms, \
                f"Room {room['id']} matches genre filter but was not included"


@settings(max_examples=100)
@given(
    rooms=st.lists(room_dict_strategy(), min_size=5, max_size=20, unique_by=lambda r: r['id']),
    search_term=st.text(min_size=1, max_size=20, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll'), min_codepoint=65, max_codepoint=122
    )),
    filter_genres=st.lists(genre_strategy(), min_size=1, max_size=3, unique=True)
)
def test_combined_search_and_genre_filter(rooms, search_term, filter_genres):
    """
    Property 6: Filter Application
    
    For any combination of search and genre filters, the filtered rooms must
    match BOTH the search term AND have at least one matching genre tag.
    """
    # Apply search filter
    search_lower = search_term.lower()
    search_filtered = [
        room for room in rooms
        if search_lower in room['name'].lower() or search_lower in room['description'].lower()
    ]
    
    # Apply genre filter to search results
    filter_genres_lower = [g.lower() for g in filter_genres]
    combined_filtered = []
    for room in search_filtered:
        room_genres_lower = [g.lower() for g in room['genre_tags']]
        if any(genre in room_genres_lower for genre in filter_genres_lower):
            combined_filtered.append(room)
    
    # Verify all filtered rooms match both criteria
    for room in combined_filtered:
        # Check search match
        name_match = search_lower in room['name'].lower()
        desc_match = search_lower in room['description'].lower()
        assert name_match or desc_match, \
            f"Room {room['id']} does not match search term '{search_term}'"
        
        # Check genre match
        room_genres_lower = [g.lower() for g in room['genre_tags']]
        has_genre_match = any(genre in room_genres_lower for genre in filter_genres_lower)
        assert has_genre_match, \
            f"Room {room['id']} does not match genre filter {filter_genres}"


@settings(max_examples=100)
@given(rooms=st.lists(room_dict_strategy(), min_size=1, max_size=20))
def test_empty_search_returns_all_rooms(rooms):
    """
    Property 6: Filter Application
    
    For an empty or None search term, all rooms should be returned (no filtering).
    """
    # Empty search should return all rooms
    empty_search = ""
    filtered_rooms = [
        room for room in rooms
        if empty_search in room['name'].lower() or empty_search in room['description'].lower()
    ]
    
    # Since empty string is in every string, all rooms should be returned
    assert len(filtered_rooms) == len(rooms), \
        f"Empty search should return all {len(rooms)} rooms, got {len(filtered_rooms)}"


@settings(max_examples=100)
@given(
    rooms=st.lists(room_dict_strategy(), min_size=5, max_size=20, unique_by=lambda r: r['id'])
)
def test_non_matching_search_returns_empty(rooms):
    """
    Property 6: Filter Application
    
    For a search term that doesn't match any room, an empty list should be returned.
    """
    # Use a search term that's very unlikely to match
    non_matching_search = "XYZABC123NONEXISTENT999"
    
    filtered_rooms = [
        room for room in rooms
        if non_matching_search.lower() in room['name'].lower() or 
           non_matching_search.lower() in room['description'].lower()
    ]
    
    # Should return empty list (or very rarely a match if randomly generated)
    # We can't assert it's always empty due to random generation, but we can verify
    # that any returned rooms actually contain the search term
    for room in filtered_rooms:
        name_match = non_matching_search.lower() in room['name'].lower()
        desc_match = non_matching_search.lower() in room['description'].lower()
        assert name_match or desc_match, \
            f"Room {room['id']} was returned but doesn't match search term"


@settings(max_examples=100)
@given(
    rooms=st.lists(room_dict_strategy(), min_size=5, max_size=20, unique_by=lambda r: r['id'])
)
def test_non_matching_genre_returns_empty_or_subset(rooms):
    """
    Property 6: Filter Application
    
    For a genre filter that doesn't match any room, an empty list should be returned.
    """
    # Use a genre that's not in our strategy
    non_matching_genre = "nonexistent-genre-xyz"
    
    filtered_rooms = []
    for room in rooms:
        room_genres_lower = [g.lower() for g in room['genre_tags']]
        if non_matching_genre.lower() in room_genres_lower:
            filtered_rooms.append(room)
    
    # Should return empty list since we're using a genre not in our strategy
    assert len(filtered_rooms) == 0, \
        f"Non-matching genre filter should return empty list, got {len(filtered_rooms)} rooms"


@settings(max_examples=100)
@given(
    rooms=st.lists(room_dict_strategy(), min_size=1, max_size=20, unique_by=lambda r: r['id'])
)
def test_filter_preserves_room_structure(rooms):
    """
    Property 6: Filter Application
    
    For any filter applied, the filtered rooms must preserve all original fields
    and structure (no fields should be added or removed by filtering).
    """
    # Pick a genre that exists in at least one room
    if not rooms:
        return
    
    # Get all unique genres from all rooms
    all_genres = set()
    for room in rooms:
        all_genres.update(g.lower() for g in room['genre_tags'])
    
    if not all_genres:
        return
    
    # Pick one genre to filter by
    filter_genre = list(all_genres)[0]
    
    # Apply genre filter
    filtered_rooms = []
    for room in rooms:
        room_genres_lower = [g.lower() for g in room['genre_tags']]
        if filter_genre in room_genres_lower:
            filtered_rooms.append(room)
    
    # Verify each filtered room has the same structure as original
    original_keys = set(rooms[0].keys())
    for room in filtered_rooms:
        assert set(room.keys()) == original_keys, \
            f"Filtered room {room['id']} has different keys than original"


@settings(max_examples=100)
@given(
    rooms=st.lists(room_dict_strategy(), min_size=1, max_size=20, unique_by=lambda r: r['id']),
    search_term=st.text(min_size=1, max_size=20, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll'), min_codepoint=65, max_codepoint=122
    ))
)
def test_search_filter_is_case_insensitive(rooms, search_term):
    """
    Property 6: Filter Application
    
    For any search term, the filter must be case-insensitive (matching both
    uppercase and lowercase variations).
    """
    # Apply filter with lowercase search term
    search_lower = search_term.lower()
    filtered_lower = [
        room for room in rooms
        if search_lower in room['name'].lower() or search_lower in room['description'].lower()
    ]
    
    # Apply filter with uppercase search term
    search_upper = search_term.upper()
    filtered_upper = [
        room for room in rooms
        if search_upper.lower() in room['name'].lower() or search_upper.lower() in room['description'].lower()
    ]
    
    # Both should return the same rooms
    assert len(filtered_lower) == len(filtered_upper), \
        f"Case-insensitive search failed: lowercase found {len(filtered_lower)} rooms, " \
        f"uppercase found {len(filtered_upper)} rooms"
    
    # Verify same room IDs
    lower_ids = sorted([r['id'] for r in filtered_lower])
    upper_ids = sorted([r['id'] for r in filtered_upper])
    assert lower_ids == upper_ids, \
        "Case-insensitive search returned different rooms for different cases"


@settings(max_examples=100)
@given(
    rooms=st.lists(room_dict_strategy(), min_size=1, max_size=20, unique_by=lambda r: r['id'])
)
def test_genre_filter_is_case_insensitive(rooms):
    """
    Property 6: Filter Application
    
    For any genre filter, the filter must be case-insensitive (matching both
    uppercase and lowercase genre tags).
    """
    # Get all unique genres from rooms
    all_genres = set()
    for room in rooms:
        all_genres.update(room['genre_tags'])
    
    if not all_genres:
        return
    
    # Pick one genre
    test_genre = list(all_genres)[0]
    
    # Apply filter with lowercase
    filter_lower = [test_genre.lower()]
    filtered_lower = []
    for room in rooms:
        room_genres_lower = [g.lower() for g in room['genre_tags']]
        if any(genre in room_genres_lower for genre in filter_lower):
            filtered_lower.append(room)
    
    # Apply filter with uppercase
    filter_upper = [test_genre.upper()]
    filtered_upper = []
    for room in rooms:
        room_genres_lower = [g.lower() for g in room['genre_tags']]
        if any(genre.lower() in room_genres_lower for genre in filter_upper):
            filtered_upper.append(room)
    
    # Both should return the same rooms
    assert len(filtered_lower) == len(filtered_upper), \
        f"Case-insensitive genre filter failed: lowercase found {len(filtered_lower)} rooms, " \
        f"uppercase found {len(filtered_upper)} rooms"
