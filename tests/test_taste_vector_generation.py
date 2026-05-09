"""
Unit tests for taste vector generation.

Tests the generate_user_taste_vector function with various inputs.
"""

import pytest
from backend.recommendation_engine import generate_user_taste_vector


def test_generate_user_taste_vector_with_valid_features():
    """Test taste vector generation with valid audio features."""
    audio_features = [
        {
            'danceability': 0.8,
            'energy': 0.7,
            'valence': 0.6,
            'acousticness': 0.2,
            'instrumentalness': 0.1,
            'speechiness': 0.05,
            'tempo': 120.0
        },
        {
            'danceability': 0.6,
            'energy': 0.5,
            'valence': 0.4,
            'acousticness': 0.3,
            'instrumentalness': 0.2,
            'speechiness': 0.1,
            'tempo': 100.0
        }
    ]
    
    result = generate_user_taste_vector(audio_features)
    
    # Check all required keys are present
    assert 'danceability' in result
    assert 'energy' in result
    assert 'valence' in result
    assert 'acousticness' in result
    assert 'instrumentalness' in result
    assert 'speechiness' in result
    assert 'tempo_normalized' in result
    
    # Check mean calculations (use approximate comparison for floating point)
    assert abs(result['danceability'] - 0.7) < 0.0001  # (0.8 + 0.6) / 2
    assert abs(result['energy'] - 0.6) < 0.0001  # (0.7 + 0.5) / 2
    assert abs(result['valence'] - 0.5) < 0.0001  # (0.6 + 0.4) / 2
    assert abs(result['acousticness'] - 0.25) < 0.0001  # (0.2 + 0.3) / 2
    assert abs(result['instrumentalness'] - 0.15) < 0.0001  # (0.1 + 0.2) / 2
    assert abs(result['speechiness'] - 0.075) < 0.0001  # (0.05 + 0.1) / 2
    assert abs(result['tempo_normalized'] - 0.55) < 0.0001  # (120 + 100) / 2 / 200


def test_generate_user_taste_vector_with_empty_list():
    """Test taste vector generation with empty audio features list."""
    result = generate_user_taste_vector([])
    
    # Should return default taste vector with all values at 0.5
    assert result['danceability'] == 0.5
    assert result['energy'] == 0.5
    assert result['valence'] == 0.5
    assert result['acousticness'] == 0.5
    assert result['instrumentalness'] == 0.5
    assert result['speechiness'] == 0.5
    assert result['tempo_normalized'] == 0.5


def test_generate_user_taste_vector_tempo_normalization():
    """Test that tempo is correctly normalized to 0-1 range."""
    audio_features = [
        {'danceability': 0.5, 'energy': 0.5, 'valence': 0.5, 
         'acousticness': 0.5, 'instrumentalness': 0.5, 'speechiness': 0.5,
         'tempo': 200.0}
    ]
    
    result = generate_user_taste_vector(audio_features)
    assert result['tempo_normalized'] == 1.0  # 200 / 200 = 1.0


def test_generate_user_taste_vector_tempo_exceeds_max():
    """Test that tempo values above 200 BPM are capped at 1.0."""
    audio_features = [
        {'danceability': 0.5, 'energy': 0.5, 'valence': 0.5,
         'acousticness': 0.5, 'instrumentalness': 0.5, 'speechiness': 0.5,
         'tempo': 250.0}
    ]
    
    result = generate_user_taste_vector(audio_features)
    assert result['tempo_normalized'] == 1.0  # Capped at 1.0


def test_generate_user_taste_vector_with_missing_features():
    """Test taste vector generation when some features are missing."""
    audio_features = [
        {
            'danceability': 0.8,
            'energy': 0.7,
            # Missing other features
        }
    ]
    
    result = generate_user_taste_vector(audio_features)
    
    # Present features should have their values
    assert result['danceability'] == 0.8
    assert result['energy'] == 0.7
    
    # Missing features should default to 0.5
    assert result['valence'] == 0.5
    assert result['acousticness'] == 0.5
    assert result['instrumentalness'] == 0.5
    assert result['speechiness'] == 0.5
    assert result['tempo_normalized'] == 0.5


def test_generate_user_taste_vector_with_none_values():
    """Test taste vector generation when features have None values."""
    audio_features = [
        {
            'danceability': 0.8,
            'energy': None,
            'valence': 0.6,
            'acousticness': None,
            'instrumentalness': 0.1,
            'speechiness': 0.05,
            'tempo': 120.0
        }
    ]
    
    result = generate_user_taste_vector(audio_features)
    
    # Non-None values should be used
    assert result['danceability'] == 0.8
    assert result['valence'] == 0.6
    assert result['instrumentalness'] == 0.1
    assert result['speechiness'] == 0.05
    assert result['tempo_normalized'] == 0.6  # 120 / 200
    
    # None values should default to 0.5
    assert result['energy'] == 0.5
    assert result['acousticness'] == 0.5


def test_generate_user_taste_vector_single_track():
    """Test taste vector generation with a single track."""
    audio_features = [
        {
            'danceability': 0.75,
            'energy': 0.85,
            'valence': 0.65,
            'acousticness': 0.15,
            'instrumentalness': 0.05,
            'speechiness': 0.08,
            'tempo': 128.0
        }
    ]
    
    result = generate_user_taste_vector(audio_features)
    
    # With single track, mean equals the value
    assert result['danceability'] == 0.75
    assert result['energy'] == 0.85
    assert result['valence'] == 0.65
    assert result['acousticness'] == 0.15
    assert result['instrumentalness'] == 0.05
    assert result['speechiness'] == 0.08
    assert result['tempo_normalized'] == 0.64  # 128 / 200
