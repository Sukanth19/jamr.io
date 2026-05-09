"""Property-based tests for Spotify API retry logic.

Feature: jamr-io-mvp
Tests that Spotify API requests retry with exponential backoff for transient errors.
"""

import pytest
from unittest.mock import Mock, patch
from hypothesis import given, strategies as st, settings
from requests.exceptions import Timeout, RequestException, ConnectionError
from backend.spotify_client import SpotifyClient, SpotifyAPIError


# Feature: jamr-io-mvp, Property 45: Spotify API Retry Logic
# **Validates: Requirements 14.1**


@settings(max_examples=100)
@given(
    status_code=st.sampled_from([500, 501, 502, 503, 504, 429]),
    num_failures=st.integers(min_value=1, max_value=2)
)
@patch('backend.spotify_client.time.sleep')
@patch('backend.spotify_client.requests.Session.request')
def test_spotify_api_retries_on_transient_errors(mock_request, mock_sleep, status_code, num_failures):
    """
    Property 45: Spotify API Retry Logic (Part 1 - Transient Error Retries)
    
    For any Spotify API request that fails with a transient error (5xx status, 429),
    the platform must retry the request up to 3 times with exponential backoff.
    
    This test verifies that transient errors trigger retries and eventually succeed.
    """
    # Create mock responses: num_failures failures, then success
    mock_response_fail = Mock()
    mock_response_fail.status_code = status_code
    
    mock_response_success = Mock()
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = {"items": [{"id": "track1"}]}
    
    # Set up side effects: failures followed by success
    side_effects = [mock_response_fail] * num_failures + [mock_response_success]
    mock_request.side_effect = side_effects
    
    # Make request
    client = SpotifyClient("test_token")
    result = client.get_user_top_tracks(limit=1)
    
    # Verify success
    assert result == [{"id": "track1"}]
    
    # Verify correct number of attempts
    assert mock_request.call_count == num_failures + 1
    
    # Verify exponential backoff was used
    assert mock_sleep.call_count == num_failures
    expected_delays = [1 * (2 ** i) for i in range(num_failures)]
    actual_delays = [call[0][0] for call in mock_sleep.call_args_list]
    assert actual_delays == expected_delays


@settings(max_examples=100)
@given(
    exception_type=st.sampled_from([Timeout, ConnectionError, RequestException])
)
@patch('backend.spotify_client.time.sleep')
@patch('backend.spotify_client.requests.Session.request')
def test_spotify_api_retries_on_network_errors(mock_request, mock_sleep, exception_type):
    """
    Property 45: Spotify API Retry Logic (Part 2 - Network Error Retries)
    
    For any Spotify API request that fails with a network error (timeout, connection error),
    the platform must retry the request up to 3 times with exponential backoff.
    """
    # First attempt raises exception, second succeeds
    mock_response_success = Mock()
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = {"items": []}
    
    mock_request.side_effect = [
        exception_type("Network error"),
        mock_response_success
    ]
    
    # Make request
    client = SpotifyClient("test_token")
    result = client.get_user_top_tracks()
    
    # Verify success after retry
    assert result == []
    assert mock_request.call_count == 2
    
    # Verify exponential backoff (1 second for first retry)
    assert mock_sleep.call_count == 1
    mock_sleep.assert_called_with(1)


@patch('backend.spotify_client.time.sleep')
@patch('backend.spotify_client.requests.Session.request')
def test_spotify_api_exponential_backoff_delays(mock_request, mock_sleep):
    """
    Property 45: Spotify API Retry Logic (Part 3 - Exponential Backoff Delays)
    
    For any Spotify API request that fails with transient errors, the platform must
    use exponential backoff with delays of 1s, 2s, 4s between retries.
    """
    # All attempts fail to test all backoff delays
    mock_response_fail = Mock()
    mock_response_fail.status_code = 503
    mock_request.return_value = mock_response_fail
    
    client = SpotifyClient("test_token")
    
    # Request should fail after all retries
    with pytest.raises(SpotifyAPIError):
        client.get_user_top_tracks()
    
    # Verify 3 attempts were made
    assert mock_request.call_count == 3
    
    # Verify exponential backoff delays: 1s, 2s (no sleep after 3rd attempt)
    assert mock_sleep.call_count == 2
    delays = [call[0][0] for call in mock_sleep.call_args_list]
    assert delays == [1, 2], f"Expected delays [1, 2], got {delays}"


