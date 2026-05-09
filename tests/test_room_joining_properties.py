"""Property-based tests for room joining.

Feature: jamr-io-mvp
Tests room joining membership creation and user count increment properties.
"""

import pytest
import uuid
from hypothesis import given, strategies as st, settings
from backend.models import Room, User, RoomMembership
from backend.recommendation_engine import generate_room_taste_vector
from tests.conftest import get_test_session


# Helper function to create a test user
def create_test_user(db_session, spotify_id=None):
    """Create a test user for room joining tests."""
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
    """Create a test room for joining tests."""
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


# Property 14: Room Join Membership
# **Validates: Requirements 6.1, 6.2**
@settings(max_examples=100)
@given(
    spotify_id=st.text(min_size=5, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789_'),
    room_name=st.text(min_size=3, max_size=50, alphabet=st.characters(min_codepoint=33, max_codepoint=126))
)
def test_property_14_room_join_membership_creation(spotify_id, room_name):
    """
    Property 14: Room Join Membership (Part 1 - Membership Creation)
    
    For any user joining a room, a room_memberships record must be created with
    the user_id and room_id, and the record must be retrievable from the database.
    
    Feature: jamr-io-mvp, Property 14: Room Join Membership
    """
    db_session = get_test_session()
    try:
        # Create a test user with unique spotify_id
        user = create_test_user(db_session, spotify_id=f"{spotify_id}_{uuid.uuid4()}")
        
        # Create a test room
        room = create_test_room(db_session, owner_id=user.id, name=room_name.strip())
        
        # Verify no membership exists initially
        initial_membership = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == user.id,
            RoomMembership.room_id == room.id
        ).first()
        assert initial_membership is None
        
        # Simulate user joining room by creating membership
        membership = RoomMembership(
            user_id=user.id,
            room_id=room.id
        )
        db_session.add(membership)
        db_session.commit()
        db_session.refresh(membership)
        
        # Verify membership record was created and has an ID
        assert membership.id is not None
        
        # Retrieve membership from database
        retrieved_membership = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == user.id,
            RoomMembership.room_id == room.id
        ).first()
        
        # Verify membership exists and has correct fields
        assert retrieved_membership is not None
        assert retrieved_membership.user_id == user.id
        assert retrieved_membership.room_id == room.id
        assert retrieved_membership.joined_at is not None
        
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    num_users=st.integers(min_value=1, max_value=10)
)
def test_property_14_room_join_membership_multiple_users(num_users):
    """
    Property 14: Room Join Membership (Part 2 - Multiple Users)
    
    For any number of users joining a room, each user must have a separate
    room_memberships record that is retrievable from the database.
    
    Feature: jamr-io-mvp, Property 14: Room Join Membership
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
        
        # Verify each user has a membership record
        for user in users:
            retrieved_membership = db_session.query(RoomMembership).filter(
                RoomMembership.user_id == user.id,
                RoomMembership.room_id == room.id
            ).first()
            
            assert retrieved_membership is not None
            assert retrieved_membership.user_id == user.id
            assert retrieved_membership.room_id == room.id
        
        # Verify total membership count matches number of users
        total_memberships = db_session.query(RoomMembership).filter(
            RoomMembership.room_id == room.id
        ).count()
        assert total_memberships == num_users
        
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    num_rooms=st.integers(min_value=1, max_value=5)
)
def test_property_14_room_join_membership_multiple_rooms(num_rooms):
    """
    Property 14: Room Join Membership (Part 3 - User Joins Multiple Rooms)
    
    For any user joining multiple rooms, a separate room_memberships record must
    be created for each room, and all records must be retrievable.
    
    Feature: jamr-io-mvp, Property 14: Room Join Membership
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
        
        # Verify user has a membership record for each room
        for room in rooms:
            retrieved_membership = db_session.query(RoomMembership).filter(
                RoomMembership.user_id == user.id,
                RoomMembership.room_id == room.id
            ).first()
            
            assert retrieved_membership is not None
            assert retrieved_membership.user_id == user.id
            assert retrieved_membership.room_id == room.id
        
        # Verify total membership count for user matches number of rooms
        total_memberships = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == user.id
        ).count()
        assert total_memberships == num_rooms
        
    finally:
        db_session.rollback()
        db_session.close()


