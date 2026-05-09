"""Unit tests for token refresh functionality."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
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


def test_refresh_token_success():
    """Test successful token refresh."""
    db_session = get_test_session()
    encryptor = get_encryptor()
    
    try:
        # Create user with tokens
        old_access_token = "old_access_token_12345"
        refresh_token = "refresh_token_67890"
        new_access_token = "new_access_token_abcde"
        
        test_user = User(
            spotify_id="test_user_123",
            display_name="Test User",
            access_token_encrypted=encryptor.encrypt(old_access_token),
            refresh_token_encrypted=encryptor.encrypt(refresh_token),
            token_expires_at=datetime.now() - timedelta(hours=1),
            taste_vector={
                "danceability": 0.5,
                "energy": 0.5,
                "valence": 0.5,
                "acousticness": 0.5,
                "instrumentalness": 0.5,
                "speechiness": 0.5,
                "tempo_normalized": 0.5
            }
        )
        
        db_session.add(test_user)
        db_session.commit()
        user_id = test_user.id
        
        # Mock Spotify response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": new_access_token,
            "token_type": "Bearer",
            "expires_in": 3600
        }
        
        with patch('backend.auth.httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client.post = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            # Call refresh_spotify_token
            result = refresh_spotify_token(user_id, db_session)
            
            # Verify result
            assert result == new_access_token
            
            # Verify database was updated
            updated_user = db_session.query(User).filter(User.id == user_id).first()
            decrypted_token = encryptor.decrypt(updated_user.access_token_encrypted)
            assert decrypted_token == new_access_token
            assert updated_user.token_expires_at > datetime.now()
    
    finally:
        db_session.rollback()
        db_session.close()


def test_refresh_token_no_refresh_token():
    """Test token refresh fails when user has no refresh token."""
    db_session = get_test_session()
    encryptor = get_encryptor()
    
    try:
        # Create user without refresh token
        test_user = User(
            spotify_id="test_user_456",
            display_name="Test User 2",
            access_token_encrypted=encryptor.encrypt("access_token"),
            refresh_token_encrypted=None,
            token_expires_at=datetime.now() - timedelta(hours=1),
            taste_vector={
                "danceability": 0.5,
                "energy": 0.5,
                "valence": 0.5,
                "acousticness": 0.5,
                "instrumentalness": 0.5,
                "speechiness": 0.5,
                "tempo_normalized": 0.5
            }
        )
        
        db_session.add(test_user)
        db_session.commit()
        user_id = test_user.id
        
        # Attempt to refresh should fail
        with pytest.raises(HTTPException) as exc_info:
            refresh_spotify_token(user_id, db_session)
        
        assert exc_info.value.status_code == 400
        assert "NO_REFRESH_TOKEN" in str(exc_info.value.detail)
    
    finally:
        db_session.rollback()
        db_session.close()


def test_refresh_token_user_not_found():
    """Test token refresh fails when user doesn't exist."""
    db_session = get_test_session()
    
    try:
        # Use non-existent user ID
        with pytest.raises(HTTPException) as exc_info:
            refresh_spotify_token(999999, db_session)
        
        assert exc_info.value.status_code == 404
        assert "USER_NOT_FOUND" in str(exc_info.value.detail)
    
    finally:
        db_session.rollback()
        db_session.close()