@settings(max_examples=100)
@given(
    status_code=st.integers(min_value=400, max_value=499).filter(lambda x: x != 429)
)
@patch('backend.spotify_client.time.sleep')
@patch('backend.spotify_client.requests.Session.request')
def test_spotify_api_no_retry_on_non_transient_errors(mock_request, mock_sleep, status_code):
    """
    Property 45: Spotify API Retry Logic (Part 4 - No Retry for Non-Transient Errors)
    
    For any Spotify API request that fails with a non-transient error (4xx except 429),
    the platform must NOT retry the request.
    """
    mock_response = Mock()
    mock_response.status_code = status_code
    mock_response.json.return_value = {"error": {"message": "Client error"}}
    mock_request.return_value = mock_response
    
    client = SpotifyClient("test_token")
    
    # Request should fail immediately without retries
    with pytest.raises(SpotifyAPIError):
        client.get_user_top_tracks()
    
    # Verify only 1 attempt was made (no retries)
    assert mock_request.call_count == 1
    
    # Verify no sleep was called (no backoff)
    assert mock_sleep.call_count == 0


@settings(max_examples=100)
@given(
    method_name=st.sampled_from(['get_user_top_tracks', 'get_user_top_artists'])
)
@patch('backend.spotify_client.time.sleep')
@patch('backend.spotify_client.requests.Session.request')
def test_spotify_api_retry_logic_applies_to_all_methods(mock_request, mock_sleep, method_name):
    """
    Property 45: Spotify API Retry Logic (Part 5 - Retry Logic for All Methods)
    
    For any Spotify API method, the retry logic with exponential backoff must be applied
    consistently across all API calls.
    """
    # First attempt fails with 500, second succeeds
    mock_response_fail = Mock()
    mock_response_fail.status_code = 500
    
    mock_response_success = Mock()
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = {"items": []}
    
    mock_request.side_effect = [mock_response_fail, mock_response_success]
    
    client = SpotifyClient("test_token")
    method = getattr(client, method_name)
    
    # Call the method
    result = method()
    
    # Verify retry occurred
    assert mock_request.call_count == 2
    assert mock_sleep.call_count == 1
    mock_sleep.assert_called_with(1)


@patch('backend.spotify_client.time.sleep')
@patch('backend.spotify_client.requests.Session.request')
def test_spotify_api_max_three_retries(mock_request, mock_sleep):
    """
    Property 45: Spotify API Retry Logic (Part 6 - Maximum 3 Attempts)
    
    For any Spotify API request that continuously fails with transient errors,
    the platform must make exactly 3 attempts (initial + 2 retries) before giving up.
    """
    # All attempts fail
    mock_response_fail = Mock()
    mock_response_fail.status_code = 502
    mock_request.return_value = mock_response_fail
    
    client = SpotifyClient("test_token")
    
    with pytest.raises(SpotifyAPIError):
        client.get_user_top_tracks()
    
    # Verify exactly 3 attempts (initial + 2 retries)
    assert mock_request.call_count == 3, f"Expected 3 attempts, got {mock_request.call_count}"
    
    # Verify 2 sleep calls (between attempts)
    assert mock_sleep.call_count == 2


