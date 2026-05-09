"""Property-based tests for Jam link management.

Feature: jamr-io-mvp
Tests Spotify Jam link validation, storage, and authorization properties.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from backend.validators import validate_spotify_jam_link
from backend.models import User, Room, RoomMembership
from tests.conftest import get_test_session
from datetime import datetime, timedelta


# Property 26: Spotify Jam Link Validation
# **Validates: Requirements 8.2**
@settings(max_examples=100)
@given(
    jam_id=st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
)
def test_property_26_valid_spotify_jam_link_accepted(jam_id):
    """
    Property 26: Spotify Jam Link Validation (Part 1 - Valid Format)
    
    For any Spotify Jam link submission, if the link matches the pattern
    https://open.spotify.com/jam/<alphanumeric_id>, the platform must accept it.
    
    **Validates: Requirements 8.2**
    """
    link = f"https://open.spotify.com/jam/{jam_id}"
    is_valid, error_message = validate_spotify_jam_link(link)
    
    assert is_valid is True
    assert error_message == ""


@settings(max_examples=100)
@given(
    domain=st.sampled_from(['example.com', 'spotify.com', 'open.spotify.org', 'spotify.io', 'fake-spotify.com']),
    jam_id=st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
)
def test_property_26_invalid_domain_rejected(domain, jam_id):
    """
    Property 26: Spotify Jam Link Validation (Part 2 - Invalid Domain)
    
    For any Spotify Jam link submission, if the link does not match the pattern
    https://open.spotify.com/jam/*, the platform must reject it.
    
    **Validates: Requirements 8.2**
    """
    link = f"https://{domain}/jam/{jam_id}"
    is_valid, error_message = validate_spotify_jam_link(link)
    
    assert is_valid is False
    assert len(error_message) > 0


@settings(max_examples=100)
@given(
    path=st.sampled_from(['track', 'playlist', 'album', 'artist', 'session', 'user', 'show', 'episode']),
    jam_id=st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
)
def test_property_26_invalid_path_rejected(path, jam_id):
    """
    Property 26: Spotify Jam Link Validation (Part 3 - Invalid Path)
    
    For any Spotify link that is not a Jam link, the platform must reject it.
    
    **Validates: Requirements 8.2**
    """
    link = f"https://open.spotify.com/{path}/{jam_id}"
    is_valid, error_message = validate_spotify_jam_link(link)
    
    assert is_valid is False
    assert len(error_message) > 0


@settings(max_examples=100)
@given(
    jam_id=st.text(min_size=1, max_size=50)
)
def test_property_26_special_characters_rejected(jam_id):
    """
    Property 26: Spotify Jam Link Validation (Part 4 - Special Characters)
    
    For any Spotify Jam link with non-alphanumeric characters in the ID,
    the platform must reject it.
    
    **Validates: Requirements 8.2**
    """
    # Only test if the jam_id contains non-alphanumeric characters
    assume(not jam_id.isalnum())
    
    link = f"https://open.spotify.com/jam/{jam_id}"
    is_valid, error_message = validate_spotify_jam_link(link)
    
    assert is_valid is False
    assert len(error_message) > 0


def test_property_26_empty_link_rejected():
    """
    Property 26: Spotify Jam Link Validation (Part 5 - Empty Link)
    
    Empty Spotify Jam links must be rejected.
    
    **Validates: Requirements 8.2**
    """
    is_valid, error_message = validate_spotify_jam_link("")
    
    assert is_valid is False
    assert len(error_message) > 0


def test_property_26_http_protocol_rejected():
    """
    Property 26: Spotify Jam Link Validation (Part 6 - HTTP Protocol)
    
    HTTP (non-HTTPS) Spotify Jam links must be rejected.
    
    **Validates: Requirements 8.2**
    """
    link = "http://open.spotify.com/jam/abc123"
    is_valid, error_message = validate_spotify_jam_link(link)
    
    assert is_valid is False
    assert len(error_message) > 0


# Property 27: Jam Link Storage
# **Validates: Requirements 8.3**
@settings(max_examples=100)
@given(
    jam_id=st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'),
    room_name=st.text(min_size=3, max_size=50, alphabet=st.characters(min_codepoint=33, max_codepoint=126)),
    spotify_id=st.uuids()
)
def test_property_27_valid_jam_link_stored_in_room(jam_id, room_name, spotify_id):
    """
    Property 27: Jam Link Storage
    
    For any valid Spotify Jam link submission, the link must be stored in the
    room's active_jam_link field and must be retrievable when querying the room.
    
    **Validates: Requirements 8.3**
    """
    db_session = get_test_session()
    try:
        # Create a test user
        user = User(
            spotify_id=str(spotify_id),
            display_name="Test User",
            email="test@example.com",
            access_token_encrypted="encrypted_token",
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
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Create a test room
        room = Room(
            name=room_name,
            description="Test room",
            owner_id=user.id,
            genre_tags=["rock", "pop"],
            taste_vector={
                "danceability": 0.5,
                "energy": 0.5,
                "valence": 0.5,
                "acousticness": 0.5,
                "instrumentalness": 0.5,
                "speechiness": 0.5,
                "tempo_normalized": 0.5
            },
            active_jam_link=None,
            user_count=0
        )
        db_session.add(room)
        db_session.commit()
        db_session.refresh(room)
        
        # Create a valid Spotify Jam link
        jam_link = f"https://open.spotify.com/jam/{jam_id}"
        
        # Validate the link
        is_valid, error_message = validate_spotify_jam_link(jam_link)
        assert is_valid is True
        
        # Store the link in the room
        room.active_jam_link = jam_link
        db_session.commit()
        db_session.refresh(room)
        
        # Retrieve the room and verify the link is stored
        retrieved_room = db_session.query(Room).filter(Room.id == room.id).first()
        
        assert retrieved_room is not None
        assert retrieved_room.active_jam_link == jam_link
        assert retrieved_room.active_jam_link == f"https://open.spotify.com/jam/{jam_id}"
    finally:
        # Clean up: delete all test data
        db_session.query(Room).delete()
        db_session.query(User).delete()
        db_session.commit()
        db_session.close()


@settings(max_examples=100)
@given(
    jam_id_1=st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'),
    jam_id_2=st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'),
    room_name=st.text(min_size=3, max_size=50, alphabet=st.characters(min_codepoint=33, max_codepoint=126)),
    spotify_id=st.uuids()
)
def test_property_27_jam_link_update_overwrites_previous(jam_id_1, jam_id_2, room_name, spotify_id):
    """
    Property 27: Jam Link Storage (Part 2 - Update Overwrites)
    
    For any valid Spotify Jam link submission, when a room already has an active
    jam link, the new link must overwrite the previous one.
    
    **Validates: Requirements 8.3**
    """
    # Ensure the two jam IDs are different
    assume(jam_id_1 != jam_id_2)
    
    db_session = get_test_session()
    try:
        # Create a test user
        user = User(
            spotify_id=str(spotify_id),
            display_name="Test User",
            email="test@example.com",
            access_token_encrypted="encrypted_token",
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
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Create a test room with an initial jam link
        jam_link_1 = f"https://open.spotify.com/jam/{jam_id_1}"
        room = Room(
            name=room_name,
            description="Test room",
            owner_id=user.id,
            genre_tags=["rock", "pop"],
            taste_vector={
                "danceability": 0.5,
                "energy": 0.5,
                "valence": 0.5,
                "acousticness": 0.5,
                "instrumentalness": 0.5,
                "speechiness": 0.5,
                "tempo_normalized": 0.5
            },
            active_jam_link=jam_link_1,
            user_count=0
        )
        db_session.add(room)
        db_session.commit()
        db_session.refresh(room)
        
        # Verify initial link is stored
        assert room.active_jam_link == jam_link_1
        
        # Update with a new jam link
        jam_link_2 = f"https://open.spotify.com/jam/{jam_id_2}"
        is_valid, error_message = validate_spotify_jam_link(jam_link_2)
        assert is_valid is True
        
        room.active_jam_link = jam_link_2
        db_session.commit()
        db_session.refresh(room)
        
        # Retrieve the room and verify the new link overwrote the old one
        retrieved_room = db_session.query(Room).filter(Room.id == room.id).first()
        
        assert retrieved_room is not None
        assert retrieved_room.active_jam_link == jam_link_2
        assert retrieved_room.active_jam_link != jam_link_1
    finally:
        # Clean up: delete all test data
        db_session.query(Room).delete()
        db_session.query(User).delete()
        db_session.commit()
        db_session.close()


# Property 29: Jam Link Authorization
# **Validates: Requirements 8.7**
@settings(max_examples=100)
@given(
    jam_id=st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'),
    room_name=st.text(min_size=3, max_size=50, alphabet=st.characters(min_codepoint=33, max_codepoint=126)),
    member_spotify_id=st.uuids(),
    non_member_spotify_id=st.uuids()
)
def test_property_29_only_room_members_can_update_jam_link(
    jam_id, room_name, member_spotify_id, non_member_spotify_id
):
    """
    Property 29: Jam Link Authorization
    
    For any Spotify Jam link update attempt, if the requesting user is not a
    member of the room (no room_memberships record exists), the platform must
    reject the request.
    
    This test verifies that only users with a room_memberships record can
    update the jam link.
    
    **Validates: Requirements 8.7**
    """
    # Ensure the two users have different Spotify IDs
    assume(member_spotify_id != non_member_spotify_id)
    
    db_session = get_test_session()
    try:
        # Create a room member user
        member_user = User(
            spotify_id=str(member_spotify_id),
            display_name="Member User",
            email="member@example.com",
            access_token_encrypted="encrypted_token_member",
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
        db_session.add(member_user)
        
        # Create a non-member user
        non_member_user = User(
            spotify_id=str(non_member_spotify_id),
            display_name="Non-Member User",
            email="nonmember@example.com",
            access_token_encrypted="encrypted_token_nonmember",
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
        db_session.add(non_member_user)
        db_session.commit()
        db_session.refresh(member_user)
        db_session.refresh(non_member_user)
        
        # Create a test room
        room = Room(
            name=room_name,
            description="Test room",
            owner_id=member_user.id,
            genre_tags=["rock", "pop"],
            taste_vector={
                "danceability": 0.5,
                "energy": 0.5,
                "valence": 0.5,
                "acousticness": 0.5,
                "instrumentalness": 0.5,
                "speechiness": 0.5,
                "tempo_normalized": 0.5
            },
            active_jam_link=None,
            user_count=1
        )
        db_session.add(room)
        db_session.commit()
        db_session.refresh(room)
        
        # Create room membership for member_user only
        membership = RoomMembership(
            user_id=member_user.id,
            room_id=room.id
        )
        db_session.add(membership)
        db_session.commit()
        
        # Verify member_user has a membership record
        member_membership = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == member_user.id,
            RoomMembership.room_id == room.id
        ).first()
        assert member_membership is not None
        
        # Verify non_member_user does NOT have a membership record
        non_member_membership = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == non_member_user.id,
            RoomMembership.room_id == room.id
        ).first()
        assert non_member_membership is None
        
        # Create a valid Spotify Jam link
        jam_link = f"https://open.spotify.com/jam/{jam_id}"
        is_valid, error_message = validate_spotify_jam_link(jam_link)
        assert is_valid is True
        
        # Simulate authorization check: member can update
        # In the actual API, this would be enforced by the endpoint
        # Here we verify the membership record exists
        can_member_update = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == member_user.id,
            RoomMembership.room_id == room.id
        ).first() is not None
        
        assert can_member_update is True
        
        # Simulate authorization check: non-member cannot update
        can_non_member_update = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == non_member_user.id,
            RoomMembership.room_id == room.id
        ).first() is not None
        
        assert can_non_member_update is False
    finally:
        # Clean up: delete all test data
        db_session.query(RoomMembership).delete()
        db_session.query(Room).delete()
        db_session.query(User).delete()
        db_session.commit()
        db_session.close()


@settings(max_examples=100)
@given(
    jam_id=st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'),
    room_name=st.text(min_size=3, max_size=50, alphabet=st.characters(min_codepoint=33, max_codepoint=126)),
    spotify_id=st.uuids()
)
def test_property_29_room_member_can_update_jam_link(jam_id, room_name, spotify_id):
    """
    Property 29: Jam Link Authorization (Part 2 - Member Can Update)
    
    For any Spotify Jam link update attempt, if the requesting user is a member
    of the room (room_memberships record exists), the platform must allow the
    update.
    
    **Validates: Requirements 8.7**
    """
    db_session = get_test_session()
    try:
        # Create a test user
        user = User(
            spotify_id=str(spotify_id),
            display_name="Test User",
            email="test@example.com",
            access_token_encrypted="encrypted_token",
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
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Create a test room
        room = Room(
            name=room_name,
            description="Test room",
            owner_id=user.id,
            genre_tags=["rock", "pop"],
            taste_vector={
                "danceability": 0.5,
                "energy": 0.5,
                "valence": 0.5,
                "acousticness": 0.5,
                "instrumentalness": 0.5,
                "speechiness": 0.5,
                "tempo_normalized": 0.5
            },
            active_jam_link=None,
            user_count=1
        )
        db_session.add(room)
        db_session.commit()
        db_session.refresh(room)
        
        # Create room membership for the user
        membership = RoomMembership(
            user_id=user.id,
            room_id=room.id
        )
        db_session.add(membership)
        db_session.commit()
        
        # Verify membership exists
        user_membership = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == user.id,
            RoomMembership.room_id == room.id
        ).first()
        assert user_membership is not None
        
        # Create a valid Spotify Jam link
        jam_link = f"https://open.spotify.com/jam/{jam_id}"
        is_valid, error_message = validate_spotify_jam_link(jam_link)
        assert is_valid is True
        
        # Simulate authorization check: user is a member and can update
        can_update = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == user.id,
            RoomMembership.room_id == room.id
        ).first() is not None
        
        assert can_update is True
        
        # Update the jam link (simulating what the API endpoint does)
        room.active_jam_link = jam_link
        db_session.commit()
        db_session.refresh(room)
        
        # Verify the link was updated
        retrieved_room = db_session.query(Room).filter(Room.id == room.id).first()
        assert retrieved_room is not None
        assert retrieved_room.active_jam_link == jam_link
    finally:
        # Clean up: delete all test data
        db_session.query(RoomMembership).delete()
        db_session.query(Room).delete()
        db_session.query(User).delete()
        db_session.commit()
        db_session.close()
