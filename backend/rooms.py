"""Room management API endpoints for jamr.io."""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Room, User
from backend.auth import get_current_user
from backend.recommendation_engine import get_recommended_rooms, generate_room_taste_vector
from backend.validators import validate_room_name, validate_room_description, validate_spotify_jam_link

# Create router for room endpoints
router = APIRouter(prefix="/api/rooms", tags=["Rooms"])


# Pydantic models for request/response validation
class CreateRoomRequest(BaseModel):
    """Request model for creating a new room."""
    name: str = Field(..., min_length=1, max_length=100, description="Room name (3-50 characters after trimming)")
    description: Optional[str] = Field(None, max_length=300, description="Room description (max 300 characters)")
    genre_tags: List[str] = Field(..., min_items=1, description="List of genre tags (must be non-empty)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Indie Rock Lovers",
                "description": "A room for fans of indie and alternative rock music",
                "genre_tags": ["rock", "indie", "alternative"]
            }
        }


class UpdateJamLinkRequest(BaseModel):
    """Request model for updating Spotify Jam link."""
    link: str = Field(..., description="Spotify Jam link URL")
    
    class Config:
        json_schema_extra = {
            "example": {
                "link": "https://open.spotify.com/jam/abc123xyz"
            }
        }


@router.get("")
async def get_rooms(
    search: Optional[str] = Query(None, description="Search term for room name or description"),
    genres: Optional[str] = Query(None, description="Comma-separated list of genre tags to filter by"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of rooms with optional filtering and recommendation ranking.
    
    Accepts optional query parameters for search and genre filtering.
    Returns rooms ranked by similarity to the authenticated user's taste vector.
    
    **Validates: Requirements 3.1, 3.2, 3.5, 3.6**
    
    Args:
        search: Optional search term to filter rooms by name or description
        genres: Optional comma-separated genre tags to filter by (e.g., "rock,pop,indie")
        current_user: Authenticated user (from dependency)
        db: Database session dependency
    
    Returns:
        dict: List of rooms with similarity scores and metadata
        {
            "rooms": [
                {
                    "id": int,
                    "name": str,
                    "description": str,
                    "genre_tags": List[str],
                    "user_count": int,
                    "active_jam_link": str | None,
                    "owner_id": int,
                    "created_at": str,
                    "updated_at": str,
                    "similarity_score": float,
                    "highly_recommended": bool
                }
            ],
            "total": int
        }
    """
    # Start with base query
    query = db.query(Room)
    
    # Apply search filter if provided
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Room.name.ilike(search_term)) | 
            (Room.description.ilike(search_term))
        )
    
    # Apply genre filter if provided
    genre_list = []
    if genres:
        # Parse comma-separated genres
        genre_list = [g.strip().lower() for g in genres.split(",") if g.strip()]
    
    # Fetch all matching rooms
    rooms = query.all()
    
    # If genre filter was applied, filter rooms
    if genre_list:
        # Filter rooms in Python (works for both SQLite and PostgreSQL)
        import json
        filtered_rooms = []
        for room in rooms:
            # Handle both string (SQLite) and list (PostgreSQL) formats
            if isinstance(room.genre_tags, str):
                room_genres = json.loads(room.genre_tags)
            else:
                room_genres = room.genre_tags
            
            # Convert to lowercase for case-insensitive comparison
            room_genres_lower = [g.lower() for g in room_genres]
            
            # Check if any genre in the filter list matches
            if any(genre in room_genres_lower for genre in genre_list):
                filtered_rooms.append(room)
        
        rooms = filtered_rooms
    
    # Convert rooms to dictionaries for recommendation engine
    rooms_data = []
    for room in rooms:
        room_dict = {
            'id': room.id,
            'name': room.name,
            'description': room.description,
            'genre_tags': room.genre_tags,
            'taste_vector': room.taste_vector,
            'user_count': room.user_count,
            'active_jam_link': room.active_jam_link,
            'owner_id': room.owner_id,
            'created_at': room.created_at.isoformat() if room.created_at else None,
            'updated_at': room.updated_at.isoformat() if room.updated_at else None
        }
        rooms_data.append(room_dict)
    
    # Get user's taste vector
    user_taste_vector = current_user.taste_vector
    
    # Rank rooms by similarity to user's taste
    recommended_rooms = get_recommended_rooms(user_taste_vector, rooms_data)
    
    return {
        "rooms": recommended_rooms,
        "total": len(recommended_rooms)
    }


@router.post("", status_code=201)
async def create_room(
    room_data: CreateRoomRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new room.
    
    Requires authentication. Validates room name (3-50 chars after trimming),
    description (max 300 chars), and genre_tags (non-empty array).
    Generates room taste vector from genre tags and assigns the authenticated
    user as the room owner.
    
    **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7**
    
    Args:
        room_data: Room creation request data
        current_user: Authenticated user (from dependency)
        db: Database session dependency
    
    Returns:
        dict: Created room with all fields including ID
        {
            "id": int,
            "name": str,
            "description": str | None,
            "genre_tags": List[str],
            "taste_vector": dict,
            "owner_id": int,
            "active_jam_link": str | None,
            "user_count": int,
            "created_at": str,
            "updated_at": str
        }
    
    Raises:
        HTTPException: 400 if validation fails
    """
    # Validate room name (3-50 chars after trimming)
    is_valid_name, name_error = validate_room_name(room_data.name)
    if not is_valid_name:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": name_error,
                    "field": "name"
                }
            }
        )
    
    # Validate room description (max 300 chars)
    is_valid_description, description_error = validate_room_description(room_data.description or "")
    if not is_valid_description:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": description_error,
                    "field": "description"
                }
            }
        )
    
    # Validate genre_tags is non-empty array
    if not room_data.genre_tags or len(room_data.genre_tags) == 0:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Genre tags cannot be empty",
                    "field": "genre_tags"
                }
            }
        )
    
    # Trim whitespace from room name
    trimmed_name = room_data.name.strip()
    
    # Generate room taste vector from genre tags
    taste_vector = generate_room_taste_vector(room_data.genre_tags)
    
    # Create new room
    new_room = Room(
        name=trimmed_name,
        description=room_data.description,
        owner_id=current_user.id,
        genre_tags=room_data.genre_tags,
        taste_vector=taste_vector,
        active_jam_link=None,
        user_count=0
    )
    
    # Store room in database
    db.add(new_room)
    db.commit()
    db.refresh(new_room)
    
    # Return created room with all fields
    return {
        "id": new_room.id,
        "name": new_room.name,
        "description": new_room.description,
        "genre_tags": new_room.genre_tags,
        "taste_vector": new_room.taste_vector,
        "owner_id": new_room.owner_id,
        "active_jam_link": new_room.active_jam_link,
        "user_count": new_room.user_count,
        "created_at": new_room.created_at.isoformat() if new_room.created_at else None,
        "updated_at": new_room.updated_at.isoformat() if new_room.updated_at else None
    }


