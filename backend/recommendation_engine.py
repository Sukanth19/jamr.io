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


# Keywords in Spotify artist genres (e.g. "uk hip hop", "edm", "neo soul")
# that map onto our base genres. Checked in addition to the base genre names.
GENRE_ALIASES = {
    'hip hop': 'hip-hop',
    'rap': 'hip-hop',
    'trap': 'hip-hop',
    'edm': 'electronic',
    'house': 'electronic',
    'techno': 'electronic',
    'trance': 'electronic',
    'dubstep': 'electronic',
    'drum and bass': 'electronic',
    'rnb': 'r&b',
    'r&b': 'r&b',
    'reggaeton': 'latin',
    'salsa': 'latin',
    'bachata': 'latin',
    'singer-songwriter': 'folk',
    'americana': 'country',
    'bluegrass': 'country',
    'orchestra': 'classical',
    'baroque': 'classical',
    'hardcore': 'punk',
}


def map_spotify_genres(spotify_genres: List[str]) -> List[str]:
    """
    Map free-form Spotify artist genres onto the base genres in GENRE_VECTORS.

    A single Spotify genre can map to several base genres (e.g. "indie rock"
    → indie, rock). Duplicates are kept so frequent genres weigh more.

    Args:
        spotify_genres: Genre strings from Spotify artist objects.

    Returns:
        List of base genre keys (may contain duplicates).
    """
    mapped = []
    for genre in spotify_genres:
        genre = genre.lower()
        matches = {base for base in GENRE_VECTORS if base in genre}
        matches |= {base for alias, base in GENRE_ALIASES.items() if alias in genre}
        mapped.extend(sorted(matches))
    return mapped


def generate_taste_vector_from_genres(spotify_genres: List[str]) -> Dict[str, float]:
    """
    Generate a user taste vector from their top artists' Spotify genres.

    Used as a fallback when Spotify's audio-features endpoint is unavailable
    (it returns 403 for apps created after November 2024). Produces a vector
    in the same space as room taste vectors.

    Args:
        spotify_genres: Genre strings collected from the user's top artists.

    Returns:
        Taste vector dictionary, or the default vector if no genres map.
    """
    return generate_room_taste_vector(map_spotify_genres(spotify_genres))


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


def _euclidean_distance(vector_a: Dict[str, float], vector_b: Dict[str, float]) -> float:
    """Euclidean distance between two taste vectors over their common keys."""
    common_keys = set(vector_a.keys()) & set(vector_b.keys())
    return sum((vector_a[key] - vector_b[key]) ** 2 for key in common_keys) ** 0.5


def _build_genre_closeness() -> Dict[tuple, float]:
    """
    Precompute how close each pair of base genres is, scaled to 0-1.
    
    Uses Euclidean distance between genre vectors, min-max scaled across all
    pairs so the closest pair (e.g. metal/punk) is ~1 and the farthest
    (e.g. classical/electronic) is 0. Cosine similarity is unsuitable here:
    every genre vector is all-positive, so nearly all pairs score above 0.9.
    """
    genres = list(GENRE_VECTORS)
    distances = {
        (a, b): _euclidean_distance(GENRE_VECTORS[a], GENRE_VECTORS[b])
        for a in genres for b in genres if a != b
    }
    d_min, d_max = min(distances.values()), max(distances.values())
    return {pair: 1 - (d - d_min) / (d_max - d_min) for pair, d in distances.items()}


GENRE_CLOSENESS = _build_genre_closeness()

# How much a room genre the user didn't pick, but is close to one they did,
# can contribute (an exact match contributes 1)
RELATED_GENRE_WEIGHT = 0.5


def genre_match_score(user_genres: List[str], room_genres: List[str]) -> float:
    """
    Score how well a room's genres fit the genres a user picked.
    
    Each room genre the user picked counts 1. Each other room genre counts
    RELATED_GENRE_WEIGHT × its closeness to the nearest genre the user picked.
    The score is the average over the room's genres, so a room scores > 0.7
    only when most of its genres are ones the user picked.
    
    Args:
        user_genres: Genres the user picked.
        room_genres: The room's genre tags.
    
    Returns:
        Float between 0 and 1. Returns 0.0 if either list has no known genres.
    """
    user_set = {g.lower() for g in user_genres if g.lower() in GENRE_VECTORS}
    room_list = [g.lower() for g in room_genres if g.lower() in GENRE_VECTORS]
    
    if not user_set or not room_list:
        return 0.0
    
    total = 0.0
    for genre in room_list:
        if genre in user_set:
            total += 1.0
        else:
            total += RELATED_GENRE_WEIGHT * max(GENRE_CLOSENESS[(genre, u)] for u in user_set)
    
    return total / len(room_list)


def get_recommended_rooms(
    user_taste_vector: Dict[str, float],
    rooms: List[Dict],
    user_genres: Optional[List[str]] = None
) -> List[Dict]:
    """
    Rank rooms by similarity to user taste vector and mark highly recommended rooms.
    
    Calculates cosine similarity between the user's taste vector and each room's taste vector,
    sorts rooms by similarity score in descending order, and marks rooms with score > 0.7
    as highly recommended.
    
    Args:
        user_taste_vector: User's taste vector dictionary with audio feature values.
        rooms: List of room dictionaries. Each room dict must contain:
               - 'taste_vector': Dict[str, float] - Room's taste vector
               - Other room fields (id, name, description, etc.)
    
    Returns:
        List of room dictionaries sorted by similarity score (descending), with added fields:
        - 'similarity_score': float (0-1) - Cosine similarity to user taste
        - 'highly_recommended': bool - True if similarity_score > 0.7
    
    If user_genres is given (the user picked favorite genres), rooms are scored
    with genre_match_score against each room's 'genre_tags' instead, and each
    room also gets 'matched_genres': the room genres the user picked.
    
    Requirements: 4.3, 4.4, 4.5
    """
    # Calculate similarity score for each room
    rooms_with_scores = []
    for room in rooms:
        room_taste_vector = room.get('taste_vector', {})
        
        # Create new room dict with added fields
        room_with_score = room.copy()
        
        # Calculate similarity score
        if user_genres:
            room_genres = room.get('genre_tags') or []
            similarity_score = genre_match_score(user_genres, room_genres)
            picked = {g.lower() for g in user_genres}
            room_with_score['matched_genres'] = [g for g in room_genres if g.lower() in picked]
        else:
            similarity_score = cosine_similarity(user_taste_vector, room_taste_vector)
        
        room_with_score['similarity_score'] = similarity_score
        room_with_score['highly_recommended'] = similarity_score > 0.7
        
        rooms_with_scores.append(room_with_score)
    
    # Sort rooms by similarity score descending
    rooms_with_scores.sort(key=lambda r: r['similarity_score'], reverse=True)
    
    return rooms_with_scores


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


def find_shared_artists(user_artists: Optional[List[Dict]], others_artists: List[Optional[List[Dict]]]) -> List[str]:
    """
    Find the user's top artists that other people also have in their top artists.
    
    Args:
        user_artists: The user's top artists ([{"id", "name", ...}]), in Spotify's
            ranking order (most listened first).
        others_artists: Top artist lists of the other people to compare against.
    
    Returns:
        Names of shared artists, in the user's ranking order.
    """
    if not user_artists:
        return []
    
    other_ids = {
        artist.get("id")
        for artists in others_artists if artists
        for artist in artists
    }
    return [a["name"] for a in user_artists if a.get("id") in other_ids]
