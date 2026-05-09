"""Unit tests for Spotify API client."""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from requests.exceptions import Timeout, RequestException
from backend.spotify_client import SpotifyClient, SpotifyAPIError


class TestSpotifyClientInitialization:
    """Tests for SpotifyClient initialization."""
    
    def test_init_with_valid_token(self):
        """Test initialization with valid access token."""
        client = SpotifyClient("valid_token_123")
        assert client.access_token == "valid_token_123"
        assert client.session.headers['Authorization'] == 'Bearer valid_token_123'
    
    def test_init_with_empty_token_raises_error(self):
        """Test initialization with empty token raises ValueError."""
        with pytest.raises(ValueError, match="Access token cannot be empty or None"):
            SpotifyClient("")
    
    def test_init_with_none_token_raises_error(self):
        """Test initialization with None token raises ValueError."""
        with pytest.raises(ValueError, match="Access token cannot be empty or None"):
            SpotifyClient(None)


class TestTransientErrorDetection:
    """Tests for transient error detection."""
    
    def test_5xx_errors_are_transient(self):
        """Test that 5xx status codes are identified as transient."""
        client = SpotifyClient("token")
        assert client._is_transient_error(500) is True
        assert client._is_transient_error(502) is True
        assert client._is_transient_error(503) is True
        assert client._is_transient_error(504) is True
    
    def test_429_is_transient(self):
        """Test that 429 (rate limit) is identified as transient."""
        client = SpotifyClient("token")
        assert client._is_transient_error(429) is True
    
    def test_4xx_errors_are_not_transient(self):
        """Test that 4xx errors (except 429) are not transient."""
        client = SpotifyClient("token")
        assert client._is_transient_error(400) is False
        assert client._is_transient_error(401) is False
        assert client._is_transient_error(403) is False
        assert client._is_transient_error(404) is False


class TestGetUserTopTracks:
    """Tests for get_user_top_tracks method."""
    
    @patch('backend.spotify_client.requests.Session.request')
    def test_successful_fetch(self, mock_request):
        """Test successful fetch of top tracks."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {"id": "track1", "name": "Song 1"},
                {"id": "track2", "name": "Song 2"}
            ]
        }
        mock_request.return_value = mock_response
        
        client = SpotifyClient("token")
        tracks = client.get_user_top_tracks(limit=2)
        
        assert len(tracks) == 2
        assert tracks[0]["id"] == "track1"
        assert tracks[1]["id"] == "track2"
        mock_request.assert_called_once()
    
    @patch('backend.spotify_client.requests.Session.request')
    def test_default_parameters(self, mock_request):
        """Test that default parameters are used correctly."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}
        mock_request.return_value = mock_response
        
        client = SpotifyClient("token")
        client.get_user_top_tracks()
        
        # Check that the request was made with default parameters
        call_args = mock_request.call_args
        assert call_args[1]['params']['limit'] == 50
        assert call_args[1]['params']['time_range'] == 'medium_term'
    
    def test_invalid_limit_raises_error(self):
        """Test that invalid limit raises ValueError."""
        client = SpotifyClient("token")
        
        with pytest.raises(ValueError, match="Limit must be between 1 and 50"):
            client.get_user_top_tracks(limit=0)
        
        with pytest.raises(ValueError, match="Limit must be between 1 and 50"):
            client.get_user_top_tracks(limit=51)
    
    def test_invalid_time_range_raises_error(self):
        """Test that invalid time_range raises ValueError."""
        client = SpotifyClient("token")
        
        with pytest.raises(ValueError, match="Invalid time_range"):
            client.get_user_top_tracks(time_range="invalid")


