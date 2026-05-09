"""Property-based tests for taste vector structure and Spotify data fetching.

Feature: jamr-io-mvp
Tests that taste vectors have correct structure and Spotify data fetching returns expected format.
"""

import pytest
from unittest.mock import Mock, patch
from hypothesis import given, strategies as st, settings, assume
from backend.spotify_client import SpotifyClient, SpotifyAPIError
from backend.recommendation_engine import generate_user_taste_vector


# Feature: jamr-io-mvp, Property 3: Spotify Data Fetching
# **Validates: Requirements 2.1, 2.2, 2.3**


@settings(max_examples=100)
@given(
    limit=st.integers(min_value=1, max_value=50),
    time_range=st.sampled_from(["short_term", "medium_term", "long_term"])
)
@patch('backend.spotify_client.requests.Session.request')
def test_get_user_top_tracks_returns_expected_format(mock_request, limit, time_range):
    """
    Property 3: Spotify Data Fetching (Part 1 - Top Tracks Format)
    
    For any user authentication, the platform must fetch the user's top tracks
    from the Spotify API and return a list of track objects.
    """
    # Mock successful response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [
            {"id": f"track_{i}", "name": f"Track {i}", "uri": f"spotify:track:{i}"}
            for i in range(limit)
        ]
    }
    mock_request.return_value = mock_response
    
    client = SpotifyClient("test_token")
    result = client.get_user_top_tracks(limit=limit, time_range=time_range)
    
    # Verify result is a list
    assert isinstance(result, list)
    
    # Verify correct number of tracks returned
    assert len(result) == limit
    
    # Verify each track has expected structure
    for track in result:
        assert isinstance(track, dict)
        assert "id" in track
        assert "name" in track
        assert "uri" in track


@settings(max_examples=100)
@given(
    limit=st.integers(min_value=1, max_value=50),
    time_range=st.sampled_from(["short_term", "medium_term", "long_term"])
)
@patch('backend.spotify_client.requests.Session.request')
def test_get_user_top_artists_returns_expected_format(mock_request, limit, time_range):
    """
    Property 3: Spotify Data Fetching (Part 2 - Top Artists Format)
    
    For any user authentication, the platform must fetch the user's top artists
    from the Spotify API and return a list of artist objects.
    """
    # Mock successful response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [
            {"id": f"artist_{i}", "name": f"Artist {i}", "uri": f"spotify:artist:{i}"}
            for i in range(limit)
        ]
    }
    mock_request.return_value = mock_response
    
    client = SpotifyClient("test_token")
    result = client.get_user_top_artists(limit=limit, time_range=time_range)
    
    # Verify result is a list
    assert isinstance(result, list)
    
    # Verify correct number of artists returned
    assert len(result) == limit
    
    # Verify each artist has expected structure
    for artist in result:
        assert isinstance(artist, dict)
        assert "id" in artist
        assert "name" in artist
        assert "uri" in artist


@settings(max_examples=100)
@given(
    num_tracks=st.integers(min_value=1, max_value=100)
)
@patch('backend.spotify_client.requests.Session.request')
def test_get_audio_features_returns_expected_format(mock_request, num_tracks):
    """
    Property 3: Spotify Data Fetching (Part 3 - Audio Features Format)
    
    For any user authentication, the platform must fetch audio features for
    the user's top tracks from the Spotify API and return a list of audio feature objects.
    """
    # Mock successful response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "audio_features": [
            {
                "id": f"track_{i}",
                "danceability": 0.5,
                "energy": 0.6,
                "valence": 0.7,
                "acousticness": 0.3,
                "instrumentalness": 0.1,
                "speechiness": 0.05,
                "tempo": 120.0
            }
            for i in range(num_tracks)
        ]
    }
    mock_request.return_value = mock_response
    
    client = SpotifyClient("test_token")
    track_ids = [f"track_{i}" for i in range(num_tracks)]
    result = client.get_audio_features(track_ids)
    
    # Verify result is a list
    assert isinstance(result, list)
    
    # Verify correct number of features returned
    assert len(result) == num_tracks
    
    # Verify each feature object has expected structure
    for features in result:
        assert isinstance(features, dict)
        assert "id" in features
        assert "danceability" in features
        assert "energy" in features
        assert "valence" in features
        assert "acousticness" in features
        assert "instrumentalness" in features
        assert "speechiness" in features
        assert "tempo" in features


