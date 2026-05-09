"""
Recommendation engine for jamr.io MVP.

This module provides functionality for generating taste vectors from Spotify audio features
and calculating similarity scores between users and rooms.
"""

from typing import Dict, List, Optional


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
