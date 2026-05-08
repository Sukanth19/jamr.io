"""SQLAlchemy database models for jamr.io."""

from sqlalchemy import (
    Column, Integer, String, Text, TIMESTAMP, ForeignKey, 
    Index, UniqueConstraint, JSON, TypeDecorator
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY as PG_ARRAY
from sqlalchemy.sql import func
from backend.database import Base
import json

# Use JSONB for PostgreSQL, JSON for other databases (like SQLite in tests)
JSONType = JSON().with_variant(JSONB(), 'postgresql')


# Custom type for handling PostgreSQL ARRAY in SQLite
class ArrayType(TypeDecorator):
    """Custom type to handle PostgreSQL ARRAY as JSON in SQLite."""
    impl = Text
    cache_ok = True
    
    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_ARRAY(Text))
        else:
            return dialect.type_descriptor(Text)
    
    def process_bind_param(self, value, dialect):
        if dialect.name != 'postgresql' and value is not None:
            return json.dumps(value)
        return value
    
    def process_result_value(self, value, dialect):
        if dialect.name != 'postgresql' and value is not None:
            return json.loads(value)
        return value


class User(Base):
    """User model representing authenticated Spotify users."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    spotify_id = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    email = Column(String(255))
    profile_image_url = Column(Text)
    access_token_encrypted = Column(Text, nullable=False)
    refresh_token_encrypted = Column(Text)
    token_expires_at = Column(TIMESTAMP)
    taste_vector = Column(JSONType, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class Room(Base):
    """Room model representing chat rooms with music preferences."""
    
    __tablename__ = "rooms"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    description = Column(String(300))
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    genre_tags = Column(ArrayType, nullable=False)
    taste_vector = Column(JSONType, nullable=False)
    active_jam_link = Column(Text)
    user_count = Column(Integer, default=0)
    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    # Index for genre tag searches using GIN index
    __table_args__ = (
        Index('idx_rooms_genre_tags', 'genre_tags', postgresql_using='gin'),
        Index('idx_rooms_created_at', 'created_at', postgresql_ops={'created_at': 'DESC'}),
    )


class Message(Base):
    """Message model representing chat messages in rooms."""
    
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    content = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # Composite index for efficient room message queries
    __table_args__ = (
        Index('idx_messages_room_id_created_at', 'room_id', 'created_at', 
              postgresql_ops={'created_at': 'DESC'}),
    )


class RoomMembership(Base):
    """RoomMembership model representing user membership in rooms."""
    
    __tablename__ = "room_memberships"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(TIMESTAMP, server_default=func.now())
    
    # Ensure unique user-room pairs
    __table_args__ = (
        UniqueConstraint('user_id', 'room_id', name='uq_user_room'),
        Index('idx_room_memberships_user_id', 'user_id'),
        Index('idx_room_memberships_room_id', 'room_id'),
    )


class Session(Base):
    """Session model representing user authentication sessions."""
    
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(TIMESTAMP, nullable=False, index=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
