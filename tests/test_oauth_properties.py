"""Property-based tests for OAuth token storage and user profile persistence.

Feature: jamr-io-mvp
Tests OAuth authentication flow properties including token encryption and profile persistence.
"""

import pytest
from hypothesis import given, strategies as st, settings
from cryptography.fernet import Fernet
from backend.models import User
from backend.encryption import get_encryptor
from tests.conftest import get_test_session


# Generate a valid Fernet key for testing
TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def set_test_encryption_key(monkeypatch):
    """Set a test encryption key for all tests in this module."""
    monkeypatch.setenv('ENCRYPTION_KEY', TEST_ENCRYPTION_KEY)


# Custom strategies for generating Spotify-like data
@st.composite
def spotify_profile_data(draw):
    """Generate valid Spotify profile data."""
    import uuid
    
    return {
        "spotify_id": str(uuid.uuid4()),
        "display_name": draw(st.text(
            min_size=1, 
            max_size=255, 
            alphabet=st.characters(
                min_codepoint=32,  # Start from space character
                max_codepoint=126,  # End at tilde (printable ASCII)
                blacklist_characters=['\x00']
            )
        )),
        "email": draw(st.emails()),
        "profile_image_url": draw(st.one_of(
            st.none(),
            st.text(
                min_size=10, 
                max_size=500, 
                alphabet=st.characters(
                    min_codepoint=32,
                    max_codepoint=126,
                    blacklist_characters=['\x00']
                )
            )
        )),
        "access_token": draw(st.text(min_size=50, max_size=500, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'), 
            whitelist_characters='-_'
        ))),
        "refresh_token": draw(st.one_of(
            st.none(),
            st.text(min_size=50, max_size=500, alphabet=st.characters(
                whitelist_categories=('Lu', 'Ll', 'Nd'), 
                whitelist_characters='-_'
            ))
        )),
        "taste_vector": {
            "danceability": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
            "energy": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
            "valence": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
            "acousticness": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
            "instrumentalness": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
            "speechiness": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
            "tempo_normalized": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
        }
    }


