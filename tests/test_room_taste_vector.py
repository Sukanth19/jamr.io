"""
Unit tests for room taste vector generation.

Tests the generate_room_taste_vector function with various genre combinations.
"""

import pytest
from backend.recommendation_engine import generate_room_taste_vector, GENRE_VECTORS


def test_generate_room_taste_vector_single_genre():
    """Test room taste vector generation with a single genre."""
    result = generate_room_taste_vector(['rock'])
    
    # Should match the rock genre vector exactly
    assert result == GENRE_VECTORS['rock']


def test_generate_room_taste_vector_multiple_genres():
    """Test room taste vector generation with multiple genres."""
    result = generate_room_taste_vector(['rock', 'pop'])
    
    # Should be average of rock and pop vectors
    rock = GENRE_VECTORS['rock']
    pop = GENRE_VECTORS['pop']
    
    expected_danceability = (rock['danceability'] + pop['danceability']) / 2
    expected_energy = (rock['energy'] + pop['energy']) / 2
    
    assert abs(result['danceability'] - expected_danceability) < 0.0001
    assert abs(result['energy'] - expected_energy) < 0.0001


def test_generate_room_taste_vector_empty_list():
    """Test room taste vector generation with empty genre list."""
    result = generate_room_taste_vector([])
    
    # Should return default taste vector with all values at 0.5
    assert result['danceability'] == 0.5
    assert result['energy'] == 0.5
    assert result['valence'] == 0.5
    assert result['acousticness'] == 0.5
    assert result['instrumentalness'] == 0.5
    assert result['speechiness'] == 0.5
    assert result['tempo_normalized'] == 0.5


def test_generate_room_taste_vector_unknown_genre():
    """Test room taste vector generation with unknown genre."""
    result = generate_room_taste_vector(['unknown-genre'])
    
    # Should return default taste vector since no valid genres
    assert result['danceability'] == 0.5
    assert result['energy'] == 0.5


def test_generate_room_taste_vector_mixed_valid_invalid():
    """Test room taste vector generation with mix of valid and invalid genres."""
    result = generate_room_taste_vector(['rock', 'unknown-genre', 'pop'])
    
    # Should average only the valid genres (rock and pop)
    rock = GENRE_VECTORS['rock']
    pop = GENRE_VECTORS['pop']
    
    expected_danceability = (rock['danceability'] + pop['danceability']) / 2
    assert abs(result['danceability'] - expected_danceability) < 0.0001


def test_generate_room_taste_vector_case_insensitive():
    """Test that genre matching is case-insensitive."""
    result_lower = generate_room_taste_vector(['rock'])
    result_upper = generate_room_taste_vector(['ROCK'])
    result_mixed = generate_room_taste_vector(['RoCk'])
    
    # All should produce the same result
    assert result_lower == result_upper == result_mixed


def test_generate_room_taste_vector_all_features_present():
    """Test that all required features are present in the result."""
    result = generate_room_taste_vector(['jazz'])
    
    required_keys = ['danceability', 'energy', 'valence', 'acousticness',
                     'instrumentalness', 'speechiness', 'tempo_normalized']
    
    for key in required_keys:
        assert key in result
        assert 0.0 <= result[key] <= 1.0


def test_generate_room_taste_vector_three_genres():
    """Test room taste vector generation with three genres."""
    result = generate_room_taste_vector(['rock', 'pop', 'jazz'])
    
    # Should be average of all three
    rock = GENRE_VECTORS['rock']
    pop = GENRE_VECTORS['pop']
    jazz = GENRE_VECTORS['jazz']
    
    expected_energy = (rock['energy'] + pop['energy'] + jazz['energy']) / 3
    assert abs(result['energy'] - expected_energy) < 0.0001
