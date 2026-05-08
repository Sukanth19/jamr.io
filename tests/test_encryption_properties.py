"""Property-based tests for token encryption.

Feature: jamr-io-mvp
Tests encryption and decryption properties for secure token storage.
"""

import pytest
import os
from hypothesis import given, strategies as st, settings
from cryptography.fernet import Fernet, InvalidToken
from backend.encryption import TokenEncryption, get_encryptor


# Generate a valid Fernet key for testing
TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def set_test_encryption_key(monkeypatch):
    """Set a test encryption key for all tests in this module."""
    monkeypatch.setenv('ENCRYPTION_KEY', TEST_ENCRYPTION_KEY)


# Property 1: Token Encryption
# **Validates: Requirements 1.3, 15.1**
@settings(max_examples=100)
@given(token=st.text(min_size=1, max_size=1000))
def test_token_encryption_roundtrip(token):
    """
    Property 1: Token Encryption
    
    For any Spotify access token, the token must be encrypted using Fernet 
    symmetric encryption before storage, and must be decryptable back to 
    the original value.
    """
    encryptor = TokenEncryption()
    
    # Encrypt the token
    encrypted = encryptor.encrypt(token)
    
    # Verify encrypted token is different from original (unless very short)
    assert encrypted != token
    
    # Verify encrypted token is a valid string
    assert isinstance(encrypted, str)
    assert len(encrypted) > 0
    
    # Decrypt the token
    decrypted = encryptor.decrypt(encrypted)
    
    # Verify decrypted token matches original
    assert decrypted == token


@settings(max_examples=100)
@given(token=st.text(min_size=1, max_size=1000))
def test_token_encryption_produces_different_ciphertext(token):
    """
    Verify that encryption produces ciphertext that differs from plaintext.
    
    This ensures tokens are actually being encrypted and not stored in plaintext.
    """
    encryptor = TokenEncryption()
    
    encrypted = encryptor.encrypt(token)
    
    # Encrypted token should not equal the original token
    assert encrypted != token
    
    # Encrypted token should be longer (Fernet adds overhead)
    # Fernet tokens are base64 encoded and include version, timestamp, IV, ciphertext, and HMAC
    assert len(encrypted) > len(token)


@settings(max_examples=100)
@given(token=st.text(min_size=1, max_size=1000))
def test_encrypted_token_is_deterministic_with_same_key(token):
    """
    Verify that the same token encrypted with the same key can be decrypted.
    
    Note: Fernet includes a timestamp, so the same plaintext will produce 
    different ciphertexts each time, but all should decrypt correctly.
    """
    encryptor = TokenEncryption()
    
    # Encrypt the same token multiple times
    encrypted1 = encryptor.encrypt(token)
    encrypted2 = encryptor.encrypt(token)
    
    # Ciphertexts will be different (Fernet includes timestamp)
    # But both should decrypt to the same original value
    decrypted1 = encryptor.decrypt(encrypted1)
    decrypted2 = encryptor.decrypt(encrypted2)
    
    assert decrypted1 == token
    assert decrypted2 == token


@settings(max_examples=50)
@given(token=st.text(min_size=1, max_size=1000))
def test_encrypted_token_cannot_be_decrypted_with_different_key(token):
    """
    Verify that a token encrypted with one key cannot be decrypted with another key.
    
    This ensures key security - tokens are protected by the encryption key.
    """
    # Create two different encryptors with different keys
    key1 = Fernet.generate_key().decode()
    key2 = Fernet.generate_key().decode()
    
    # Temporarily set first key
    os.environ['ENCRYPTION_KEY'] = key1
    encryptor1 = TokenEncryption()
    
    # Encrypt with first key
    encrypted = encryptor1.encrypt(token)
    
    # Try to decrypt with second key
    os.environ['ENCRYPTION_KEY'] = key2
    encryptor2 = TokenEncryption()
    
    # Should raise InvalidToken exception
    with pytest.raises(InvalidToken):
        encryptor2.decrypt(encrypted)


def test_token_encryption_requires_encryption_key():
    """
    Verify that TokenEncryption raises an error if ENCRYPTION_KEY is not set.
    """
    # Temporarily remove the encryption key
    original_key = os.environ.get('ENCRYPTION_KEY')
    if 'ENCRYPTION_KEY' in os.environ:
        del os.environ['ENCRYPTION_KEY']
    
    try:
        with pytest.raises(ValueError, match="ENCRYPTION_KEY environment variable not set"):
            TokenEncryption()
    finally:
        # Restore the original key
        if original_key:
            os.environ['ENCRYPTION_KEY'] = original_key


def test_token_encryption_rejects_empty_token():
    """
    Verify that encryption rejects empty or None tokens.
    """
    encryptor = TokenEncryption()
    
    with pytest.raises(ValueError, match="Token cannot be empty or None"):
        encryptor.encrypt("")
    
    with pytest.raises(ValueError, match="Token cannot be empty or None"):
        encryptor.encrypt(None)


def test_token_decryption_rejects_empty_token():
    """
    Verify that decryption rejects empty or None encrypted tokens.
    """
    encryptor = TokenEncryption()
    
    with pytest.raises(ValueError, match="Encrypted token cannot be empty or None"):
        encryptor.decrypt("")
    
    with pytest.raises(ValueError, match="Encrypted token cannot be empty or None"):
        encryptor.decrypt(None)


def test_token_decryption_rejects_invalid_token():
    """
    Verify that decryption rejects invalid/corrupted tokens.
    """
    encryptor = TokenEncryption()
    
    # Try to decrypt an invalid token
    with pytest.raises(InvalidToken):
        encryptor.decrypt("invalid_encrypted_token_data")


def test_get_encryptor_returns_singleton():
    """
    Verify that get_encryptor returns the same instance.
    """
    encryptor1 = get_encryptor()
    encryptor2 = get_encryptor()
    
    assert encryptor1 is encryptor2


@settings(max_examples=100)
@given(
    token=st.text(min_size=1, max_size=1000),
    # Generate tokens that look like real Spotify access tokens
    spotify_like_token=st.text(
        min_size=100, 
        max_size=500, 
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_')
    )
)
def test_token_encryption_handles_various_token_formats(token, spotify_like_token):
    """
    Verify that encryption works with various token formats including 
    realistic Spotify token patterns.
    """
    encryptor = TokenEncryption()
    
    # Test with general token
    encrypted1 = encryptor.encrypt(token)
    decrypted1 = encryptor.decrypt(encrypted1)
    assert decrypted1 == token
    
    # Test with Spotify-like token
    encrypted2 = encryptor.encrypt(spotify_like_token)
    decrypted2 = encryptor.decrypt(encrypted2)
    assert decrypted2 == spotify_like_token
