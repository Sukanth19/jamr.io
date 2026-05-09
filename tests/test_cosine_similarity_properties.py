"""Property-based tests for cosine similarity calculation.

Feature: jamr-io-mvp
Tests that cosine similarity calculation is mathematically correct.
"""

import pytest
import math
from hypothesis import given, strategies as st, settings, assume
from backend.recommendation_engine import cosine_similarity


# Feature: jamr-io-mvp, Property 8: Cosine Similarity Calculation
# **Validates: Requirements 4.1, 4.2**


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


def calculate_expected_cosine_similarity(vector_a, vector_b):
    """Calculate expected cosine similarity using the formula: (A · B) / (||A|| × ||B||)."""
    # Get common keys
    common_keys = set(vector_a.keys()) & set(vector_b.keys())
    
    if not common_keys:
        return 0.0
    
    # Calculate dot product (A · B)
    dot_product = sum(vector_a[key] * vector_b[key] for key in common_keys)
    
    # Calculate magnitude of vector A (||A||)
    magnitude_a = math.sqrt(sum(vector_a[key] ** 2 for key in common_keys))
    
    # Calculate magnitude of vector B (||B||)
    magnitude_b = math.sqrt(sum(vector_b[key] ** 2 for key in common_keys))
    
    # Avoid division by zero
    if magnitude_a == 0.0 or magnitude_b == 0.0:
        return 0.0
    
    # Calculate cosine similarity
    similarity = dot_product / (magnitude_a * magnitude_b)
    
    # Clamp to [0, 1] range
    return max(0.0, min(1.0, similarity))


@settings(max_examples=100)
@given(
    vector_a=taste_vector_strategy(),
    vector_b=taste_vector_strategy()
)
def test_cosine_similarity_matches_mathematical_formula(vector_a, vector_b):
    """
    Property 8: Cosine Similarity Calculation
    
    For any user taste vector and room taste vector, the similarity score must equal
    the cosine similarity: (A · B) / (||A|| × ||B||), where A and B are the taste vectors.
    """
    # Calculate similarity using the implementation
    actual_similarity = cosine_similarity(vector_a, vector_b)
    
    # Calculate expected similarity using the mathematical formula
    expected_similarity = calculate_expected_cosine_similarity(vector_a, vector_b)
    
    # Verify they match (with small tolerance for floating point precision)
    assert abs(actual_similarity - expected_similarity) < 1e-9, \
        f"Cosine similarity mismatch: expected {expected_similarity}, got {actual_similarity}"
    
    # Verify result is in valid range [0, 1]
    assert 0.0 <= actual_similarity <= 1.0, \
        f"Cosine similarity {actual_similarity} is not in range [0, 1]"


@settings(max_examples=100)
@given(vector=taste_vector_strategy())
def test_cosine_similarity_identical_vectors(vector):
    """
    Property 8: Cosine Similarity Calculation (Edge Case - Identical Vectors)
    
    For any taste vector compared with itself, the cosine similarity must be 1.0
    (identical vectors have maximum similarity).
    """
    # Assume at least one non-zero value to avoid zero vector edge case
    assume(any(abs(v) > 1e-10 for v in vector.values()))
    
    similarity = cosine_similarity(vector, vector)
    
    # Identical vectors should have similarity of 1.0
    assert abs(similarity - 1.0) < 1e-9, \
        f"Identical vectors should have similarity 1.0, got {similarity}"


@settings(max_examples=100)
@given(vector=taste_vector_strategy())
def test_cosine_similarity_zero_vector(vector):
    """
    Property 8: Cosine Similarity Calculation (Edge Case - Zero Vector)
    
    For any taste vector compared with a zero vector, the cosine similarity must be 0.0
    (zero magnitude vectors have no similarity).
    """
    zero_vector = {key: 0.0 for key in vector.keys()}
    
    similarity = cosine_similarity(vector, zero_vector)
    
    # Zero vector should have similarity of 0.0
    assert similarity == 0.0, \
        f"Zero vector should have similarity 0.0, got {similarity}"


@settings(max_examples=100)
@given(
    vector_a=taste_vector_strategy(),
    vector_b=taste_vector_strategy()
)
def test_cosine_similarity_symmetry(vector_a, vector_b):
    """
    Property 8: Cosine Similarity Calculation (Symmetry Property)
    
    For any two taste vectors A and B, cosine_similarity(A, B) must equal
    cosine_similarity(B, A) (cosine similarity is symmetric).
    """
    similarity_ab = cosine_similarity(vector_a, vector_b)
    similarity_ba = cosine_similarity(vector_b, vector_a)
    
    assert abs(similarity_ab - similarity_ba) < 1e-9, \
        f"Cosine similarity is not symmetric: AB={similarity_ab}, BA={similarity_ba}"


