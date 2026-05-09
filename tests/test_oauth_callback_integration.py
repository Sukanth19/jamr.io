"""Integration tests for OAuth callback taste vector generation."""

import pytest
from backend.auth import _generate_taste_vector, _default_taste_vector


def test_generate_taste_vector_with_valid_features():
    """Test taste vector generation with valid audio features."""
    audio_features = [
        {
            "danceability": 0.7,
            "energy": 0.8,
            "valence": 0.6,
            "acousticness": 0.2,
            "instrumentalness": 0.1,
            "speechiness": 0.05,
            "tempo": 120
        },
        {
            "danceability": 0.6,
            "energy": 0.7,
            "valence": 0.5,
            "acousticness": 0.3,
            "instrumentalness": 0.2,
            "speechiness": 0.08,
            "tempo": 130
        }
    ]
    
    taste_vector = _generate_taste_vector(audio_features)
    
    # Check all required keys are present
    assert "danceability" in taste_vector
    assert "energy" in taste_vector
    assert "valence" in taste_vector
    assert "acousticness" in taste_vector
    assert "instrumentalness" in taste_vector
    assert "speechiness" in taste_vector
    assert "tempo_normalized" in taste_vector
    
    # Check values are averages
    assert taste_vector["danceability"] == pytest.approx(0.65)
    assert taste_vector["energy"] == pytest.approx(0.75)
    assert taste_vector["valence"] == pytest.approx(0.55)
    assert taste_vector["acousticness"] == pytest.approx(0.25)
    assert taste_vector["instrumentalness"] == pytest.approx(0.15)
    assert taste_vector["speechiness"] == pytest.approx(0.065)
    
    # Check tempo is normalized (average of 120 and 130 is 125, normalized to 0.625)
    assert taste_vector["tempo_normalized"] == pytest.approx(0.625)


def test_generate_taste_vector_with_empty_list():
    """Test taste vector generation with empty audio features list."""
    taste_vector = _generate_taste_vector([])
    
    # Should return default taste vector
    default = _default_taste_vector()
    assert taste_vector == default


def test_generate_taste_vector_with_none_values():
    """Test taste vector generation with None values in features."""
    audio_features = [
        {
            "danceability": 0.7,
            "energy": None,
            "valence": 0.6,
            "acousticness": 0.2,
            "instrumentalness": 0.1,
            "speechiness": 0.05,
            "tempo": 120
        },
        None,  # Spotify sometimes returns null for unavailable features
        {
            "danceability": 0.6,
            "energy": 0.7,
            "valence": None,
            "acousticness": 0.3,
            "instrumentalness": 0.2,
            "speechiness": 0.08,
            "tempo": 130
        }
    ]
    
    taste_vector = _generate_taste_vector(audio_features)
    
    # Should handle None values gracefully
    assert "danceability" in taste_vector
    assert "energy" in taste_vector
    assert "valence" in taste_vector
    
    # Danceability should be average of 0.7 and 0.6
    assert taste_vector["danceability"] == pytest.approx(0.65)
    
    # Energy should be 0.7 (only one valid value)
    assert taste_vector["energy"] == pytest.approx(0.7)
    
    # Valence should be 0.6 (only one valid value)
    assert taste_vector["valence"] == pytest.approx(0.6)


def test_generate_taste_vector_with_missing_keys():
    """Test taste vector generation with missing keys in features."""
    audio_features = [
        {
            "danceability": 0.7,
            "energy": 0.8,
            # Missing other keys
        }
    ]
    
    taste_vector = _generate_taste_vector(audio_features)
    
    # Should have all required keys with defaults for missing ones
    assert "danceability" in taste_vector
    assert "energy" in taste_vector
    assert "valence" in taste_vector
    assert "acousticness" in taste_vector
    assert "instrumentalness" in taste_vector
    assert "speechiness" in taste_vector
    assert "tempo_normalized" in taste_vector
    
    # Present keys should have correct values
    assert taste_vector["danceability"] == pytest.approx(0.7)
    assert taste_vector["energy"] == pytest.approx(0.8)
    
    # Missing keys should have default value of 0.5
    assert taste_vector["valence"] == pytest.approx(0.5)
    assert taste_vector["acousticness"] == pytest.approx(0.5)


def test_generate_taste_vector_tempo_normalization():
    """Test that tempo is properly normalized to 0-1 range."""
    audio_features = [
        {"tempo": 200}  # Max expected tempo
    ]
    
    taste_vector = _generate_taste_vector(audio_features)
    
    # 200 BPM should normalize to 1.0
    assert taste_vector["tempo_normalized"] == pytest.approx(1.0)
    
    # Test with tempo above 200 (should cap at 1.0)
    audio_features = [
        {"tempo": 250}
    ]
    
    taste_vector = _generate_taste_vector(audio_features)
    assert taste_vector["tempo_normalized"] == pytest.approx(1.0)
    
    # Test with tempo of 100 (should be 0.5)
    audio_features = [
        {"tempo": 100}
    ]
    
    taste_vector = _generate_taste_vector(audio_features)
    assert taste_vector["tempo_normalized"] == pytest.approx(0.5)


def test_default_taste_vector():
    """Test that default taste vector has correct structure."""
    default = _default_taste_vector()
    
    # Check all required keys are present
    required_keys = ['danceability', 'energy', 'valence', 'acousticness', 
                     'instrumentalness', 'speechiness', 'tempo_normalized']
    
    for key in required_keys:
        assert key in default
        assert default[key] == 0.5  # All default values should be 0.5