@settings(max_examples=100)
@given(
    num_tracks=st.integers(min_value=1, max_value=50)
)
@patch('backend.spotify_client.requests.Session.request')
def test_spotify_data_fetching_integration(mock_request, num_tracks):
    """
    Property 3: Spotify Data Fetching (Part 4 - Integration)
    
    For any user authentication, the platform must successfully fetch top tracks,
    top artists, and audio features in sequence.
    """
    # Mock responses for all three API calls
    mock_tracks_response = Mock()
    mock_tracks_response.status_code = 200
    mock_tracks_response.json.return_value = {
        "items": [{"id": f"track_{i}", "name": f"Track {i}"} for i in range(num_tracks)]
    }
    
    mock_artists_response = Mock()
    mock_artists_response.status_code = 200
    mock_artists_response.json.return_value = {
        "items": [{"id": f"artist_{i}", "name": f"Artist {i}"} for i in range(num_tracks)]
    }
    
    mock_features_response = Mock()
    mock_features_response.status_code = 200
    mock_features_response.json.return_value = {
        "audio_features": [
            {
                "id": f"track_{i}",
                "danceability": 0.5,
                "energy": 0.6,
                "valence": 0.7,
                "acousticness": 0.3,
                "instrumentalness": 0.1,
                "speechiness": 0.05,
                "tempo": 120.0
            }
            for i in range(num_tracks)
        ]
    }
    
    mock_request.side_effect = [mock_tracks_response, mock_artists_response, mock_features_response]
    
    client = SpotifyClient("test_token")
    
    # Fetch all data
    tracks = client.get_user_top_tracks(limit=num_tracks)
    artists = client.get_user_top_artists(limit=num_tracks)
    track_ids = [track["id"] for track in tracks]
    features = client.get_audio_features(track_ids)
    
    # Verify all data was fetched successfully
    assert len(tracks) == num_tracks
    assert len(artists) == num_tracks
    assert len(features) == num_tracks
    
    # Verify all three API calls were made
    assert mock_request.call_count == 3


# Feature: jamr-io-mvp, Property 4: Taste Vector Structure
# **Validates: Requirements 2.4, 2.5, 5.6**


@settings(max_examples=100)
@given(
    num_tracks=st.integers(min_value=1, max_value=50),
    danceability=st.floats(min_value=0.0, max_value=1.0),
    energy=st.floats(min_value=0.0, max_value=1.0),
    valence=st.floats(min_value=0.0, max_value=1.0),
    acousticness=st.floats(min_value=0.0, max_value=1.0),
    instrumentalness=st.floats(min_value=0.0, max_value=1.0),
    speechiness=st.floats(min_value=0.0, max_value=1.0),
    tempo=st.floats(min_value=40.0, max_value=250.0)
)
def test_taste_vector_has_required_keys(
    num_tracks, danceability, energy, valence, acousticness, 
    instrumentalness, speechiness, tempo
):
    """
    Property 4: Taste Vector Structure (Part 1 - Required Keys)
    
    For any generated taste vector (user or room), the vector must be a valid JSON object
    containing all required keys: danceability, energy, valence, acousticness,
    instrumentalness, speechiness, tempo_normalized.
    """
    # Generate audio features
    audio_features = [
        {
            "danceability": danceability,
            "energy": energy,
            "valence": valence,
            "acousticness": acousticness,
            "instrumentalness": instrumentalness,
            "speechiness": speechiness,
            "tempo": tempo
        }
        for _ in range(num_tracks)
    ]
    
    # Generate taste vector
    taste_vector = generate_user_taste_vector(audio_features)
    
    # Verify all required keys are present
    required_keys = [
        "danceability", "energy", "valence", "acousticness",
        "instrumentalness", "speechiness", "tempo_normalized"
    ]
    
    for key in required_keys:
        assert key in taste_vector, f"Missing required key: {key}"
    
    # Verify no extra keys
    assert set(taste_vector.keys()) == set(required_keys)


