"""Data serialization utilities for API responses.

This module provides functions to serialize database models into safe
API response dictionaries, excluding sensitive fields like encrypted tokens.
"""

from typing import Dict, Any, Optional
from backend.models import User, Room, Message


def serialize_user(user: User, include_email: bool = True) -> Dict[str, Any]:
    """
    Serialize a User model to a safe dictionary for API responses.
    
    Excludes sensitive fields:
    - access_token_encrypted
    - refresh_token_encrypted
    - token_expires_at
    
    Args:
        user: The User model instance to serialize
        include_email: Whether to include the email field (default: True)
        
    Returns:
        Dictionary with safe user fields
        
    Example:
        >>> user = User(id=1, spotify_id="abc123", display_name="John Doe")
        >>> serialize_user(user)
        {
            "id": 1,
            "spotify_id": "abc123",
            "display_name": "John Doe",
            "email": "john@example.com",
            "profile_image_url": "https://...",
            "taste_vector": {...},
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00"
        }
    """
    user_dict = {
        "id": user.id,
        "spotify_id": user.spotify_id,
        "display_name": user.display_name,
        "profile_image_url": user.profile_image_url,
        "taste_vector": user.taste_vector,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None
    }
    
    # Optionally include email
    if include_email:
        user_dict["email"] = user.email
    
    return user_dict


def serialize_room(room: Room) -> Dict[str, Any]:
    """
    Serialize a Room model to a dictionary for API responses.
    
    Args:
        room: The Room model instance to serialize
        
    Returns:
        Dictionary with all room fields
        
    Example:
        >>> room = Room(id=1, name="Rock Lovers", description="A room for rock fans")
        >>> serialize_room(room)
        {
            "id": 1,
            "name": "Rock Lovers",
            "description": "A room for rock fans",
            ...
        }
    """
    return {
        "id": room.id,
        "name": room.name,
        "description": room.description,
        "owner_id": room.owner_id,
        "genre_tags": room.genre_tags,
        "taste_vector": room.taste_vector,
        "active_jam_link": room.active_jam_link,
        "user_count": room.user_count,
        "created_at": room.created_at.isoformat() if room.created_at else None,
        "updated_at": room.updated_at.isoformat() if room.updated_at else None
    }


def serialize_message(message: Message, username: Optional[str] = None) -> Dict[str, Any]:
    """
    Serialize a Message model to a dictionary for API responses.
    
    Args:
        message: The Message model instance to serialize
        username: Optional username to include in the response
        
    Returns:
        Dictionary with all message fields
        
    Example:
        >>> message = Message(id=1, room_id=1, user_id=1, content="Hello!")
        >>> serialize_message(message, username="John Doe")
        {
            "id": 1,
            "room_id": 1,
            "user_id": 1,
            "username": "John Doe",
            "content": "Hello!",
            "created_at": "2024-01-01T00:00:00"
        }
    """
    message_dict = {
        "id": message.id,
        "room_id": message.room_id,
        "user_id": message.user_id,
        "content": message.content,
        "created_at": message.created_at.isoformat() if message.created_at else None
    }
    
    # Optionally include username
    if username is not None:
        message_dict["username"] = username
    
    return message_dict