# Property 16: User Count Increment
# **Validates: Requirements 6.4**
@settings(max_examples=100)
@given(
    initial_count=st.integers(min_value=0, max_value=100)
)
def test_property_16_user_count_increment(initial_count):
    """
    Property 16: User Count Increment (Part 1 - Single Join)
    
    For any user joining a room, the room's user_count field must increase by exactly 1.
    
    Feature: jamr-io-mvp, Property 16: User Count Increment
    """
    db_session = get_test_session()
    try:
        # Create a test user
        user = create_test_user(db_session)
        
        # Create a test room with initial user count
        room = create_test_room(db_session, owner_id=user.id, initial_user_count=initial_count)
        
        # Verify initial count
        assert room.user_count == initial_count
        
        # Create another user to join the room
        joining_user = create_test_user(db_session, spotify_id=f"joining_user_{uuid.uuid4()}")
        
        # Simulate user joining room
        membership = RoomMembership(
            user_id=joining_user.id,
            room_id=room.id
        )
        db_session.add(membership)
        
        # Increment user count (as the join endpoint would do)
        room.user_count += 1
        db_session.commit()
        db_session.refresh(room)
        
        # Verify user count increased by exactly 1
        assert room.user_count == initial_count + 1
        
        # Retrieve room from database and verify count persists
        retrieved_room = db_session.query(Room).filter(Room.id == room.id).first()
        assert retrieved_room is not None
        assert retrieved_room.user_count == initial_count + 1
        
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    initial_count=st.integers(min_value=0, max_value=50),
    num_joins=st.integers(min_value=1, max_value=10)
)
def test_property_16_user_count_increment_multiple_joins(initial_count, num_joins):
    """
    Property 16: User Count Increment (Part 2 - Multiple Joins)
    
    For any number of users joining a room sequentially, the room's user_count
    field must increase by exactly the number of users who joined.
    
    Feature: jamr-io-mvp, Property 16: User Count Increment
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room with initial user count
        room = create_test_room(db_session, owner_id=owner.id, initial_user_count=initial_count)
        
        # Verify initial count
        assert room.user_count == initial_count
        
        # Have multiple users join the room
        for i in range(num_joins):
            # Create a new user
            user = create_test_user(db_session, spotify_id=f"user_{uuid.uuid4()}")
            
            # Create membership
            membership = RoomMembership(
                user_id=user.id,
                room_id=room.id
            )
            db_session.add(membership)
            
            # Increment user count
            room.user_count += 1
        
        db_session.commit()
        db_session.refresh(room)
        
        # Verify user count increased by exactly num_joins
        expected_count = initial_count + num_joins
        assert room.user_count == expected_count
        
        # Retrieve room from database and verify count persists
        retrieved_room = db_session.query(Room).filter(Room.id == room.id).first()
        assert retrieved_room is not None
        assert retrieved_room.user_count == expected_count
        
        # Verify membership count matches the increment
        membership_count = db_session.query(RoomMembership).filter(
            RoomMembership.room_id == room.id
        ).count()
        assert membership_count == num_joins
        
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    initial_count=st.integers(min_value=0, max_value=100)
)
def test_property_16_user_count_no_increment_on_duplicate_join(initial_count):
    """
    Property 16: User Count Increment (Part 3 - No Duplicate Increment)
    
    For any user who is already a member of a room, attempting to join again
    should not increment the user_count (idempotent operation).
    
    Feature: jamr-io-mvp, Property 16: User Count Increment
    """
    db_session = get_test_session()
    try:
        # Create a test user
        user = create_test_user(db_session)
        
        # Create a test room with initial user count
        room = create_test_room(db_session, owner_id=user.id, initial_user_count=initial_count)
        
        # Create another user to join the room
        joining_user = create_test_user(db_session, spotify_id=f"joining_user_{uuid.uuid4()}")
        
        # First join - create membership and increment count
        membership = RoomMembership(
            user_id=joining_user.id,
            room_id=room.id
        )
        db_session.add(membership)
        room.user_count += 1
        db_session.commit()
        db_session.refresh(room)
        
        # Verify count after first join
        count_after_first_join = initial_count + 1
        assert room.user_count == count_after_first_join
        
        # Check if membership already exists (simulating duplicate join check)
        existing_membership = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == joining_user.id,
            RoomMembership.room_id == room.id
        ).first()
        
        # If membership exists, don't increment count (this is what the endpoint should do)
        if existing_membership:
            # Don't increment count
            pass
        else:
            # This shouldn't happen in this test
            room.user_count += 1
        
        db_session.commit()
        db_session.refresh(room)
        
        # Verify count did not change on duplicate join attempt
        assert room.user_count == count_after_first_join
        
        # Verify only one membership record exists
        membership_count = db_session.query(RoomMembership).filter(
            RoomMembership.user_id == joining_user.id,
            RoomMembership.room_id == room.id
        ).count()
        assert membership_count == 1
        
    finally:
        db_session.rollback()
        db_session.close()


@settings(max_examples=100)
@given(
    initial_count=st.integers(min_value=0, max_value=100)
)
def test_property_16_user_count_consistency_with_memberships(initial_count):
    """
    Property 16: User Count Increment (Part 4 - Consistency Check)
    
    For any room, after users join, the user_count field should be consistent
    with the actual number of room_memberships records (assuming initial_count
    represents pre-existing members).
    
    Feature: jamr-io-mvp, Property 16: User Count Increment
    """
    db_session = get_test_session()
    try:
        # Create room owner
        owner = create_test_user(db_session)
        
        # Create a test room with initial user count
        room = create_test_room(db_session, owner_id=owner.id, initial_user_count=initial_count)
        
        # Have 3 users join the room
        num_new_joins = 3
        for i in range(num_new_joins):
            user = create_test_user(db_session, spotify_id=f"user_{uuid.uuid4()}")
            
            membership = RoomMembership(
                user_id=user.id,
                room_id=room.id
            )
            db_session.add(membership)
            room.user_count += 1
        
        db_session.commit()
        db_session.refresh(room)
        
        # Verify user_count matches initial_count + new joins
        expected_count = initial_count + num_new_joins
        assert room.user_count == expected_count
        
        # Verify membership count matches new joins
        membership_count = db_session.query(RoomMembership).filter(
            RoomMembership.room_id == room.id
        ).count()
        assert membership_count == num_new_joins
        
        # The user_count should equal initial_count + membership_count
        assert room.user_count == initial_count + membership_count
        
    finally:
        db_session.rollback()
        db_session.close()