@settings(max_examples=100)
@given(
    num_tracks=st.integers(min_value=1, max_value=50),
    danceability=st.floats(min_value=0.0, max_value=1.0),
    energy=st.floats(min_value=0.0, max_value=1.0),
    valence=st.floats(min_value=0.0, max_value=1.0),
    acousticness=st.floats(min_value=0.0, max_value=1.0),
    instrumentalness=st.floats(min_value=0.0, max_value=1.0),
    speechiness=st.floats(min_value=0.0, max_value=1.0),
    tempo=st.floats(min_value=40.0, max_value=250.0)
)
def test_taste_vector_values_in_valid_range(
    num_tracks, danceability, energy, valence, acousticness,
    instrumentalness, speechiness, tempo
):
    """
    Property 4: Taste Vector Structure (Part 2 - Value Range)
    
    For any generated taste vector, all values must be numeric and between 0 and 1.
    """
    # Generate audio features
    audio_features = [
        {
            "danceability": danceability,
            "energy": energy,
            "valence": valence,
            "acousticness": acousticness,
            "instrumentalness": instrumentalness,
            "speechiness": speechiness,
            "tempo": tempo
        }
        for _ in range(num_tracks)
    ]
    
    # Generate taste vector
    taste_vector = generate_user_taste_vector(audio_features)
    
    # Verify all values are numeric and in range [0, 1]
    for key, value in taste_vector.items():
        assert isinstance(value, (int, float)), f"{key} value is not numeric: {type(value)}"
        assert 0.0 <= value <= 1.0, f"{key} value {value} is not in range [0, 1]"


@settings(max_examples=100)
@given(
    num_tracks=st.integers(min_value=1, max_value=50),
    data=st.data()
)
def test_taste_vector_with_random_audio_features(num_tracks, data):
    """
    Property 4: Taste Vector Structure (Part 3 - Random Features)
    
    For any generated taste vector with random audio features, the structure
    must remain valid regardless of input values.
    """
    # Generate random audio features using st.data()
    audio_features = []
    for _ in range(num_tracks):
        features = {
            "danceability": data.draw(st.floats(min_value=0.0, max_value=1.0)),
            "energy": data.draw(st.floats(min_value=0.0, max_value=1.0)),
            "valence": data.draw(st.floats(min_value=0.0, max_value=1.0)),
            "acousticness": data.draw(st.floats(min_value=0.0, max_value=1.0)),
            "instrumentalness": data.draw(st.floats(min_value=0.0, max_value=1.0)),
            "speechiness": data.draw(st.floats(min_value=0.0, max_value=1.0)),
            "tempo": data.draw(st.floats(min_value=40.0, max_value=250.0))
        }
        audio_features.append(features)
    
    # Generate taste vector
    taste_vector = generate_user_taste_vector(audio_features)
    
    # Verify structure
    required_keys = [
        "danceability", "energy", "valence", "acousticness",
        "instrumentalness", "speechiness", "tempo_normalized"
    ]
    
    assert set(taste_vector.keys()) == set(required_keys)
    
    for key, value in taste_vector.items():
        assert isinstance(value, (int, float))
        assert 0.0 <= value <= 1.0


def test_taste_vector_empty_features_returns_default():
    """
    Property 4: Taste Vector Structure (Part 4 - Empty Features)
    
    For any taste vector generation with empty audio features, the platform
    must return a default taste vector with all values at 0.5.
    """
    # Generate taste vector with empty features
    taste_vector = generate_user_taste_vector([])
    
    # Verify structure
    required_keys = [
        "danceability", "energy", "valence", "acousticness",
        "instrumentalness", "speechiness", "tempo_normalized"
    ]
    
    assert set(taste_vector.keys()) == set(required_keys)
    
    # Verify all values are 0.5 (default)
    for key, value in taste_vector.items():
        assert value == 0.5, f"{key} should be 0.5 for empty features, got {value}"


