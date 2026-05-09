"""
Recommendation engine for jamr.io MVP.

This module provides functionality for generating taste vectors from Spotify audio features
and calculating similarity scores between users and rooms.
"""

from typing import Dict, List, Optional


# Genre to audio feature mapping
# Each genre is mapped to predefined audio feature values based on typical characteristics
GENRE_VECTORS = {
    'rock': {
        'danceability': 0.5,
        'energy': 0.8,
        'valence': 0.6,
        'acousticness': 0.2,
        'instrumentalness': 0.3,
        'speechiness': 0.05,
        'tempo_normalized': 0.65
    },
    'pop': {
        'danceability': 0.7,
        'energy': 0.7,
        'valence': 0.7,
        'acousticness': 0.2,
        'instrumentalness': 0.0,
        'speechiness': 0.1,
        'tempo_normalized': 0.6
    },
    'hip-hop': {
        'danceability': 0.75,
        'energy': 0.65,
        'valence': 0.55,
        'acousticness': 0.1,
        'instrumentalness': 0.05,
        'speechiness': 0.3,
        'tempo_normalized': 0.55
    },
    'electronic': {
        'danceability': 0.8,
        'energy': 0.85,
        'valence': 0.6,
        'acousticness': 0.05,
        'instrumentalness': 0.5,
        'speechiness': 0.05,
        'tempo_normalized': 0.7
    },
    'jazz': {
        'danceability': 0.5,
        'energy': 0.4,
        'valence': 0.5,
        'acousticness': 0.6,
        'instrumentalness': 0.6,
        'speechiness': 0.05,
        'tempo_normalized': 0.5
    },
    'classical': {
        'danceability': 0.3,
        'energy': 0.3,
        'valence': 0.5,
        'acousticness': 0.9,
        'instrumentalness': 0.9,
        'speechiness': 0.0,
        'tempo_normalized': 0.45
    },
    'r&b': {
        'danceability': 0.7,
        'energy': 0.6,
        'valence': 0.6,
        'acousticness': 0.2,
        'instrumentalness': 0.05,
        'speechiness': 0.15,
        'tempo_normalized': 0.5
    },
    'country': {
        'danceability': 0.6,
        'energy': 0.6,
        'valence': 0.65,
        'acousticness': 0.5,
        'instrumentalness': 0.1,
        'speechiness': 0.05,
        'tempo_normalized': 0.55
    },
    'metal': {
        'danceability': 0.4,
        'energy': 0.95,
        'valence': 0.4,
        'acousticness': 0.05,
        'instrumentalness': 0.4,
        'speechiness': 0.1,
        'tempo_normalized': 0.75
    },
    'indie': {
        'danceability': 0.55,
        'energy': 0.6,
        'valence': 0.55,
        'acousticness': 0.4,
        'instrumentalness': 0.2,
        'speechiness': 0.05,
        'tempo_normalized': 0.55
    },
    'folk': {
        'danceability': 0.45,
        'energy': 0.4,
        'valence': 0.6,
        'acousticness': 0.8,
        'instrumentalness': 0.2,
        'speechiness': 0.05,
        'tempo_normalized': 0.45
    },
    'blues': {
        'danceability': 0.5,
        'energy': 0.5,
        'valence': 0.4,
        'acousticness': 0.5,
        'instrumentalness': 0.3,
        'speechiness': 0.05,
        'tempo_normalized': 0.45
    },
    'reggae': {
        'danceability': 0.75,
        'energy': 0.6,
        'valence': 0.7,
        'acousticness': 0.3,
        'instrumentalness': 0.2,
        'speechiness': 0.15,
        'tempo_normalized': 0.45
    },
    'latin': {
        'danceability': 0.8,
        'energy': 0.75,
        'valence': 0.75,
        'acousticness': 0.2,
        'instrumentalness': 0.1,
        'speechiness': 0.1,
        'tempo_normalized': 0.6
    },
    'soul': {
        'danceability': 0.65,
        'energy': 0.6,
        'valence': 0.6,
        'acousticness': 0.3,
        'instrumentalness': 0.1,
        'speechiness': 0.1,
        'tempo_normalized': 0.5
    },
    'punk': {
        'danceability': 0.5,
        'energy': 0.9,
        'valence': 0.5,
        'acousticness': 0.1,
        'instrumentalness': 0.2,
        'speechiness': 0.15,
        'tempo_normalized': 0.75
    }
}


