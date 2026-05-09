"""Spotify API client for fetching user listening data.

This module provides a client for interacting with the Spotify Web API,
including methods to fetch user top tracks, top artists, and audio features.
Implements retry logic with exponential backoff for transient errors.
"""

import time
import logging
from typing import Optional, List, Dict, Any
import requests
from requests.exceptions import RequestException, Timeout


# Configure logging
logger = logging.getLogger(__name__)


class SpotifyAPIError(Exception):
    """Base exception for Spotify API errors."""
    pass


class SpotifyClient:
    """Client for interacting with the Spotify Web API."""
    
    BASE_URL = "https://api.spotify.com/v1"
    MAX_RETRIES = 3
    INITIAL_BACKOFF = 1  # seconds
    
    def __init__(self, access_token: str):
        """
        Initialize the Spotify client.
        
        Args:
            access_token: Valid Spotify access token for API requests
            
        Raises:
            ValueError: If access_token is empty or None
        """
        if not access_token:
            raise ValueError("Access token cannot be empty or None")
        
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        })
    
    def _is_transient_error(self, status_code: int) -> bool:
        """
        Check if an HTTP status code represents a transient error.
        
        Args:
            status_code: HTTP status code
            
        Returns:
            True if the error is transient and should be retried
        """
        # 5xx server errors and 429 rate limiting are transient
        return status_code >= 500 or status_code == 429
    
    def _make_request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make an HTTP request with exponential backoff retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to request
            **kwargs: Additional arguments to pass to requests
            
        Returns:
            JSON response as dictionary
            
        Raises:
            SpotifyAPIError: If request fails after all retries
        """
        last_exception = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.session.request(method, url, timeout=10, **kwargs)
                
                # Check for successful response
                if response.status_code == 200:
                    return response.json()
                
                # Check if error is transient
                if self._is_transient_error(response.status_code):
                    if attempt < self.MAX_RETRIES - 1:
                        # Calculate exponential backoff delay
                        delay = self.INITIAL_BACKOFF * (2 ** attempt)
                        logger.warning(
                            f"Spotify API request failed with status {response.status_code}. "
                            f"Retrying in {delay}s (attempt {attempt + 1}/{self.MAX_RETRIES})"
                        )
                        time.sleep(delay)
                        continue
                
                # Non-transient error or final retry attempt
                error_msg = f"Spotify API error: {response.status_code}"
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_msg += f" - {error_data['error'].get('message', '')}"
                except:
                    error_msg += f" - {response.text}"
                
                raise SpotifyAPIError(error_msg)
                
            except (Timeout, RequestException) as e:
                last_exception = e
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.INITIAL_BACKOFF * (2 ** attempt)
                    logger.warning(
                        f"Spotify API request failed with {type(e).__name__}. "
                        f"Retrying in {delay}s (attempt {attempt + 1}/{self.MAX_RETRIES})"
                    )
                    time.sleep(delay)
                    continue
                else:
                    raise SpotifyAPIError(f"Request failed after {self.MAX_RETRIES} retries: {e}")
        
        # Should not reach here, but just in case
        if last_exception:
            raise SpotifyAPIError(f"Request failed: {last_exception}")
        raise SpotifyAPIError("Request failed for unknown reason")
    
    def get_user_top_tracks(
        self,
        time_range: str = "medium_term",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Fetch user's top tracks from Spotify.
        
        Args:
            time_range: Time range for top tracks (short_term, medium_term, long_term)
            limit: Maximum number of tracks to return (max 50)
            
        Returns:
            List of track objects from Spotify API
            
        Raises:
            SpotifyAPIError: If request fails after retries
            ValueError: If limit is invalid
        """
        if limit < 1 or limit > 50:
            raise ValueError("Limit must be between 1 and 50")
        
        if time_range not in ["short_term", "medium_term", "long_term"]:
            raise ValueError("Invalid time_range. Must be short_term, medium_term, or long_term")
        
        url = f"{self.BASE_URL}/me/top/tracks"
        params = {
            "time_range": time_range,
            "limit": limit
        }
        
        logger.info(f"Fetching user top tracks (limit={limit}, time_range={time_range})")
        response = self._make_request_with_retry("GET", url, params=params)
        
        tracks = response.get("items", [])
        logger.info(f"Successfully fetched {len(tracks)} top tracks")
        return tracks
    
    def get_user_top_artists(
        self,
        time_range: str = "medium_term",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Fetch user's top artists from Spotify.
        
        Args:
            time_range: Time range for top artists (short_term, medium_term, long_term)
            limit: Maximum number of artists to return (max 50)
            
        Returns:
            List of artist objects from Spotify API
            
        Raises:
            SpotifyAPIError: If request fails after retries
            ValueError: If limit is invalid
        """
        if limit < 1 or limit > 50:
            raise ValueError("Limit must be between 1 and 50")
        
        if time_range not in ["short_term", "medium_term", "long_term"]:
            raise ValueError("Invalid time_range. Must be short_term, medium_term, or long_term")
        
        url = f"{self.BASE_URL}/me/top/artists"
        params = {
            "time_range": time_range,
            "limit": limit
        }
        
        logger.info(f"Fetching user top artists (limit={limit}, time_range={time_range})")
        response = self._make_request_with_retry("GET", url, params=params)
        
        artists = response.get("items", [])
        logger.info(f"Successfully fetched {len(artists)} top artists")
        return artists
    
    def get_audio_features(self, track_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch audio features for multiple tracks.
        
        Args:
            track_ids: List of Spotify track IDs (max 100 per request)
            
        Returns:
            List of audio feature objects from Spotify API
            
        Raises:
            SpotifyAPIError: If request fails after retries
            ValueError: If track_ids is empty or too large
        """
        if not track_ids:
            raise ValueError("track_ids cannot be empty")
        
        if len(track_ids) > 100:
            raise ValueError("Maximum 100 track IDs per request")
        
        url = f"{self.BASE_URL}/audio-features"
        params = {
            "ids": ",".join(track_ids)
        }
        
        logger.info(f"Fetching audio features for {len(track_ids)} tracks")
        response = self._make_request_with_retry("GET", url, params=params)
        
        features = response.get("audio_features", [])
        # Filter out None values (tracks that don't have audio features)
        features = [f for f in features if f is not None]
        logger.info(f"Successfully fetched audio features for {len(features)} tracks")
        return features
