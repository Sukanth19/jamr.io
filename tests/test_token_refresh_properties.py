"""Property-based tests for Spotify token refresh logic.

Feature: jamr-io-mvp
Tests token refresh functionality including retry logic and token updates.
"""

import pytest
from hypothesis import given, strategies as st, settings
from cryptography.fernet import Fernet
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from backend.models import User
from backend.encryption import get_encryptor
from backend.auth import refresh_spotify_token
from tests.conftest import get_test_session
from fastapi import HTTPException


# Generate a valid Fernet key for testing
TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def set_test_encryption_key(monkeypatch):
    """Set a test encryption key for all tests in this module."""
    monkeypatch.setenv('ENCRYPTION_KEY', TEST_ENCRYPTION_KEY)
    monkeypatch.setenv('SPOTIFY_CLIENT_ID', 'test_client_id')
    monkeypatch.setenv('SPOTIFY_CLIENT_SECRET', 'test_client_secret')


# Custom strategies for generating token data
@st.composite
def token_data(draw):
    """Generate valid token data for testing."""
    return {
        "access_token": draw(st.text(min_size=50, max_size=200, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'), 
            whitelist_characters='-_.'
        ))),
        "refresh_token": draw(st.text(min_size=50, max_size=200, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'), 
            whitelist_characters='-_.'
        ))),
        "new_access_token": draw(st.text(min_size=50, max_size=200, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'), 
            whitelist_characters='-_.'
        ))),
        "expires_in": draw(st.integers(min_value=1800, max_value=7200))
    }


@st.composite
def user_data(draw):
    """Generate valid user data for testing."""
    import uuid
    
    return {
        "spotify_id": str(uuid.uuid4()),
        "display_name": draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
            min_codepoint=32,
            max_codepoint=126,
            blacklist_characters=['\x00']
        ))),
        "taste_vector": {
            "danceability": 0.5,
            "energy": 0.5,
            "valence": 0.5,
            "acousticness": 0.5,
            "instrumentalness": 0.5,
            "speechiness": 0.5,
            "tempo_normalized": 0.5
        }
    }