# Property 2: User Profile Persistence
# **Validates: Requirements 1.4, 1.6**
@settings(max_examples=100)
@given(profile=spotify_profile_data())
def test_user_profile_persistence_after_authentication(profile):
    """
    Property 2: User Profile Persistence
    
    For any successful Spotify authentication, the user's profile data 
    (Spotify ID, display name, email, profile image) must be stored in 
    the database and retrievable by user ID.
    
    This test simulates the OAuth callback storing user profile data
    and verifies all fields are persisted correctly.
    """
    db_session = get_test_session()
    encryptor = get_encryptor()
    
    try:
        # Encrypt tokens (as done in OAuth callback)
        access_token_encrypted = encryptor.encrypt(profile["access_token"])
        refresh_token_encrypted = None
        if profile["refresh_token"]:
            refresh_token_encrypted = encryptor.encrypt(profile["refresh_token"])
        
        # Create user with profile data (simulating OAuth callback)
        user = User(
            spotify_id=profile["spotify_id"],
            display_name=profile["display_name"],
            email=profile["email"],
            profile_image_url=profile["profile_image_url"],
            access_token_encrypted=access_token_encrypted,
            refresh_token_encrypted=refresh_token_encrypted,
            taste_vector=profile["taste_vector"]
        )
        
        db_session.add(user)
        db_session.commit()
        
        # Retrieve user from database by user ID
        retrieved_user = db_session.query(User).filter(User.id == user.id).first()
        
        # Assert user was stored and is retrievable
        assert retrieved_user is not None, "User should be retrievable from database"
        
        # Assert all profile fields are persisted correctly
        assert retrieved_user.spotify_id == profile["spotify_id"], \
            "Spotify ID should match"
        assert retrieved_user.display_name == profile["display_name"], \
            "Display name should match"
        assert retrieved_user.email == profile["email"], \
            "Email should match"
        assert retrieved_user.profile_image_url == profile["profile_image_url"], \
            "Profile image URL should match"
        
        # Assert tokens are stored encrypted
        assert retrieved_user.access_token_encrypted is not None, \
            "Access token should be stored"
        assert retrieved_user.access_token_encrypted != profile["access_token"], \
            "Access token should be encrypted (not plaintext)"
        
        # Assert taste vector is stored
        assert retrieved_user.taste_vector is not None, \
            "Taste vector should be stored"
        assert retrieved_user.taste_vector == profile["taste_vector"], \
            "Taste vector should match"
        
        # Verify tokens can be decrypted back to original values
        decrypted_access_token = encryptor.decrypt(retrieved_user.access_token_encrypted)
        assert decrypted_access_token == profile["access_token"], \
            "Decrypted access token should match original"
        
        if profile["refresh_token"]:
            assert retrieved_user.refresh_token_encrypted is not None, \
                "Refresh token should be stored when provided"
            decrypted_refresh_token = encryptor.decrypt(retrieved_user.refresh_token_encrypted)
            assert decrypted_refresh_token == profile["refresh_token"], \
                "Decrypted refresh token should match original"
    
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(profile=spotify_profile_data())
def test_user_profile_retrievable_by_spotify_id(profile):
    """
    Verify that user profile can be retrieved by Spotify ID.
    
    This is important for checking if a user already exists during OAuth callback.
    """
    db_session = get_test_session()
    encryptor = get_encryptor()
    
    try:
        # Encrypt tokens
        access_token_encrypted = encryptor.encrypt(profile["access_token"])
        refresh_token_encrypted = None
        if profile["refresh_token"]:
            refresh_token_encrypted = encryptor.encrypt(profile["refresh_token"])
        
        # Create user
        user = User(
            spotify_id=profile["spotify_id"],
            display_name=profile["display_name"],
            email=profile["email"],
            profile_image_url=profile["profile_image_url"],
            access_token_encrypted=access_token_encrypted,
            refresh_token_encrypted=refresh_token_encrypted,
            taste_vector=profile["taste_vector"]
        )
        
        db_session.add(user)
        db_session.commit()
        
        # Retrieve user by Spotify ID (as done in OAuth callback)
        retrieved_user = db_session.query(User).filter(
            User.spotify_id == profile["spotify_id"]
        ).first()
        
        # Assert user is retrievable by Spotify ID
        assert retrieved_user is not None, \
            "User should be retrievable by Spotify ID"
        assert retrieved_user.id == user.id, \
            "Retrieved user should have same ID"
        assert retrieved_user.spotify_id == profile["spotify_id"], \
            "Spotify ID should match"
    
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(profile1=spotify_profile_data(), profile2=spotify_profile_data())
def test_user_profile_update_on_reauth(profile1, profile2):
    """
    Verify that user profile is updated when user re-authenticates.
    
    When a user logs in again, their profile data should be updated
    with the latest information from Spotify.
    """
    db_session = get_test_session()
    encryptor = get_encryptor()
    
    try:
        # Use same Spotify ID for both profiles (same user, different data)
        spotify_id = profile1["spotify_id"]
        
        # First authentication - create user
        access_token_encrypted1 = encryptor.encrypt(profile1["access_token"])
        refresh_token_encrypted1 = None
        if profile1["refresh_token"]:
            refresh_token_encrypted1 = encryptor.encrypt(profile1["refresh_token"])
        
        user = User(
            spotify_id=spotify_id,
            display_name=profile1["display_name"],
            email=profile1["email"],
            profile_image_url=profile1["profile_image_url"],
            access_token_encrypted=access_token_encrypted1,
            refresh_token_encrypted=refresh_token_encrypted1,
            taste_vector=profile1["taste_vector"]
        )
        
        db_session.add(user)
        db_session.commit()
        original_user_id = user.id
        
        # Second authentication - update user (simulating OAuth callback update logic)
        existing_user = db_session.query(User).filter(User.spotify_id == spotify_id).first()
        assert existing_user is not None, "User should exist from first auth"
        
        # Update with new profile data
        access_token_encrypted2 = encryptor.encrypt(profile2["access_token"])
        refresh_token_encrypted2 = None
        if profile2["refresh_token"]:
            refresh_token_encrypted2 = encryptor.encrypt(profile2["refresh_token"])
        
        existing_user.display_name = profile2["display_name"]
        existing_user.email = profile2["email"]
        existing_user.profile_image_url = profile2["profile_image_url"]
        existing_user.access_token_encrypted = access_token_encrypted2
        existing_user.refresh_token_encrypted = refresh_token_encrypted2
        existing_user.taste_vector = profile2["taste_vector"]
        
        db_session.commit()
        
        # Retrieve updated user
        updated_user = db_session.query(User).filter(User.spotify_id == spotify_id).first()
        
        # Assert user ID remains the same (not a new user)
        assert updated_user.id == original_user_id, \
            "User ID should remain the same after update"
        
        # Assert profile data is updated
        assert updated_user.display_name == profile2["display_name"], \
            "Display name should be updated"
        assert updated_user.email == profile2["email"], \
            "Email should be updated"
        assert updated_user.profile_image_url == profile2["profile_image_url"], \
            "Profile image URL should be updated"
        assert updated_user.taste_vector == profile2["taste_vector"], \
            "Taste vector should be updated"
        
        # Verify new tokens are stored
        decrypted_access_token = encryptor.decrypt(updated_user.access_token_encrypted)
        assert decrypted_access_token == profile2["access_token"], \
            "Access token should be updated"
    
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=50)
@given(profile=spotify_profile_data())
def test_user_profile_requires_all_mandatory_fields(profile):
    """
    Verify that user profile requires all mandatory fields.
    
    Spotify ID, display name, access token, and taste vector are required.
    Note: SQLite doesn't enforce NOT NULL constraints as strictly as PostgreSQL,
    so we test that the model definition has these fields marked as required.
    """
    db_session = get_test_session()
    encryptor = get_encryptor()
    
    try:
        # Verify model has nullable=False for required fields
        from backend.models import User as UserModel
        
        # Check column definitions
        assert UserModel.spotify_id.nullable == False, "spotify_id should be non-nullable"
        assert UserModel.display_name.nullable == False, "display_name should be non-nullable"
        assert UserModel.access_token_encrypted.nullable == False, "access_token_encrypted should be non-nullable"
        assert UserModel.taste_vector.nullable == False, "taste_vector should be non-nullable"
        
        # Test that a valid user can be created with all required fields
        user = User(
            spotify_id=profile["spotify_id"],
            display_name=profile["display_name"],
            access_token_encrypted=encryptor.encrypt(profile["access_token"]),
            taste_vector=profile["taste_vector"]
        )
        db_session.add(user)
        db_session.commit()
        
        # Verify user was created successfully
        retrieved_user = db_session.query(User).filter(User.id == user.id).first()
        assert retrieved_user is not None
        assert retrieved_user.spotify_id == profile["spotify_id"]
        assert retrieved_user.display_name == profile["display_name"]
        assert retrieved_user.taste_vector == profile["taste_vector"]
    
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=50)
@given(profile=spotify_profile_data())
def test_spotify_id_uniqueness_constraint(profile):
    """
    Verify that Spotify ID has a uniqueness constraint.
    
    Two users cannot have the same Spotify ID.
    """
    db_session = get_test_session()
    encryptor = get_encryptor()
    
    try:
        # Create first user
        user1 = User(
            spotify_id=profile["spotify_id"],
            display_name=profile["display_name"],
            access_token_encrypted=encryptor.encrypt(profile["access_token"]),
            taste_vector=profile["taste_vector"]
        )
        db_session.add(user1)
        db_session.commit()
        
        # Try to create second user with same Spotify ID
        with pytest.raises(Exception):  # Should raise IntegrityError
            user2 = User(
                spotify_id=profile["spotify_id"],  # Duplicate Spotify ID
                display_name="Different Name",
                access_token_encrypted=encryptor.encrypt("different_token"),
                taste_vector=profile["taste_vector"]
            )
            db_session.add(user2)
            db_session.commit()
    
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(profile=spotify_profile_data())
def test_user_profile_timestamps_are_set(profile):
    """
    Verify that created_at and updated_at timestamps are automatically set.
    """
    db_session = get_test_session()
    encryptor = get_encryptor()
    
    try:
        # Create user
        user = User(
            spotify_id=profile["spotify_id"],
            display_name=profile["display_name"],
            email=profile["email"],
            profile_image_url=profile["profile_image_url"],
            access_token_encrypted=encryptor.encrypt(profile["access_token"]),
            taste_vector=profile["taste_vector"]
        )
        
        db_session.add(user)
        db_session.commit()
        
        # Retrieve user
        retrieved_user = db_session.query(User).filter(User.id == user.id).first()
        
        # Assert timestamps are set
        assert retrieved_user.created_at is not None, \
            "created_at timestamp should be set automatically"
        assert retrieved_user.updated_at is not None, \
            "updated_at timestamp should be set automatically"
    
    finally:
        db_session.rollback()
        db_session.close()
