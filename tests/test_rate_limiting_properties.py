"""Property-based tests for rate limiting.

Feature: jamr-io-mvp
Tests rate limiting properties using sliding window algorithm.
"""

import pytest
import time
from hypothesis import given, strategies as st, settings
from backend.rate_limiter import RateLimiter, get_rate_limiter


# Property 51: Rate Limiting
# **Validates: Requirements 15.6**
@settings(max_examples=50)
@given(
    max_requests=st.integers(min_value=1, max_value=20),
    user_id=st.integers(min_value=1, max_value=1000)
)
def test_rate_limiting_enforces_max_requests(max_requests, user_id):
    """
    Property 51: Rate Limiting (Part 1 - Max Requests Enforcement)
    
    For any API endpoint, if a user makes more than the configured maximum requests
    per time window, the platform must reject subsequent requests.
    """
    limiter = RateLimiter(max_requests=max_requests, window_seconds=60)
    
    # Make exactly max_requests requests - all should succeed
    for i in range(max_requests):
        result = limiter.check_rate_limit(user_id)
        assert result is True, f"Request {i+1}/{max_requests} should be allowed"
    
    # The next request should be rejected
    result = limiter.check_rate_limit(user_id)
    assert result is False, f"Request {max_requests+1} should be rejected (limit: {max_requests})"


@settings(max_examples=50)
@given(
    max_requests=st.integers(min_value=5, max_value=20),
    num_requests=st.integers(min_value=1, max_value=4),
    user_id=st.integers(min_value=1, max_value=1000)
)
def test_rate_limiting_allows_requests_within_limit(max_requests, num_requests, user_id):
    """
    Property 51: Rate Limiting (Part 2 - Requests Within Limit Allowed)
    
    For any API endpoint, if a user makes fewer than the maximum requests
    per time window, all requests should be allowed.
    """
    limiter = RateLimiter(max_requests=max_requests, window_seconds=60)
    
    # Make num_requests requests (which is less than max_requests)
    for i in range(num_requests):
        result = limiter.check_rate_limit(user_id)
        assert result is True, f"Request {i+1}/{num_requests} should be allowed (limit: {max_requests})"


@settings(max_examples=30)
@given(
    user_id1=st.integers(min_value=1, max_value=500),
    user_id2=st.integers(min_value=501, max_value=1000)
)
def test_rate_limiting_isolates_users(user_id1, user_id2):
    """
    Property 51: Rate Limiting (Part 3 - User Isolation)
    
    Rate limits should be enforced per user. One user hitting the rate limit
    should not affect other users.
    """
    max_requests = 5
    limiter = RateLimiter(max_requests=max_requests, window_seconds=60)
    
    # User 1 exhausts their rate limit
    for i in range(max_requests):
        result = limiter.check_rate_limit(user_id1)
        assert result is True
    
    # User 1's next request should be rejected
    result = limiter.check_rate_limit(user_id1)
    assert result is False
    
    # User 2 should still be able to make requests
    result = limiter.check_rate_limit(user_id2)
    assert result is True, "User 2 should not be affected by User 1's rate limit"


def test_rate_limiting_sliding_window():
    """
    Property 51: Rate Limiting (Part 4 - Sliding Window)
    
    The rate limiter should use a sliding window algorithm, where old requests
    outside the time window are not counted.
    """
    max_requests = 3
    window_seconds = 1  # 1 second window for faster testing
    limiter = RateLimiter(max_requests=max_requests, window_seconds=window_seconds)
    user_id = 1
    
    # Make max_requests requests
    for i in range(max_requests):
        result = limiter.check_rate_limit(user_id)
        assert result is True
    
    # Next request should be rejected
    result = limiter.check_rate_limit(user_id)
    assert result is False
    
    # Wait for the window to expire
    time.sleep(window_seconds + 0.1)
    
    # Now requests should be allowed again
    result = limiter.check_rate_limit(user_id)
    assert result is True, "Requests should be allowed after window expires"