class TestGetUserTopArtists:
    """Tests for get_user_top_artists method."""
    
    @patch('backend.spotify_client.requests.Session.request')
    def test_successful_fetch(self, mock_request):
        """Test successful fetch of top artists."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {"id": "artist1", "name": "Artist 1"},
                {"id": "artist2", "name": "Artist 2"}
            ]
        }
        mock_request.return_value = mock_response
        
        client = SpotifyClient("token")
        artists = client.get_user_top_artists(limit=2)
        
        assert len(artists) == 2
        assert artists[0]["id"] == "artist1"
        assert artists[1]["id"] == "artist2"
    
    def test_invalid_limit_raises_error(self):
        """Test that invalid limit raises ValueError."""
        client = SpotifyClient("token")
        
        with pytest.raises(ValueError, match="Limit must be between 1 and 50"):
            client.get_user_top_artists(limit=0)
        
        with pytest.raises(ValueError, match="Limit must be between 1 and 50"):
            client.get_user_top_artists(limit=51)


class TestGetAudioFeatures:
    """Tests for get_audio_features method."""
    
    @patch('backend.spotify_client.requests.Session.request')
    def test_successful_fetch(self, mock_request):
        """Test successful fetch of audio features."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "audio_features": [
                {"id": "track1", "danceability": 0.8, "energy": 0.7},
                {"id": "track2", "danceability": 0.6, "energy": 0.9}
            ]
        }
        mock_request.return_value = mock_response
        
        client = SpotifyClient("token")
        features = client.get_audio_features(["track1", "track2"])
        
        assert len(features) == 2
        assert features[0]["danceability"] == 0.8
        assert features[1]["energy"] == 0.9
    
    @patch('backend.spotify_client.requests.Session.request')
    def test_filters_none_values(self, mock_request):
        """Test that None values are filtered from audio features."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "audio_features": [
                {"id": "track1", "danceability": 0.8},
                None,  # Track without audio features
                {"id": "track3", "danceability": 0.6}
            ]
        }
        mock_request.return_value = mock_response
        
        client = SpotifyClient("token")
        features = client.get_audio_features(["track1", "track2", "track3"])
        
        assert len(features) == 2
        assert all(f is not None for f in features)
    
    def test_empty_track_ids_raises_error(self):
        """Test that empty track_ids raises ValueError."""
        client = SpotifyClient("token")
        
        with pytest.raises(ValueError, match="track_ids cannot be empty"):
            client.get_audio_features([])
    
    def test_too_many_track_ids_raises_error(self):
        """Test that more than 100 track IDs raises ValueError."""
        client = SpotifyClient("token")
        track_ids = [f"track{i}" for i in range(101)]
        
        with pytest.raises(ValueError, match="Maximum 100 track IDs per request"):
            client.get_audio_features(track_ids)


class TestRetryLogic:
    """Tests for retry logic with exponential backoff."""
    
    @patch('backend.spotify_client.time.sleep')
    @patch('backend.spotify_client.requests.Session.request')
    def test_retries_on_500_error(self, mock_request, mock_sleep):
        """Test that 500 errors trigger retries with exponential backoff."""
        # First two attempts fail with 500, third succeeds
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"items": []}
        
        mock_request.side_effect = [
            mock_response_fail,
            mock_response_fail,
            mock_response_success
        ]
        
        client = SpotifyClient("token")
        result = client.get_user_top_tracks()
        
        # Should have made 3 requests
        assert mock_request.call_count == 3
        
        # Should have slept twice with exponential backoff (1s, 2s)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)
    
    @patch('backend.spotify_client.time.sleep')
    @patch('backend.spotify_client.requests.Session.request')
    def test_retries_on_timeout(self, mock_request, mock_sleep):
        """Test that timeout errors trigger retries."""
        # First attempt times out, second succeeds
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"items": []}
        
        mock_request.side_effect = [
            Timeout("Connection timeout"),
            mock_response_success
        ]
        
        client = SpotifyClient("token")
        result = client.get_user_top_tracks()
        
        assert mock_request.call_count == 2
        assert mock_sleep.call_count == 1
        mock_sleep.assert_called_with(1)
    
    @patch('backend.spotify_client.time.sleep')
    @patch('backend.spotify_client.requests.Session.request')
    def test_fails_after_max_retries(self, mock_request, mock_sleep):
        """Test that request fails after MAX_RETRIES attempts."""
        mock_response_fail = Mock()
        mock_response_fail.status_code = 503
        mock_request.return_value = mock_response_fail
        
        client = SpotifyClient("token")
        
        with pytest.raises(SpotifyAPIError):
            client.get_user_top_tracks()
        
        # Should have made 3 attempts
        assert mock_request.call_count == 3
        
        # Should have slept twice (between attempts)
        assert mock_sleep.call_count == 2
    
    @patch('backend.spotify_client.requests.Session.request')
    def test_no_retry_on_400_error(self, mock_request):
        """Test that 400 errors do not trigger retries."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": {"message": "Bad request"}}
        mock_request.return_value = mock_response
        
        client = SpotifyClient("token")
        
        with pytest.raises(SpotifyAPIError, match="400"):
            client.get_user_top_tracks()
        
        # Should only make one request (no retries)
        assert mock_request.call_count == 1
    
    @patch('backend.spotify_client.time.sleep')
    @patch('backend.spotify_client.requests.Session.request')
    def test_exponential_backoff_delays(self, mock_request, mock_sleep):
        """Test that exponential backoff uses correct delays (1s, 2s, 4s)."""
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        mock_request.return_value = mock_response_fail
        
        client = SpotifyClient("token")
        
        with pytest.raises(SpotifyAPIError):
            client.get_user_top_tracks()
        
        # Check that sleep was called with exponential delays
        assert mock_sleep.call_count == 2
        calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert calls == [1, 2]  # 1s, 2s (third attempt fails without sleep)
