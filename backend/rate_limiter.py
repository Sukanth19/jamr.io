"""Rate limiting middleware using sliding window algorithm.

This module provides rate limiting functionality to prevent abuse
by limiting the number of requests a user can make within a time window.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List
import threading


class RateLimiter:
    """
    Rate limiter using sliding window algorithm.
    
    Tracks requests per user and enforces a maximum number of requests
    within a specified time window.
    """
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        """
        Initialize the rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed within the window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        
        # Store request timestamps per user
        # Key: user_id, Value: list of request timestamps
        self.requests: Dict[int, List[datetime]] = defaultdict(list)
        
        # Thread lock for thread-safe operations
        self._lock = threading.Lock()
    
    def check_rate_limit(self, user_id: int) -> bool:
        """
        Check if a user has exceeded the rate limit.
        
        This method uses a sliding window algorithm:
        1. Remove old requests outside the time window
        2. Check if the number of remaining requests exceeds the limit
        3. If not exceeded, add the current request timestamp
        
        Args:
            user_id: The ID of the user making the request
            
        Returns:
            True if the request is allowed (within rate limit)
            False if the request should be rejected (rate limit exceeded)
            
        Example:
            >>> limiter = RateLimiter(max_requests=10, window_seconds=60)
            >>> limiter.check_rate_limit(user_id=1)
            True
            >>> # After 10 requests within 60 seconds:
            >>> limiter.check_rate_limit(user_id=1)
            False
        """
        with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=self.window_seconds)
            
            # Remove old requests outside the time window
            self.requests[user_id] = [
                req_time for req_time in self.requests[user_id]
                if req_time > cutoff
            ]
            
            # Check if limit is exceeded
            if len(self.requests[user_id]) >= self.max_requests:
                return False
            
            # Add current request timestamp
            self.requests[user_id].append(now)
            return True
    
    def get_remaining_requests(self, user_id: int) -> int:
        """
        Get the number of remaining requests for a user within the current window.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            Number of remaining requests allowed
        """
        with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=self.window_seconds)
            
            # Count requests within the window
            recent_requests = [
                req_time for req_time in self.requests[user_id]
                if req_time > cutoff
            ]
            
            return max(0, self.max_requests - len(recent_requests))
    
    def reset_user(self, user_id: int) -> None:
        """
        Reset the rate limit for a specific user.
        
        This can be useful for testing or administrative purposes.
        
        Args:
            user_id: The ID of the user to reset
        """
        with self._lock:
            if user_id in self.requests:
                del self.requests[user_id]
    
    def clear_all(self) -> None:
        """
        Clear all rate limit data.
        
        This can be useful for testing or maintenance.
        """
        with self._lock:
            self.requests.clear()


# Global rate limiter instance
_rate_limiter = None


def get_rate_limiter(max_requests: int = 100, window_seconds: int = 60) -> RateLimiter:
    """
    Get the global rate limiter instance.
    
    Args:
        max_requests: Maximum number of requests allowed within the window
        window_seconds: Time window in seconds
        
    Returns:
        RateLimiter: The rate limiter instance
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(max_requests=max_requests, window_seconds=window_seconds)
    return _rate_limiter