# Property 45: Spotify API Retry Logic (Token Refresh)
# **Validates: Requirements 14.1**
@settings(max_examples=100)
@given(user=user_data(), tokens=token_data())
def test_token_refresh_updates_encrypted_token_in_database(user, tokens):
    """
    Property 45: Spotify API Retry Logic (Token Refresh)
    
    For any Spotify API request that fails with 401 (token expired),
    the platform must use the refresh token to obtain a new access token
    and update the encrypted token in the database.
    
    This test verifies that:
    1. The refresh token is used to get a new access token
    2. The new access token is encrypted before storage
    3. The database is updated with the new encrypted token
    4. The new access token is returned for retry
    """
    db_session = get_test_session()
    encryptor = get_encryptor()
    
    try:
        # Create user with initial tokens
        initial_access_token_encrypted = encryptor.encrypt(tokens["access_token"])
        initial_refresh_token_encrypted = encryptor.encrypt(tokens["refresh_token"])
        initial_expires_at = datetime.now() - timedelta(hours=1)  # Expired token
        
        test_user = User(
            spotify_id=user["spotify_id"],
            display_name=user["display_name"],
            access_token_encrypted=initial_access_token_encrypted,
            refresh_token_encrypted=initial_refresh_token_encrypted,
            token_expires_at=initial_expires_at,
            taste_vector=user["taste_vector"]
        )
        
        db_session.add(test_user)
        db_session.commit()
        user_id = test_user.id
        
        # Mock Spotify token refresh response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": tokens["new_access_token"],
            "token_type": "Bearer",
            "expires_in": tokens["expires_in"],
            "scope": "user-read-email user-top-read"
        }
        
        # Mock httpx.Client
        with patch('backend.auth.httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client.post = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            # Call refresh_spotify_token
            new_access_token = refresh_spotify_token(user_id, db_session)
            
            # Verify the new access token is returned
            assert new_access_token == tokens["new_access_token"], \
                "New access token should be returned"
            
            # Verify Spotify API was called with correct parameters
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://accounts.spotify.com/api/token"
            assert call_args[1]["data"]["grant_type"] == "refresh_token"
            assert call_args[1]["data"]["refresh_token"] == tokens["refresh_token"]
            
            # Retrieve updated user from database
            updated_user = db_session.query(User).filter(User.id == user_id).first()
            
            # Verify access token was updated in database
            assert updated_user.access_token_encrypted != initial_access_token_encrypted, \
                "Access token should be updated in database"
            
            # Verify new token is encrypted (not plaintext)
            assert updated_user.access_token_encrypted != tokens["new_access_token"], \
                "New access token should be encrypted in database"
            
            # Verify new token can be decrypted to correct value
            decrypted_new_token = encryptor.decrypt(updated_user.access_token_encrypted)
            assert decrypted_new_token == tokens["new_access_token"], \
                "Decrypted token should match new access token"
            
            # Verify token expiration was updated
            assert updated_user.token_expires_at > initial_expires_at, \
                "Token expiration should be updated"
            
            # Verify expiration is approximately correct (within 10 seconds tolerance)
            expected_expires_at = datetime.now() + timedelta(seconds=tokens["expires_in"])
            time_diff = abs((updated_user.token_expires_at - expected_expires_at).total_seconds())
            assert time_diff < 10, \
                "Token expiration should be set correctly based on expires_in"
            
            # Verify refresh token is still stored (unchanged if not provided by Spotify)
            assert updated_user.refresh_token_encrypted == initial_refresh_token_encrypted, \
                "Refresh token should remain unchanged if not provided in response"
    
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=50)
@given(user=user_data(), tokens=token_data())
def test_token_refresh_updates_refresh_token_if_provided(user, tokens):
    """
    Verify that refresh token is updated if Spotify returns a new one.
    
    Spotify may optionally return a new refresh token in the response.
    If provided, it should be encrypted and stored.
    """
    db_session = get_test_session()
    encryptor = get_encryptor()
    
    try:
        # Create user with initial tokens
        initial_access_token_encrypted = encryptor.encrypt(tokens["access_token"])
        initial_refresh_token_encrypted = encryptor.encrypt(tokens["refresh_token"])
        
        test_user = User(
            spotify_id=user["spotify_id"],
            display_name=user["display_name"],
            access_token_encrypted=initial_access_token_encrypted,
            refresh_token_encrypted=initial_refresh_token_encrypted,
            token_expires_at=datetime.now() - timedelta(hours=1),
            taste_vector=user["taste_vector"]
        )
        
        db_session.add(test_user)
        db_session.commit()
        user_id = test_user.id
        
        # Generate a new refresh token
        new_refresh_token = tokens["refresh_token"] + "_new"
        
        # Mock Spotify response with new refresh token
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": tokens["new_access_token"],
            "refresh_token": new_refresh_token,  # New refresh token provided
            "token_type": "Bearer",
            "expires_in": tokens["expires_in"]
        }
        
        with patch('backend.auth.httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client.post = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            # Call refresh_spotify_token
            refresh_spotify_token(user_id, db_session)
            
            # Retrieve updated user
            updated_user = db_session.query(User).filter(User.id == user_id).first()
            
            # Verify refresh token was updated
            assert updated_user.refresh_token_encrypted != initial_refresh_token_encrypted, \
                "Refresh token should be updated when provided by Spotify"
            
            # Verify new refresh token is encrypted correctly
            decrypted_refresh_token = encryptor.decrypt(updated_user.refresh_token_encrypted)
            assert decrypted_refresh_token == new_refresh_token, \
                "Decrypted refresh token should match new refresh token"
    
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=50)
@given(user=user_data(), tokens=token_data())
def test_token_refresh_fails_when_no_refresh_token(user, tokens):
    """
    Verify that token refresh fails gracefully when user has no refresh token.
    
    If a user doesn't have a refresh token stored, the function should
    raise an appropriate error asking them to re-authenticate.
    """
    db_session = get_test_session()
    encryptor = get_encryptor()
    
    try:
        # Create user WITHOUT refresh token
        test_user = User(
            spotify_id=user["spotify_id"],
            display_name=user["display_name"],
            access_token_encrypted=encryptor.encrypt(tokens["access_token"]),
            refresh_token_encrypted=None,  # No refresh token
            token_expires_at=datetime.now() - timedelta(hours=1),
            taste_vector=user["taste_vector"]
        )
        
        db_session.add(test_user)
        db_session.commit()
        user_id = test_user.id
        
        # Attempt to refresh token should fail
        with pytest.raises(HTTPException) as exc_info:
            refresh_spotify_token(user_id, db_session)
        
        # Verify error details
        assert exc_info.value.status_code == 400
        assert "NO_REFRESH_TOKEN" in str(exc_info.value.detail)
    
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=50)
@given(user=user_data(), tokens=token_data())
def test_token_refresh_fails_when_spotify_returns_error(user, tokens):
    """
    Verify that token refresh fails gracefully when Spotify returns an error.
    
    If Spotify returns a non-200 status (e.g., refresh token expired),
    the function should raise an appropriate error.
    """
    db_session = get_test_session()
    encryptor = get_encryptor()
    
    try:
        # Create user with tokens
        test_user = User(
            spotify_id=user["spotify_id"],
            display_name=user["display_name"],
            access_token_encrypted=encryptor.encrypt(tokens["access_token"]),
            refresh_token_encrypted=encryptor.encrypt(tokens["refresh_token"]),
            token_expires_at=datetime.now() - timedelta(hours=1),
            taste_vector=user["taste_vector"]
        )
        
        db_session.add(test_user)
        db_session.commit()
        user_id = test_user.id
        
        # Mock Spotify error response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"error": "invalid_grant", "error_description": "Refresh token expired"}'
        mock_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Refresh token expired"
        }
        
        with patch('backend.auth.httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client.post = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            # Attempt to refresh token should fail
            with pytest.raises(HTTPException) as exc_info:
                refresh_spotify_token(user_id, db_session)
            
            # Verify error details
            assert exc_info.value.status_code == 401
            assert "TOKEN_REFRESH_FAILED" in str(exc_info.value.detail)
    
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=50)
@given(user=user_data(), tokens=token_data())
def test_token_refresh_fails_when_user_not_found(user, tokens):
    """
    Verify that token refresh fails when user doesn't exist.
    """
    db_session = get_test_session()
    
    try:
        # Use a non-existent user ID
        non_existent_user_id = 999999
        
        # Attempt to refresh token should fail
        with pytest.raises(HTTPException) as exc_info:
            refresh_spotify_token(non_existent_user_id, db_session)
        
        # Verify error details
        assert exc_info.value.status_code == 404
        assert "USER_NOT_FOUND" in str(exc_info.value.detail)
    
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=50)
@given(user=user_data(), tokens=token_data())
def test_token_refresh_preserves_other_user_fields(user, tokens):
    """
    Verify that token refresh only updates token-related fields.
    
    Other user fields (spotify_id, display_name, email, taste_vector)
    should remain unchanged after token refresh.
    """
    db_session = get_test_session()
    encryptor = get_encryptor()
    
    try:
        # Create user with all fields
        test_user = User(
            spotify_id=user["spotify_id"],
            display_name=user["display_name"],
            email="test@example.com",
            profile_image_url="https://example.com/image.jpg",
            access_token_encrypted=encryptor.encrypt(tokens["access_token"]),
            refresh_token_encrypted=encryptor.encrypt(tokens["refresh_token"]),
            token_expires_at=datetime.now() - timedelta(hours=1),
            taste_vector=user["taste_vector"]
        )
        
        db_session.add(test_user)
        db_session.commit()
        user_id = test_user.id
        
        # Store original values
        original_spotify_id = test_user.spotify_id
        original_display_name = test_user.display_name
        original_email = test_user.email
        original_profile_image_url = test_user.profile_image_url
        original_taste_vector = test_user.taste_vector
        
        # Mock Spotify response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": tokens["new_access_token"],
            "token_type": "Bearer",
            "expires_in": tokens["expires_in"]
        }
        
        with patch('backend.auth.httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client.post = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            # Call refresh_spotify_token
            refresh_spotify_token(user_id, db_session)
            
            # Retrieve updated user
            updated_user = db_session.query(User).filter(User.id == user_id).first()
            
            # Verify non-token fields are unchanged
            assert updated_user.spotify_id == original_spotify_id, \
                "Spotify ID should not change"
            assert updated_user.display_name == original_display_name, \
                "Display name should not change"
            assert updated_user.email == original_email, \
                "Email should not change"
            assert updated_user.profile_image_url == original_profile_image_url, \
                "Profile image URL should not change"
            assert updated_user.taste_vector == original_taste_vector, \
                "Taste vector should not change"
    
    finally:
        db_session.rollback()
        db_session.close()