@settings(max_examples=100)
@given(
    num_tracks=st.integers(min_value=1, max_value=50),
    missing_keys=st.lists(
        st.sampled_from([
            "danceability", "energy", "valence", "acousticness",
            "instrumentalness", "speechiness", "tempo"
        ]),
        min_size=1,
        max_size=3,
        unique=True
    )
)
def test_taste_vector_with_missing_features(num_tracks, missing_keys):
    """
    Property 4: Taste Vector Structure (Part 5 - Missing Features)
    
    For any taste vector generation with missing audio features, the platform
    must still return a valid taste vector with default values for missing features.
    """
    # Generate audio features with some keys missing
    audio_features = []
    for _ in range(num_tracks):
        features = {
            "danceability": 0.5,
            "energy": 0.6,
            "valence": 0.7,
            "acousticness": 0.3,
            "instrumentalness": 0.1,
            "speechiness": 0.05,
            "tempo": 120.0
        }
        # Remove some keys
        for key in missing_keys:
            features.pop(key, None)
        
        audio_features.append(features)
    
    # Generate taste vector
    taste_vector = generate_user_taste_vector(audio_features)
    
    # Verify structure is still valid
    required_keys = [
        "danceability", "energy", "valence", "acousticness",
        "instrumentalness", "speechiness", "tempo_normalized"
    ]
    
    assert set(taste_vector.keys()) == set(required_keys)
    
    # Verify all values are in valid range
    for key, value in taste_vector.items():
        assert isinstance(value, (int, float))
        assert 0.0 <= value <= 1.0


@settings(max_examples=100)
@given(
    num_tracks=st.integers(min_value=1, max_value=50),
    tempo=st.floats(min_value=200.0, max_value=500.0)
)
def test_taste_vector_tempo_normalization_caps_at_one(num_tracks, tempo):
    """
    Property 4: Taste Vector Structure (Part 6 - Tempo Normalization Cap)
    
    For any taste vector generation with tempo values above 200 BPM,
    the tempo_normalized value must be capped at 1.0.
    """
    # Generate audio features with high tempo
    audio_features = [
        {
            "danceability": 0.5,
            "energy": 0.6,
            "valence": 0.7,
            "acousticness": 0.3,
            "instrumentalness": 0.1,
            "speechiness": 0.05,
            "tempo": tempo
        }
        for _ in range(num_tracks)
    ]
    
    # Generate taste vector
    taste_vector = generate_user_taste_vector(audio_features)
    
    # Verify tempo_normalized is capped at 1.0
    assert taste_vector["tempo_normalized"] <= 1.0
    assert taste_vector["tempo_normalized"] >= 0.0


@settings(max_examples=100)
@given(
    num_tracks=st.integers(min_value=1, max_value=50),
    none_probability=st.floats(min_value=0.1, max_value=0.5)
)
def test_taste_vector_with_none_values(num_tracks, none_probability):
    """
    Property 4: Taste Vector Structure (Part 7 - None Values)
    
    For any taste vector generation with None values in audio features,
    the platform must handle them gracefully and return a valid taste vector.
    """
    import random
    
    # Generate audio features with some None values
    audio_features = []
    for _ in range(num_tracks):
        features = {
            "danceability": None if random.random() < none_probability else 0.5,
            "energy": None if random.random() < none_probability else 0.6,
            "valence": None if random.random() < none_probability else 0.7,
            "acousticness": None if random.random() < none_probability else 0.3,
            "instrumentalness": None if random.random() < none_probability else 0.1,
            "speechiness": None if random.random() < none_probability else 0.05,
            "tempo": None if random.random() < none_probability else 120.0
        }
        audio_features.append(features)
    
    # Generate taste vector
    taste_vector = generate_user_taste_vector(audio_features)
    
    # Verify structure is valid
    required_keys = [
        "danceability", "energy", "valence", "acousticness",
        "instrumentalness", "speechiness", "tempo_normalized"
    ]
    
    assert set(taste_vector.keys()) == set(required_keys)
    
    # Verify all values are in valid range
    for key, value in taste_vector.items():
        assert isinstance(value, (int, float))
        assert 0.0 <= value <= 1.0