@router.get("/{room_id}")
async def get_room(
    room_id: int,
    db: Session = Depends(get_db)
):
    """
    Get room details by ID.
    
    Fetches a single room by its ID and returns all room details including
    the active Spotify Jam link. Returns 404 if the room doesn't exist.
    
    **Validates: Requirements 8.5**
    
    Args:
        room_id: ID of the room to fetch
        db: Database session dependency
    
    Returns:
        dict: Room details with all fields
        {
            "id": int,
            "name": str,
            "description": str | None,
            "genre_tags": List[str],
            "taste_vector": dict,
            "owner_id": int,
            "active_jam_link": str | None,
            "user_count": int,
            "created_at": str,
            "updated_at": str
        }
    
    Raises:
        HTTPException: 404 if room not found
    """
    # Fetch room by ID from database
    room = db.query(Room).filter(Room.id == room_id).first()
    
    # Return 404 if room not found
    if not room:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Room with ID {room_id} not found",
                    "field": "room_id"
                }
            }
        )
    
    # Return room details including active_jam_link
    return {
        "id": room.id,
        "name": room.name,
        "description": room.description,
        "genre_tags": room.genre_tags,
        "taste_vector": room.taste_vector,
        "owner_id": room.owner_id,
        "active_jam_link": room.active_jam_link,
        "user_count": room.user_count,
        "created_at": room.created_at.isoformat() if room.created_at else None,
        "updated_at": room.updated_at.isoformat() if room.updated_at else None
    }