@settings(max_examples=100)
@given(
    vector_a=taste_vector_strategy(),
    vector_b=taste_vector_strategy()
)
def test_cosine_similarity_range(vector_a, vector_b):
    """
    Property 8: Cosine Similarity Calculation (Range Property)
    
    For any two taste vectors, the cosine similarity must be in the range [0, 1].
    """
    similarity = cosine_similarity(vector_a, vector_b)
    
    assert 0.0 <= similarity <= 1.0, \
        f"Cosine similarity {similarity} is not in range [0, 1]"


@settings(max_examples=100)
@given(
    scale_factor=st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False)
)
def test_cosine_similarity_scale_invariance(scale_factor):
    """
    Property 8: Cosine Similarity Calculation (Scale Invariance)
    
    For any two taste vectors, scaling one vector by a positive constant should not
    change the cosine similarity (cosine similarity is scale-invariant).
    """
    vector_a = {
        'danceability': 0.5,
        'energy': 0.6,
        'valence': 0.7,
        'acousticness': 0.3,
        'instrumentalness': 0.1,
        'speechiness': 0.05,
        'tempo_normalized': 0.55
    }
    
    vector_b = {
        'danceability': 0.7,
        'energy': 0.8,
        'valence': 0.6,
        'acousticness': 0.2,
        'instrumentalness': 0.05,
        'speechiness': 0.08,
        'tempo_normalized': 0.65
    }
    
    # Calculate similarity with original vectors
    original_similarity = cosine_similarity(vector_a, vector_b)
    
    # Scale vector_b by scale_factor
    scaled_vector_b = {key: value * scale_factor for key, value in vector_b.items()}
    
    # Calculate similarity with scaled vector
    scaled_similarity = cosine_similarity(vector_a, scaled_vector_b)
    
    # Similarities should be equal (with tolerance for floating point)
    assert abs(original_similarity - scaled_similarity) < 1e-9, \
        f"Cosine similarity is not scale-invariant: original={original_similarity}, scaled={scaled_similarity}"


def test_cosine_similarity_orthogonal_vectors():
    """
    Property 8: Cosine Similarity Calculation (Edge Case - Orthogonal Vectors)
    
    For orthogonal taste vectors (dot product = 0), the cosine similarity must be 0.0.
    """
    # Create orthogonal vectors in 2D subspace for simplicity
    # Vector A: all weight on danceability
    vector_a = {
        'danceability': 1.0,
        'energy': 0.0,
        'valence': 0.0,
        'acousticness': 0.0,
        'instrumentalness': 0.0,
        'speechiness': 0.0,
        'tempo_normalized': 0.0
    }
    
    # Vector B: all weight on energy (orthogonal to A)
    vector_b = {
        'danceability': 0.0,
        'energy': 1.0,
        'valence': 0.0,
        'acousticness': 0.0,
        'instrumentalness': 0.0,
        'speechiness': 0.0,
        'tempo_normalized': 0.0
    }
    
    similarity = cosine_similarity(vector_a, vector_b)
    
    # Orthogonal vectors should have similarity of 0.0
    assert abs(similarity - 0.0) < 1e-9, \
        f"Orthogonal vectors should have similarity 0.0, got {similarity}"


@settings(max_examples=100)
@given(vector=taste_vector_strategy())
def test_cosine_similarity_with_partial_overlap(vector):
    """
    Property 8: Cosine Similarity Calculation (Partial Key Overlap)
    
    For taste vectors with only partial key overlap, the cosine similarity
    should only consider common keys.
    """
    # Create a vector with only some keys
    partial_vector = {
        'danceability': vector['danceability'],
        'energy': vector['energy'],
        'valence': vector['valence']
    }
    
    # Calculate similarity
    similarity = cosine_similarity(vector, partial_vector)
    
    # Calculate expected similarity using only common keys
    common_keys = set(partial_vector.keys())
    expected_similarity = calculate_expected_cosine_similarity(
        {k: vector[k] for k in common_keys},
        partial_vector
    )
    
    assert abs(similarity - expected_similarity) < 1e-9, \
        f"Partial overlap similarity mismatch: expected {expected_similarity}, got {similarity}"


def test_cosine_similarity_empty_vectors():
    """
    Property 8: Cosine Similarity Calculation (Edge Case - Empty Vectors)
    
    For taste vectors with no common keys, the cosine similarity must be 0.0.
    """
    vector_a = {'danceability': 0.5, 'energy': 0.6}
    vector_b = {'valence': 0.7, 'acousticness': 0.3}
    
    similarity = cosine_similarity(vector_a, vector_b)
    
    assert similarity == 0.0, \
        f"Vectors with no common keys should have similarity 0.0, got {similarity}"


@settings(max_examples=100)
@given(
    vector_a=taste_vector_strategy(),
    vector_b=taste_vector_strategy()
)
def test_cosine_similarity_returns_float(vector_a, vector_b):
    """
    Property 8: Cosine Similarity Calculation (Type Property)
    
    For any two taste vectors, the cosine similarity must return a float value.
    """
    similarity = cosine_similarity(vector_a, vector_b)
    
    assert isinstance(similarity, float), \
        f"Cosine similarity should return float, got {type(similarity)}"
