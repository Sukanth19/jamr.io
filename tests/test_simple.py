"""Simple test to verify database setup."""

from backend.models import User
from tests.conftest import get_test_session


def test_simple_user_creation():
    """Test that we can create a user."""
    db_session = get_test_session()
    try:
        user = User(
            spotify_id="test123",
            display_name="Test User",
            email="test@example.com",
            access_token_encrypted="encrypted_token",
            taste_vector={"danceability": 0.5}
        )
        db_session.add(user)
        db_session.commit()
        
        retrieved = db_session.query(User).filter(User.spotify_id == "test123").first()
        assert retrieved is not None
        assert retrieved.display_name == "Test User"
    finally:
        db_session.rollback()
        db_session.close()