@settings(max_examples=100)
@given(
    track_count=st.integers(min_value=1, max_value=10)
)
@patch('backend.spotify_client.time.sleep')
@patch('backend.spotify_client.requests.Session.request')
def test_spotify_api_retry_preserves_request_parameters(mock_request, mock_sleep, track_count):
    """
    Property 45: Spotify API Retry Logic (Part 7 - Request Parameters Preserved)
    
    For any Spotify API request that is retried, the original request parameters
    must be preserved across all retry attempts.
    """
    # First attempt fails, second succeeds
    mock_response_fail = Mock()
    mock_response_fail.status_code = 503
    
    mock_response_success = Mock()
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = {"items": []}
    
    mock_request.side_effect = [mock_response_fail, mock_response_success]
    
    client = SpotifyClient("test_token")
    client.get_user_top_tracks(limit=track_count, time_range="short_term")
    
    # Verify both requests had the same parameters
    assert mock_request.call_count == 2
    
    for call in mock_request.call_args_list:
        params = call[1]['params']
        assert params['limit'] == track_count
        assert params['time_range'] == 'short_term'


@settings(max_examples=100)
@given(
    num_track_ids=st.integers(min_value=1, max_value=20)
)
@patch('backend.spotify_client.time.sleep')
@patch('backend.spotify_client.requests.Session.request')
def test_spotify_api_retry_for_audio_features(mock_request, mock_sleep, num_track_ids):
    """
    Property 45: Spotify API Retry Logic (Part 8 - Audio Features Retry)
    
    For any audio features request that fails with a transient error,
    the platform must retry with exponential backoff.
    """
    # First attempt fails with timeout, second succeeds
    mock_response_success = Mock()
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = {"audio_features": []}
    
    mock_request.side_effect = [
        Timeout("Request timeout"),
        mock_response_success
    ]
    
    client = SpotifyClient("test_token")
    track_ids = [f"track_{i}" for i in range(num_track_ids)]
    result = client.get_audio_features(track_ids)
    
    # Verify retry occurred
    assert mock_request.call_count == 2
    assert mock_sleep.call_count == 1
    mock_sleep.assert_called_with(1)


@settings(max_examples=100)
@given(
    failure_attempt=st.integers(min_value=1, max_value=3)
)
@patch('backend.spotify_client.time.sleep')
@patch('backend.spotify_client.requests.Session.request')
def test_spotify_api_succeeds_on_any_retry_attempt(mock_request, mock_sleep, failure_attempt):
    """
    Property 45: Spotify API Retry Logic (Part 9 - Success on Any Attempt)
    
    For any Spotify API request, if any retry attempt succeeds (1st, 2nd, or 3rd),
    the request should return successfully without further retries.
    """
    # Create failures up to failure_attempt, then success
    mock_response_fail = Mock()
    mock_response_fail.status_code = 500
    
    mock_response_success = Mock()
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = {"items": [{"id": "success"}]}
    
    side_effects = [mock_response_fail] * (failure_attempt - 1) + [mock_response_success]
    mock_request.side_effect = side_effects
    
    client = SpotifyClient("test_token")
    result = client.get_user_top_tracks()
    
    # Verify success
    assert result == [{"id": "success"}]
    
    # Verify correct number of attempts
    assert mock_request.call_count == failure_attempt
    
    # Verify correct number of sleeps (one less than attempts)
    assert mock_sleep.call_count == failure_attempt - 1


@settings(max_examples=100)
@given(
    status_code=st.sampled_from([500, 502, 503, 504])
)
@patch('backend.spotify_client.time.sleep')
@patch('backend.spotify_client.requests.Session.request')
def test_spotify_api_retry_raises_error_after_exhaustion(mock_request, mock_sleep, status_code):
    """
    Property 45: Spotify API Retry Logic (Part 10 - Error After Retry Exhaustion)
    
    For any Spotify API request that fails on all retry attempts, the platform must
    raise a SpotifyAPIError with appropriate error information.
    """
    # All attempts fail
    mock_response_fail = Mock()
    mock_response_fail.status_code = status_code
    mock_response_fail.json.return_value = {"error": {"message": "Server error"}}
    mock_request.return_value = mock_response_fail
    
    client = SpotifyClient("test_token")
    
    # Verify SpotifyAPIError is raised
    with pytest.raises(SpotifyAPIError) as exc_info:
        client.get_user_top_tracks()
    
    # Verify error message contains status code
    assert str(status_code) in str(exc_info.value)
    
    # Verify all retries were attempted
    assert mock_request.call_count == 3
    assert mock_sleep.call_count == 2
