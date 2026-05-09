"""Property-based tests for room recommendation ranking.

Feature: jamr-io-mvp
Tests that room recommendations are correctly ranked and marked.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from backend.recommendation_engine import get_recommended_rooms, cosine_similarity


# Feature: jamr-io-mvp, Property 7: Recommendation Display
# Feature: jamr-io-mvp, Property 9: High Recommendation Badge
# **Validates: Requirements 3.6, 4.3, 4.4, 4.5**


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


def room_strategy():
    """Strategy for generating room dictionaries."""
    return st.fixed_dictionaries({
        'id': st.integers(min_value=1, max_value=10000),
        'name': st.text(min_size=3, max_size=50),
        'description': st.text(max_size=300),
        'taste_vector': taste_vector_strategy(),
        'user_count': st.integers(min_value=0, max_value=100)
    })


@settings(max_examples=100)
@given(
    user_taste_vector=taste_vector_strategy(),
    rooms=st.lists(room_strategy(), min_size=1, max_size=20)
)
def test_recommended_rooms_sorted_by_similarity_descending(user_taste_vector, rooms):
    """
    Property 7: Recommendation Display
    
    For any authenticated user on the room discovery page, the page must display
    rooms sorted by similarity score in descending order.
    """
    # Get recommended rooms
    recommended_rooms = get_recommended_rooms(user_taste_vector, rooms)
    
    # Verify all rooms are returned
    assert len(recommended_rooms) == len(rooms), \
        f"Expected {len(rooms)} rooms, got {len(recommended_rooms)}"
    
    # Verify rooms are sorted by similarity score descending
    for i in range(len(recommended_rooms) - 1):
        current_score = recommended_rooms[i]['similarity_score']
        next_score = recommended_rooms[i + 1]['similarity_score']
        assert current_score >= next_score, \
            f"Rooms not sorted by similarity: room {i} has score {current_score}, " \
            f"room {i+1} has score {next_score}"


@settings(max_examples=100)
@given(
    user_taste_vector=taste_vector_strategy(),
    rooms=st.lists(room_strategy(), min_size=1, max_size=20)
)
def test_recommended_rooms_have_similarity_score(user_taste_vector, rooms):
    """
    Property 7: Recommendation Display
    
    For any recommended room, the room must have a similarity_score field
    containing the cosine similarity between user and room taste vectors.
    """
    # Get recommended rooms
    recommended_rooms = get_recommended_rooms(user_taste_vector, rooms)
    
    # Verify each room has similarity_score field
    for room in recommended_rooms:
        assert 'similarity_score' in room, \
            f"Room {room.get('id')} missing similarity_score field"
        
        # Verify similarity score is in valid range [0, 1]
        score = room['similarity_score']
        assert 0.0 <= score <= 1.0, \
            f"Room {room.get('id')} has invalid similarity score {score}"
        
        # Verify similarity score matches cosine similarity calculation
        expected_score = cosine_similarity(user_taste_vector, room['taste_vector'])
        assert abs(score - expected_score) < 1e-9, \
            f"Room {room.get('id')} similarity score {score} does not match " \
            f"expected {expected_score}"


@settings(max_examples=100)
@given(
    user_taste_vector=taste_vector_strategy(),
    rooms=st.lists(room_strategy(), min_size=1, max_size=20)
)
def test_high_recommendation_badge_above_threshold(user_taste_vector, rooms):
    """
    Property 9: High Recommendation Badge
    
    For any room with a similarity score greater than 0.7, the room card must
    display a "Highly Recommended" badge or indicator.
    """
    # Get recommended rooms
    recommended_rooms = get_recommended_rooms(user_taste_vector, rooms)
    
    # Verify each room has highly_recommended field
    for room in recommended_rooms:
        assert 'highly_recommended' in room, \
            f"Room {room.get('id')} missing highly_recommended field"
        
        score = room['similarity_score']
        is_highly_recommended = room['highly_recommended']
        
        # Verify highly_recommended is True if and only if score > 0.7
        if score > 0.7:
            assert is_highly_recommended is True, \
                f"Room {room.get('id')} with score {score} should be highly recommended"
        else:
            assert is_highly_recommended is False, \
                f"Room {room.get('id')} with score {score} should not be highly recommended"


@settings(max_examples=100)
@given(
    user_taste_vector=taste_vector_strategy(),
    rooms=st.lists(room_strategy(), min_size=1, max_size=20, unique_by=lambda r: r['id'])
)
def test_recommended_rooms_preserve_original_fields(user_taste_vector, rooms):
    """
    Property 7: Recommendation Display
    
    For any recommended room, all original room fields must be preserved
    (id, name, description, taste_vector, user_count, etc.).
    """
    # Get recommended rooms
    recommended_rooms = get_recommended_rooms(user_taste_vector, rooms)
    
    # Create a mapping of original rooms by id for easy lookup
    original_rooms_by_id = {room['id']: room for room in rooms}
    
    # Verify each recommended room preserves original fields
    for rec_room in recommended_rooms:
        room_id = rec_room['id']
        original_room = original_rooms_by_id[room_id]
        
        # Check all original fields are preserved
        for key, value in original_room.items():
            assert key in rec_room, \
                f"Room {room_id} missing original field '{key}'"
            assert rec_room[key] == value, \
                f"Room {room_id} field '{key}' changed from {value} to {rec_room[key]}"


@settings(max_examples=100)
@given(
    user_taste_vector=taste_vector_strategy(),
    room=room_strategy()
)
def test_single_room_recommendation(user_taste_vector, room):
    """
    Property 7: Recommendation Display (Edge Case - Single Room)
    
    For a single room, the recommendation function should return a list with
    one room containing the correct similarity score and badge.
    """
    # Get recommended rooms
    recommended_rooms = get_recommended_rooms(user_taste_vector, [room])
    
    # Verify exactly one room returned
    assert len(recommended_rooms) == 1, \
        f"Expected 1 room, got {len(recommended_rooms)}"
    
    # Verify the room has correct fields
    rec_room = recommended_rooms[0]
    assert 'similarity_score' in rec_room
    assert 'highly_recommended' in rec_room
    assert rec_room['id'] == room['id']


def test_empty_rooms_list():
    """
    Property 7: Recommendation Display (Edge Case - Empty List)
    
    For an empty rooms list, the recommendation function should return an empty list.
    """
    user_taste_vector = {
        'danceability': 0.5,
        'energy': 0.6,
        'valence': 0.7,
        'acousticness': 0.3,
        'instrumentalness': 0.1,
        'speechiness': 0.05,
        'tempo_normalized': 0.55
    }
    
    # Get recommended rooms with empty list
    recommended_rooms = get_recommended_rooms(user_taste_vector, [])
    
    # Verify empty list returned
    assert recommended_rooms == [], \
        f"Expected empty list, got {recommended_rooms}"


@settings(max_examples=100)
@given(
    user_taste_vector=taste_vector_strategy(),
    rooms=st.lists(room_strategy(), min_size=2, max_size=20)
)
def test_recommended_rooms_stable_sort(user_taste_vector, rooms):
    """
    Property 7: Recommendation Display (Stability)
    
    For rooms with equal similarity scores, the relative order should be stable
    (rooms that appear earlier in the input should appear earlier in the output).
    """
    # Get recommended rooms twice
    recommended_rooms_1 = get_recommended_rooms(user_taste_vector, rooms)
    recommended_rooms_2 = get_recommended_rooms(user_taste_vector, rooms)
    
    # Verify both calls produce the same order
    for i, (room1, room2) in enumerate(zip(recommended_rooms_1, recommended_rooms_2)):
        assert room1['id'] == room2['id'], \
            f"Inconsistent ordering at position {i}: {room1['id']} vs {room2['id']}"


def test_high_recommendation_threshold_boundary():
    """
    Property 9: High Recommendation Badge (Boundary Test)
    
    Test the exact boundary of the high recommendation threshold (0.7).
    """
    # Create user taste vector
    user_taste_vector = {
        'danceability': 1.0,
        'energy': 1.0,
        'valence': 1.0,
        'acousticness': 0.0,
        'instrumentalness': 0.0,
        'speechiness': 0.0,
        'tempo_normalized': 0.0
    }
    
    # Create rooms with specific similarity scores
    # Room 1: Identical to user (similarity = 1.0, should be highly recommended)
    room_high = {
        'id': 1,
        'name': 'High Match Room',
        'description': 'Perfect match',
        'taste_vector': user_taste_vector.copy(),
        'user_count': 5
    }
    
    # Room 2: Orthogonal to user (similarity = 0.0, should not be highly recommended)
    room_low = {
        'id': 2,
        'name': 'Low Match Room',
        'description': 'Poor match',
        'taste_vector': {
            'danceability': 0.0,
            'energy': 0.0,
            'valence': 0.0,
            'acousticness': 1.0,
            'instrumentalness': 1.0,
            'speechiness': 1.0,
            'tempo_normalized': 1.0
        },
        'user_count': 3
    }
    
    # Get recommended rooms
    recommended_rooms = get_recommended_rooms(user_taste_vector, [room_high, room_low])
    
    # Find the rooms in the results
    high_result = next(r for r in recommended_rooms if r['id'] == 1)
    low_result = next(r for r in recommended_rooms if r['id'] == 2)
    
    # Verify high similarity room is highly recommended
    assert high_result['similarity_score'] > 0.7, \
        f"High match room should have score > 0.7, got {high_result['similarity_score']}"
    assert high_result['highly_recommended'] is True, \
        "High match room should be highly recommended"
    
    # Verify low similarity room is not highly recommended
    assert low_result['similarity_score'] <= 0.7, \
        f"Low match room should have score <= 0.7, got {low_result['similarity_score']}"
    assert low_result['highly_recommended'] is False, \
        "Low match room should not be highly recommended"


@settings(max_examples=100)
@given(
    user_taste_vector=taste_vector_strategy(),
    rooms=st.lists(room_strategy(), min_size=1, max_size=20)
)
def test_recommended_rooms_return_type(user_taste_vector, rooms):
    """
    Property 7: Recommendation Display (Type Property)
    
    For any user taste vector and rooms list, get_recommended_rooms must return a list.
    """
    recommended_rooms = get_recommended_rooms(user_taste_vector, rooms)
    
    assert isinstance(recommended_rooms, list), \
        f"Expected list, got {type(recommended_rooms)}"
    
    # Verify each element is a dictionary
    for i, room in enumerate(recommended_rooms):
        assert isinstance(room, dict), \
            f"Room at index {i} should be dict, got {type(room)}"


@settings(max_examples=100)
@given(
    user_taste_vector=taste_vector_strategy(),
    rooms=st.lists(room_strategy(), min_size=1, max_size=20)
)
def test_recommended_rooms_no_duplicates(user_taste_vector, rooms):
    """
    Property 7: Recommendation Display (Uniqueness)
    
    For any rooms list, get_recommended_rooms must not introduce duplicate rooms.
    """
    # Ensure input rooms have unique IDs
    unique_rooms = []
    seen_ids = set()
    for room in rooms:
        if room['id'] not in seen_ids:
            unique_rooms.append(room)
            seen_ids.add(room['id'])
    
    # Get recommended rooms
    recommended_rooms = get_recommended_rooms(user_taste_vector, unique_rooms)
    
    # Verify no duplicate IDs in output
    output_ids = [room['id'] for room in recommended_rooms]
    assert len(output_ids) == len(set(output_ids)), \
        f"Duplicate room IDs found in output: {output_ids}"