@router.post("/{room_id}/join")
async def join_room(
    room_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Join a room.
    
    Requires authentication. Creates a room_memberships record for the user
    and room, and increments the room's user_count. If the user is already
    a member of the room, returns success without creating a duplicate record.
    
    **Validates: Requirements 6.1, 6.2, 6.4**
    
    Args:
        room_id: ID of the room to join
        current_user: Authenticated user (from dependency)
        db: Database session dependency
    
    Returns:
        dict: Success message with room and membership details
        {
            "message": str,
            "room_id": int,
            "user_id": int,
            "joined_at": str
        }
    
    Raises:
        HTTPException: 404 if room not found
    """
    from backend.models import RoomMembership
    
    # Check if room exists
    room = db.query(Room).filter(Room.id == room_id).first()
    
    if not room:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Room with ID {room_id} not found",
                    "field": "room_id"
                }
            }
        )
    
    # Check if user is already a member
    existing_membership = db.query(RoomMembership).filter(
        RoomMembership.user_id == current_user.id,
        RoomMembership.room_id == room_id
    ).first()
    
    if existing_membership:
        # User is already a member, return success
        return {
            "message": "Already a member of this room",
            "room_id": room_id,
            "user_id": current_user.id,
            "joined_at": existing_membership.joined_at.isoformat() if existing_membership.joined_at else None
        }
    
    # Create room membership record
    membership = RoomMembership(
        user_id=current_user.id,
        room_id=room_id
    )
    db.add(membership)
    
    # Increment room user count
    room.user_count += 1
    
    # Commit changes to database
    db.commit()
    db.refresh(membership)
    
    # Return success response
    return {
        "message": "Successfully joined room",
        "room_id": room_id,
        "user_id": current_user.id,
        "joined_at": membership.joined_at.isoformat() if membership.joined_at else None
    }


@router.post("/{room_id}/leave")
async def leave_room(
    room_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Leave a room.
    
    Requires authentication. Deletes the room_memberships record for the user
    and room, and decrements the room's user_count. Returns success response.
    
    **Validates: Requirements 6.5, 6.7**
    
    Args:
        room_id: ID of the room to leave
        current_user: Authenticated user (from dependency)
        db: Database session dependency
    
    Returns:
        dict: Success message with room and user details
        {
            "message": str,
            "room_id": int,
            "user_id": int
        }
    
    Raises:
        HTTPException: 404 if room not found or user is not a member
    """
    from backend.models import RoomMembership
    
    # Check if room exists
    room = db.query(Room).filter(Room.id == room_id).first()
    
    if not room:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Room with ID {room_id} not found",
                    "field": "room_id"
                }
            }
        )
    
    # Check if user is a member of the room
    membership = db.query(RoomMembership).filter(
        RoomMembership.user_id == current_user.id,
        RoomMembership.room_id == room_id
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "User is not a member of this room",
                    "field": "membership"
                }
            }
        )
    
    # Delete room membership record
    db.delete(membership)
    
    # Decrement room user count
    room.user_count -= 1
    
    # Commit changes to database
    db.commit()
    
    # Return success response
    return {
        "message": "Successfully left room",
        "room_id": room_id,
        "user_id": current_user.id
    }


