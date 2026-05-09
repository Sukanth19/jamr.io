"""Room management API endpoints for jamr.io."""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Room, User
from backend.auth import get_current_user
from backend.recommendation_engine import get_recommended_rooms, generate_room_taste_vector
from backend.validators import validate_room_name, validate_room_description

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
