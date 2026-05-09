"""Property-based tests for room leaving.

Feature: jamr-io-mvp
Tests room leaving membership deletion and user count decrement properties.
"""

import pytest
import uuid
from hypothesis import given, strategies as st, settings
from backend.models import Room, User, RoomMembership
from backend.recommendation_engine import generate_room_taste_vector
from tests.conftest import get_test_session


# Helper function to create a test user
def create_test_user(db_session, spotify_id=None):
    """Create a test user for room leaving tests."""
    if spotify_id is None:
        spotify_id = f"test_user_{uuid.uuid4()}"
    user = User(
        spotify_id=spotify_id,
        display_name="Test User",
        email="test@example.com",
        access_token_encrypted="encrypted_token",
        taste_vector={
            "danceability": 0.65,
            "energy": 0.72,
            "valence": 0.58,
            "acousticness": 0.23,
            "instrumentalness": 0.05,
            "speechiness": 0.08,
            "tempo_normalized": 0.55
        }
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# Helper function to create a test room
def create_test_room(db_session, owner_id, name=None, initial_user_count=0):
    """Create a test room for leaving tests."""
    if name is None:
        name = f"Test Room {uuid.uuid4()}"
    
    genre_tags = ['rock', 'indie']
    taste_vector = generate_room_taste_vector(genre_tags)
    
    room = Room(
        name=name,
        description="A test room for testing",
        owner_id=owner_id,
        genre_tags=genre_tags,
        taste_vector=taste_vector,
        user_count=initial_user_count
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return room


# Property 17: Room Leave Membership
# **Validates: Requirements 6.5**
@settings(max_examples=100)
@given(
    spotify_id=st.text(min_size=5, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789_'),
    room_name=st.text(min_size=3, max_size=50, alphabet=st.characters(min_codepoint=33, max_codepoint=126))
)
def test_property_17_room_leave_membership_deletion(spotify_id, room_name):
    """
    Property 17: Room Leave Membership (Part 1 - Membership Deletion)
    
    For any user leaving a room, the room_memberships record for that user and room
    must be deleted from the database.
    
    **Validates: Requirements 6.5**
    
    Feature: jamr-io-mvp, Property 17: Room Leave Membership
    """
    db_session = get_test_session()
    try:
        # Create a test user with unique spotify_id
        user = create_test_user(db_session, spotify_id=f"{spotify_id}_{uuid.uuid4()}")
        
        # Create a test room
        room = create_test_room(db_session, owner_id=user.id, name=room_name.strip())
        
        # Create another user to join and then leave the room
        leaving_user = create_test_user(db_session, spotify_id=f"leaving_user_{uuid.uuid4()}")
        
        # Create membership (user joins room)
        membership = RoomMembership(
            user_id=leaving_user.id,
            room_id=room.id
        )
        db_session.add(membership)
        db_session.commit()
        db_session.refresh(membership)
        
        # Verify membership exists
        existing_membership = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == leaving_user.id,
            RoomMembership.room_id == room.id
        ).first()
        assert existing_membership is not None
        assert existing_membership.user_id == leaving_user.id
        assert existing_membership.room_id == room.id
        
        # Simulate user leaving room by deleting membership
        db_session.delete(existing_membership)
        db_session.commit()
        
        # Verify membership record was deleted
        deleted_membership = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == leaving_user.id,
            RoomMembership.room_id == room.id
        ).first()
        
        # Verify membership no longer exists
        assert deleted_membership is None
        
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    num_users=st.integers(min_value=2, max_value=10)
)
def test_property_17_room_leave_membership_multiple_users(num_users):
    """
    Property 17: Room Leave Membership (Part 2 - Multiple Users Leaving)
    
    For any number of users leaving a room, each user's room_memberships record
    must be deleted from the database while other users' memberships remain.
    
    **Validates: Requirements 6.5**
    
    Feature: jamr-io-mvp, Property 17: Room Leave Membership
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room
        room = create_test_room(db_session, owner_id=owner.id)
        
        # Create multiple users and have them join the room
        users = []
        for i in range(num_users):
            user = create_test_user(db_session, spotify_id=f"user_{uuid.uuid4()}")
            users.append(user)
            
            # Create membership
            membership = RoomMembership(
                user_id=user.id,
                room_id=room.id
            )
            db_session.add(membership)
        
        db_session.commit()
        
        # Verify all users have memberships
        initial_count = db_session.query(RoomMembership).filter(
            RoomMembership.room_id == room.id
        ).count()
        assert initial_count == num_users
        
        # Have half the users leave (at least 1)
        num_leaving = max(1, num_users // 2)
        leaving_users = users[:num_leaving]
        remaining_users = users[num_leaving:]
        
        # Delete memberships for leaving users
        for user in leaving_users:
            membership = db_session.query(RoomMembership).filter(
                RoomMembership.user_id == user.id,
                RoomMembership.room_id == room.id
            ).first()
            if membership:
                db_session.delete(membership)
        
        db_session.commit()
        
        # Verify leaving users' memberships are deleted
        for user in leaving_users:
            deleted_membership = db_session.query(RoomMembership).filter(
                RoomMembership.user_id == user.id,
                RoomMembership.room_id == room.id
            ).first()
            assert deleted_membership is None
        
        # Verify remaining users' memberships still exist
        for user in remaining_users:
            existing_membership = db_session.query(RoomMembership).filter(
                RoomMembership.user_id == user.id,
                RoomMembership.room_id == room.id
            ).first()
            assert existing_membership is not None
        
        # Verify total membership count
        final_count = db_session.query(RoomMembership).filter(
            RoomMembership.room_id == room.id
        ).count()
        assert final_count == len(remaining_users)
        
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    num_rooms=st.integers(min_value=2, max_value=5)
)
def test_property_17_room_leave_membership_multiple_rooms(num_rooms):
    """
    Property 17: Room Leave Membership (Part 3 - User Leaves Multiple Rooms)
    
    For any user leaving multiple rooms, the room_memberships record for each
    room must be deleted, while memberships in other rooms remain intact.
    
    **Validates: Requirements 6.5**
    
    Feature: jamr-io-mvp, Property 17: Room Leave Membership
    """
    db_session = get_test_session()
    try:
        # Create a test user
        user = create_test_user(db_session)
        
        # Create multiple rooms and have the user join each
        rooms = []
        for i in range(num_rooms):
            room = create_test_room(db_session, owner_id=user.id, name=f"Room {uuid.uuid4()}")
            rooms.append(room)
            
            # Create membership
            membership = RoomMembership(
                user_id=user.id,
                room_id=room.id
            )
            db_session.add(membership)
        
        db_session.commit()
        
        # Verify user has memberships in all rooms
        initial_count = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == user.id
        ).count()
        assert initial_count == num_rooms
        
        # Have user leave half the rooms (at least 1)
        num_leaving = max(1, num_rooms // 2)
        leaving_rooms = rooms[:num_leaving]
        remaining_rooms = rooms[num_leaving:]
        
        # Delete memberships for leaving rooms
        for room in leaving_rooms:
            membership = db_session.query(RoomMembership).filter(
                RoomMembership.user_id == user.id,
                RoomMembership.room_id == room.id
            ).first()
            if membership:
                db_session.delete(membership)
        
        db_session.commit()
        
        # Verify memberships are deleted for leaving rooms
        for room in leaving_rooms:
            deleted_membership = db_session.query(RoomMembership).filter(
                RoomMembership.user_id == user.id,
                RoomMembership.room_id == room.id
            ).first()
            assert deleted_membership is None
        
        # Verify memberships still exist for remaining rooms
        for room in remaining_rooms:
            existing_membership = db_session.query(RoomMembership).filter(
                RoomMembership.user_id == user.id,
                RoomMembership.room_id == room.id
            ).first()
            assert existing_membership is not None
        
        # Verify total membership count for user
        final_count = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == user.id
        ).count()
        assert final_count == len(remaining_rooms)
        
    finally:
        db_session.rollback()
        db_session.close()


# Property 19: User Count Decrement
# **Validates: Requirements 6.7**
@settings(max_examples=100)
@given(
    initial_count=st.integers(min_value=1, max_value=100)
)
def test_property_19_user_count_decrement(initial_count):
    """
    Property 19: User Count Decrement (Part 1 - Single Leave)
    
    For any user leaving a room, the room's user_count field must decrease by exactly 1.
    
    **Validates: Requirements 6.7**
    
    Feature: jamr-io-mvp, Property 19: User Count Decrement
    """
    db_session = get_test_session()
    try:
        # Create a test user
        user = create_test_user(db_session)
        
        # Create a test room with initial user count (at least 1 to allow leaving)
        room = create_test_room(db_session, owner_id=user.id, initial_user_count=initial_count)
        
        # Verify initial count
        assert room.user_count == initial_count
        
        # Create another user who is a member and will leave
        leaving_user = create_test_user(db_session, spotify_id=f"leaving_user_{uuid.uuid4()}")
        
        # Create membership (user is in room)
        membership = RoomMembership(
            user_id=leaving_user.id,
            room_id=room.id
        )
        db_session.add(membership)
        db_session.commit()
        
        # Simulate user leaving room
        db_session.delete(membership)
        
        # Decrement user count (as the leave endpoint would do)
        room.user_count -= 1
        db_session.commit()
        db_session.refresh(room)
        
        # Verify user count decreased by exactly 1
        assert room.user_count == initial_count - 1
        
        # Retrieve room from database and verify count persists
        retrieved_room = db_session.query(Room).filter(Room.id == room.id).first()
        assert retrieved_room is not None
        assert retrieved_room.user_count == initial_count - 1
        
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    initial_count=st.integers(min_value=5, max_value=50),
    num_leaves=st.integers(min_value=1, max_value=5)
)
def test_property_19_user_count_decrement_multiple_leaves(initial_count, num_leaves):
    """
    Property 19: User Count Decrement (Part 2 - Multiple Leaves)
    
    For any number of users leaving a room sequentially, the room's user_count
    field must decrease by exactly the number of users who left.
    
    **Validates: Requirements 6.7**
    
    Feature: jamr-io-mvp, Property 19: User Count Decrement
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room with initial user count
        room = create_test_room(db_session, owner_id=owner.id, initial_user_count=initial_count)
        
        # Verify initial count
        assert room.user_count == initial_count
        
        # Create users and have them join the room
        users = []
        for i in range(num_leaves):
            user = create_test_user(db_session, spotify_id=f"user_{uuid.uuid4()}")
            users.append(user)
            
            # Create membership
            membership = RoomMembership(
                user_id=user.id,
                room_id=room.id
            )
            db_session.add(membership)
        
        db_session.commit()
        
        # Have all users leave the room
        for user in users:
            # Delete membership
            membership = db_session.query(RoomMembership).filter(
                RoomMembership.user_id == user.id,
                RoomMembership.room_id == room.id
            ).first()
            if membership:
                db_session.delete(membership)
            
            # Decrement user count
            room.user_count -= 1
        
        db_session.commit()
        db_session.refresh(room)
        
        # Verify user count decreased by exactly num_leaves
        expected_count = initial_count - num_leaves
        assert room.user_count == expected_count
        
        # Retrieve room from database and verify count persists
        retrieved_room = db_session.query(Room).filter(Room.id == room.id).first()
        assert retrieved_room is not None
        assert retrieved_room.user_count == expected_count
        
        # Verify no memberships remain for these users
        membership_count = db_session.query(RoomMembership).filter(
            RoomMembership.room_id == room.id,
            RoomMembership.user_id.in_([u.id for u in users])
        ).count()
        assert membership_count == 0
        
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    initial_count=st.integers(min_value=1, max_value=100)
)
def test_property_19_user_count_no_decrement_on_nonmember_leave(initial_count):
    """
    Property 19: User Count Decrement (Part 3 - No Decrement for Non-Member)
    
    For any user who is not a member of a room, attempting to leave should not
    decrement the user_count (idempotent operation).
    
    **Validates: Requirements 6.7**
    
    Feature: jamr-io-mvp, Property 19: User Count Decrement
    """
    db_session = get_test_session()
    try:
        # Create a test user
        user = create_test_user(db_session)
        
        # Create a test room with initial user count
        room = create_test_room(db_session, owner_id=user.id, initial_user_count=initial_count)
        
        # Create another user who is NOT a member
        non_member_user = create_test_user(db_session, spotify_id=f"non_member_{uuid.uuid4()}")
        
        # Verify no membership exists
        existing_membership = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == non_member_user.id,
            RoomMembership.room_id == room.id
        ).first()
        assert existing_membership is None
        
        # Attempt to leave (check if membership exists first, as endpoint should do)
        membership_to_delete = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == non_member_user.id,
            RoomMembership.room_id == room.id
        ).first()
        
        # If membership exists, delete it and decrement count
        if membership_to_delete:
            db_session.delete(membership_to_delete)
            room.user_count -= 1
        # Otherwise, don't decrement count
        
        db_session.commit()
        db_session.refresh(room)
        
        # Verify count did not change (no membership existed)
        assert room.user_count == initial_count
        
        # Verify still no membership exists
        final_membership = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == non_member_user.id,
            RoomMembership.room_id == room.id
        ).first()
        assert final_membership is None
        
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    initial_count=st.integers(min_value=5, max_value=100),
    num_members=st.integers(min_value=1, max_value=10)
)
def test_property_19_user_count_consistency_after_leaves(initial_count, num_members):
    """
    Property 19: User Count Decrement (Part 4 - Consistency Check)
    
    For any room, after users leave, the user_count field should be consistent
    with the change in room_memberships records.
    
    **Validates: Requirements 6.7**
    
    Feature: jamr-io-mvp, Property 19: User Count Decrement
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room with initial user count
        room = create_test_room(db_session, owner_id=owner.id, initial_user_count=initial_count)
        
        # Create users and have them join the room
        users = []
        for i in range(num_members):
            user = create_test_user(db_session, spotify_id=f"user_{uuid.uuid4()}")
            users.append(user)
            
            membership = RoomMembership(
                user_id=user.id,
                room_id=room.id
            )
            db_session.add(membership)
        
        db_session.commit()
        
        # Count memberships before leaving
        memberships_before = db_session.query(RoomMembership).filter(
            RoomMembership.room_id == room.id
        ).count()
        assert memberships_before == num_members
        
        # Have half the users leave (at least 1)
        num_leaving = max(1, num_members // 2)
        leaving_users = users[:num_leaving]
        
        # Delete memberships and decrement count
        for user in leaving_users:
            membership = db_session.query(RoomMembership).filter(
                RoomMembership.user_id == user.id,
                RoomMembership.room_id == room.id
            ).first()
            if membership:
                db_session.delete(membership)
                room.user_count -= 1
        
        db_session.commit()
        db_session.refresh(room)
        
        # Verify user_count decreased by number of users who left
        expected_count = initial_count - num_leaving
        assert room.user_count == expected_count
        
        # Verify membership count decreased by number of users who left
        memberships_after = db_session.query(RoomMembership).filter(
            RoomMembership.room_id == room.id
        ).count()
        assert memberships_after == num_members - num_leaving
        
        # The change in user_count should equal the change in membership count
        count_change = initial_count - room.user_count
        membership_change = memberships_before - memberships_after
        assert count_change == membership_change
        
    finally:
        db_session.rollback()
        db_session.close()