@settings(max_examples=100)
@given(
    danceability=st.floats(min_value=0.0, max_value=1.0),
    energy=st.floats(min_value=0.0, max_value=1.0),
    valence=st.floats(min_value=0.0, max_value=1.0),
    acousticness=st.floats(min_value=0.0, max_value=1.0),
    instrumentalness=st.floats(min_value=0.0, max_value=1.0),
    speechiness=st.floats(min_value=0.0, max_value=1.0),
    tempo=st.floats(min_value=40.0, max_value=200.0)
)
def test_taste_vector_single_track(
    danceability, energy, valence, acousticness,
    instrumentalness, speechiness, tempo
):
    """
    Property 4: Taste Vector Structure (Part 8 - Single Track)
    
    For any taste vector generation with a single track, the taste vector
    values must equal the input feature values (with tempo normalized).
    """
    # Generate audio features for single track
    audio_features = [
        {
            "danceability": danceability,
            "energy": energy,
            "valence": valence,
            "acousticness": acousticness,
            "instrumentalness": instrumentalness,
            "speechiness": speechiness,
            "tempo": tempo
        }
    ]
    
    # Generate taste vector
    taste_vector = generate_user_taste_vector(audio_features)
    
    # Verify values match input (with small tolerance for floating point)
    assert abs(taste_vector["danceability"] - danceability) < 0.0001
    assert abs(taste_vector["energy"] - energy) < 0.0001
    assert abs(taste_vector["valence"] - valence) < 0.0001
    assert abs(taste_vector["acousticness"] - acousticness) < 0.0001
    assert abs(taste_vector["instrumentalness"] - instrumentalness) < 0.0001
    assert abs(taste_vector["speechiness"] - speechiness) < 0.0001
    
    # Verify tempo is normalized
    expected_tempo_normalized = min(tempo / 200.0, 1.0)
    assert abs(taste_vector["tempo_normalized"] - expected_tempo_normalized) < 0.0001


@settings(max_examples=100)
@given(
    num_tracks=st.integers(min_value=2, max_value=50)
)
def test_taste_vector_averaging_behavior(num_tracks):
    """
    Property 4: Taste Vector Structure (Part 9 - Averaging)
    
    For any taste vector generation with multiple tracks, the taste vector
    values must be the mean of the input feature values.
    """
    # Generate audio features with known values
    audio_features = []
    for i in range(num_tracks):
        features = {
            "danceability": (i + 1) / (num_tracks + 1),  # Varying values
            "energy": 0.5,  # Constant value
            "valence": 0.7,
            "acousticness": 0.3,
            "instrumentalness": 0.1,
            "speechiness": 0.05,
            "tempo": 120.0
        }
        audio_features.append(features)
    
    # Generate taste vector
    taste_vector = generate_user_taste_vector(audio_features)
    
    # Calculate expected mean for danceability
    expected_danceability = sum((i + 1) / (num_tracks + 1) for i in range(num_tracks)) / num_tracks
    
    # Verify averaging (with tolerance for floating point)
    assert abs(taste_vector["danceability"] - expected_danceability) < 0.0001
    assert abs(taste_vector["energy"] - 0.5) < 0.0001
    assert abs(taste_vector["valence"] - 0.7) < 0.0001


@settings(max_examples=100)
@given(
    num_tracks=st.integers(min_value=1, max_value=50),
    data=st.data()
)
def test_taste_vector_is_json_serializable(num_tracks, data):
    """
    Property 4: Taste Vector Structure (Part 10 - JSON Serializable)
    
    For any generated taste vector, the vector must be JSON serializable
    (all values must be JSON-compatible types).
    """
    import json
    
    # Generate audio features using st.data()
    audio_features = []
    for _ in range(num_tracks):
        features = {
            "danceability": data.draw(st.floats(min_value=0.0, max_value=1.0)),
            "energy": data.draw(st.floats(min_value=0.0, max_value=1.0)),
            "valence": data.draw(st.floats(min_value=0.0, max_value=1.0)),
            "acousticness": data.draw(st.floats(min_value=0.0, max_value=1.0)),
            "instrumentalness": data.draw(st.floats(min_value=0.0, max_value=1.0)),
            "speechiness": data.draw(st.floats(min_value=0.0, max_value=1.0)),
            "tempo": data.draw(st.floats(min_value=40.0, max_value=250.0))
        }
        audio_features.append(features)
    
    # Generate taste vector
    taste_vector = generate_user_taste_vector(audio_features)
    
    # Verify it can be serialized to JSON
    try:
        json_str = json.dumps(taste_vector)
        # Verify it can be deserialized back
        deserialized = json.loads(json_str)
        assert deserialized == taste_vector
    except (TypeError, ValueError) as e:
        pytest.fail(f"Taste vector is not JSON serializable: {e}")