@router.put("/{room_id}/jam-link")
async def update_jam_link(
    room_id: int,
    jam_link_data: UpdateJamLinkRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update Spotify Jam link for a room.
    
    Requires authentication and room membership. Validates the Spotify Jam link
    format and updates the room's active_jam_link field. Only room members can
    update the Jam link.
    
    **Validates: Requirements 8.1, 8.2, 8.3, 8.7**
    
    Args:
        room_id: ID of the room to update
        jam_link_data: Request data containing the Spotify Jam link
        current_user: Authenticated user (from dependency)
        db: Database session dependency
    
    Returns:
        dict: Success message with updated room details
        {
            "message": str,
            "room_id": int,
            "active_jam_link": str,
            "updated_by": int,
            "updated_at": str
        }
    
    Raises:
        HTTPException: 404 if room not found
        HTTPException: 403 if user is not a room member
        HTTPException: 400 if Spotify Jam link format is invalid
    """
    from backend.models import RoomMembership
    
    # Check if room exists
    room = db.query(Room).filter(Room.id == room_id).first()
    
    if not room:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Room with ID {room_id} not found",
                    "field": "room_id"
                }
            }
        )
    
    # Verify user is room member
    membership = db.query(RoomMembership).filter(
        RoomMembership.user_id == current_user.id,
        RoomMembership.room_id == room_id
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Only room members can update the Spotify Jam link",
                    "field": "membership"
                }
            }
        )
    
    # Validate Spotify Jam link format
    is_valid, error_message = validate_spotify_jam_link(jam_link_data.link)
    
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": error_message,
                    "field": "link"
                }
            }
        )
    
    # Update room active_jam_link field
    room.active_jam_link = jam_link_data.link
    
    # Commit changes to database
    db.commit()
    db.refresh(room)
    
    # Return success response
    return {
        "message": "Successfully updated Spotify Jam link",
        "room_id": room_id,
        "active_jam_link": room.active_jam_link,
        "updated_by": current_user.id,
        "updated_at": room.updated_at.isoformat() if room.updated_at else None
    }


@router.get("/{room_id}/messages")
async def get_messages(
    room_id: int,
    db: Session = Depends(get_db)
):
    """
    Get recent messages for a room.
    
    Fetches the most recent 50 messages for the specified room, ordered by
    created_at descending (newest first). Returns messages with user information
    including username and user_id.
    
    **Validates: Requirements 7.5**
    
    Args:
        room_id: ID of the room to fetch messages for
        db: Database session dependency
    
    Returns:
        dict: List of messages with user information
        {
            "messages": [
                {
                    "id": int,
                    "room_id": int,
                    "user_id": int | None,
                    "username": str | None,
                    "content": str,
                    "created_at": str
                }
            ],
            "total": int,
            "room_id": int
        }
    
    Raises:
        HTTPException: 404 if room not found
    """
    from backend.models import Message
    
    # Check if room exists
    room = db.query(Room).filter(Room.id == room_id).first()
    
    if not room:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Room with ID {room_id} not found",
                    "field": "room_id"
                }
            }
        )
    
    # Fetch most recent 50 messages for room, ordered by created_at descending
    messages = db.query(Message).filter(
        Message.room_id == room_id
    ).order_by(
        Message.created_at.desc()
    ).limit(50).all()
    
    # Build response with user information
    messages_data = []
    for message in messages:
        # Fetch user information if user_id is not null
        username = None
        if message.user_id:
            user = db.query(User).filter(User.id == message.user_id).first()
            if user:
                username = user.display_name
        
        messages_data.append({
            "id": message.id,
            "room_id": message.room_id,
            "user_id": message.user_id,
            "username": username,
            "content": message.content,
            "created_at": message.created_at.isoformat() if message.created_at else None
        })
    
    return {
        "messages": messages_data,
        "total": len(messages_data),
        "room_id": room_id
    }