def test_rate_limiting_get_remaining_requests():
    """
    Property 51: Rate Limiting (Part 5 - Remaining Requests)
    
    The rate limiter should accurately report the number of remaining requests.
    """
    max_requests = 10
    limiter = RateLimiter(max_requests=max_requests, window_seconds=60)
    user_id = 1
    
    # Initially, all requests should be available
    remaining = limiter.get_remaining_requests(user_id)
    assert remaining == max_requests
    
    # Make 3 requests
    for i in range(3):
        limiter.check_rate_limit(user_id)
    
    # Should have 7 remaining
    remaining = limiter.get_remaining_requests(user_id)
    assert remaining == 7
    
    # Make 7 more requests
    for i in range(7):
        limiter.check_rate_limit(user_id)
    
    # Should have 0 remaining
    remaining = limiter.get_remaining_requests(user_id)
    assert remaining == 0


def test_rate_limiting_reset_user():
    """
    Property 51: Rate Limiting (Part 6 - User Reset)
    
    The rate limiter should allow resetting a specific user's rate limit.
    """
    max_requests = 5
    limiter = RateLimiter(max_requests=max_requests, window_seconds=60)
    user_id = 1
    
    # Exhaust the rate limit
    for i in range(max_requests):
        limiter.check_rate_limit(user_id)
    
    # Next request should be rejected
    result = limiter.check_rate_limit(user_id)
    assert result is False
    
    # Reset the user
    limiter.reset_user(user_id)
    
    # Now requests should be allowed again
    result = limiter.check_rate_limit(user_id)
    assert result is True


def test_rate_limiting_clear_all():
    """
    Property 51: Rate Limiting (Part 7 - Clear All)
    
    The rate limiter should allow clearing all rate limit data.
    """
    max_requests = 5
    limiter = RateLimiter(max_requests=max_requests, window_seconds=60)
    
    # Make requests for multiple users
    for user_id in [1, 2, 3]:
        for i in range(max_requests):
            limiter.check_rate_limit(user_id)
    
    # All users should be at their limit
    for user_id in [1, 2, 3]:
        result = limiter.check_rate_limit(user_id)
        assert result is False
    
    # Clear all data
    limiter.clear_all()
    
    # All users should be able to make requests again
    for user_id in [1, 2, 3]:
        result = limiter.check_rate_limit(user_id)
        assert result is True


def test_rate_limiting_thread_safety():
    """
    Property 51: Rate Limiting (Part 8 - Thread Safety)
    
    The rate limiter should be thread-safe and handle concurrent requests correctly.
    """
    import threading
    
    max_requests = 100
    limiter = RateLimiter(max_requests=max_requests, window_seconds=60)
    user_id = 1
    
    results = []
    
    def make_request():
        result = limiter.check_rate_limit(user_id)
        results.append(result)
    
    # Create 150 threads (50 more than the limit)
    threads = []
    for i in range(150):
        thread = threading.Thread(target=make_request)
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # Exactly max_requests should have succeeded
    successful_requests = sum(1 for r in results if r is True)
    assert successful_requests == max_requests, f"Expected {max_requests} successful requests, got {successful_requests}"
    
    # The rest should have failed
    failed_requests = sum(1 for r in results if r is False)
    assert failed_requests == 50, f"Expected 50 failed requests, got {failed_requests}"


def test_get_rate_limiter_singleton():
    """
    Property 51: Rate Limiting (Part 9 - Singleton)
    
    The get_rate_limiter function should return the same instance.
    """
    limiter1 = get_rate_limiter()
    limiter2 = get_rate_limiter()
    
    assert limiter1 is limiter2, "get_rate_limiter should return the same instance"


@settings(max_examples=50)
@given(
    max_requests=st.integers(min_value=1, max_value=20),
    window_seconds=st.integers(min_value=1, max_value=10)
)
def test_rate_limiting_configurable_parameters(max_requests, window_seconds):
    """
    Property 51: Rate Limiting (Part 10 - Configurable Parameters)
    
    The rate limiter should respect the configured max_requests and window_seconds.
    """
    limiter = RateLimiter(max_requests=max_requests, window_seconds=window_seconds)
    user_id = 1
    
    # Make exactly max_requests requests
    for i in range(max_requests):
        result = limiter.check_rate_limit(user_id)
        assert result is True
    
    # The next request should be rejected
    result = limiter.check_rate_limit(user_id)
    assert result is False