def generate_user_taste_vector(audio_features: List[Dict]) -> Dict[str, float]:
    """
    Generate taste vector from Spotify audio features.
    
    Calculates mean values for audio features across all tracks and normalizes
    tempo to 0-1 range. Returns a dictionary representing the user's music taste profile.
    
    Args:
        audio_features: List of audio feature dictionaries from Spotify API.
                       Each dict should contain keys: danceability, energy, valence,
                       acousticness, instrumentalness, speechiness, tempo.
    
    Returns:
        Dictionary with normalized audio feature means:
        {
            'danceability': float (0-1),
            'energy': float (0-1),
            'valence': float (0-1),
            'acousticness': float (0-1),
            'instrumentalness': float (0-1),
            'speechiness': float (0-1),
            'tempo_normalized': float (0-1)
        }
        
        If audio_features is empty, returns a default taste vector with all values at 0.5.
    
    Requirements: 2.4, 2.5
    """
    if not audio_features:
        return _default_taste_vector()
    
    # Initialize feature accumulators
    features = {
        'danceability': [],
        'energy': [],
        'valence': [],
        'acousticness': [],
        'instrumentalness': [],
        'speechiness': [],
        'tempo': []
    }
    
    # Collect feature values from all tracks
    for track in audio_features:
        for key in features:
            if key in track and track[key] is not None:
                features[key].append(track[key])
    
    # Calculate mean values
    taste_vector = {}
    for key, values in features.items():
        if values:
            mean_value = sum(values) / len(values)
            if key == 'tempo':
                # Normalize tempo to 0-1 range (divide by 200 BPM)
                taste_vector['tempo_normalized'] = min(mean_value / 200.0, 1.0)
            else:
                taste_vector[key] = mean_value
        else:
            # If no values for this feature, use default
            if key == 'tempo':
                taste_vector['tempo_normalized'] = 0.5
            else:
                taste_vector[key] = 0.5
    
    return taste_vector


def generate_room_taste_vector(genre_tags: List[str]) -> Dict[str, float]:
    """
    Generate taste vector for a room based on selected genre tags.
    
    Averages audio feature values across all selected genres to create a composite
    taste profile for the room. Unknown genres are ignored.
    
    Args:
        genre_tags: List of genre strings (e.g., ['rock', 'indie', 'pop']).
                   Genre names should be lowercase.
    
    Returns:
        Dictionary with averaged audio feature values:
        {
            'danceability': float (0-1),
            'energy': float (0-1),
            'valence': float (0-1),
            'acousticness': float (0-1),
            'instrumentalness': float (0-1),
            'speechiness': float (0-1),
            'tempo_normalized': float (0-1)
        }
        
        If no valid genres are provided, returns a default taste vector with all values at 0.5.
    
    Requirements: 5.6
    """
    if not genre_tags:
        return _default_taste_vector()
    
    # Filter to only known genres (case-insensitive)
    valid_genres = [
        genre.lower() for genre in genre_tags 
        if genre.lower() in GENRE_VECTORS
    ]
    
    if not valid_genres:
        return _default_taste_vector()
    
    # Initialize feature accumulators
    feature_keys = ['danceability', 'energy', 'valence', 'acousticness', 
                    'instrumentalness', 'speechiness', 'tempo_normalized']
    feature_sums = {key: 0.0 for key in feature_keys}
    
    # Sum feature values across all valid genres
    for genre in valid_genres:
        genre_vector = GENRE_VECTORS[genre]
        for key in feature_keys:
            feature_sums[key] += genre_vector[key]
    
    # Calculate averages
    num_genres = len(valid_genres)
    taste_vector = {
        key: feature_sums[key] / num_genres 
        for key in feature_keys
    }
    
    return taste_vector


def cosine_similarity(vector_a: Dict[str, float], vector_b: Dict[str, float]) -> float:
    """
    Calculate cosine similarity between two taste vectors.
    
    Cosine similarity measures the cosine of the angle between two vectors,
    resulting in a value between 0 (completely dissimilar) and 1 (identical).
    Formula: (A · B) / (||A|| × ||B||)
    
    Args:
        vector_a: First taste vector dictionary with feature keys and float values.
        vector_b: Second taste vector dictionary with feature keys and float values.
    
    Returns:
        Float between 0 and 1 representing similarity score.
        Returns 0.0 if either vector has zero magnitude.
    
    Requirements: 4.1, 4.2
    """
    # Get common keys between both vectors
    common_keys = set(vector_a.keys()) & set(vector_b.keys())
    
    if not common_keys:
        return 0.0
    
    # Calculate dot product (A · B)
    dot_product = sum(vector_a[key] * vector_b[key] for key in common_keys)
    
    # Calculate magnitude of vector A (||A||)
    magnitude_a = sum(vector_a[key] ** 2 for key in common_keys) ** 0.5
    
    # Calculate magnitude of vector B (||B||)
    magnitude_b = sum(vector_b[key] ** 2 for key in common_keys) ** 0.5
    
    # Avoid division by zero
    if magnitude_a == 0.0 or magnitude_b == 0.0:
        return 0.0
    
    # Calculate cosine similarity
    similarity = dot_product / (magnitude_a * magnitude_b)
    
    # Clamp to [0, 1] range to handle floating point precision issues
    return max(0.0, min(1.0, similarity))


def _default_taste_vector() -> Dict[str, float]:
    """
    Return default taste vector when no audio features are available.
    
    Returns:
        Dictionary with all features set to 0.5 (neutral values).
    """
    return {
        'danceability': 0.5,
        'energy': 0.5,
        'valence': 0.5,
        'acousticness': 0.5,
        'instrumentalness': 0.5,
        'speechiness': 0.5,
        'tempo_normalized': 0.5
    }
