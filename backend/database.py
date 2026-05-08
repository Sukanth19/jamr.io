"""Database configuration and connection management."""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/jamr_io")

# Engine and session factory (initialized lazily)
engine = None
SessionLocal = None

# Base class for declarative models
Base = declarative_base()


def get_engine():
    """Get or create the database engine."""
    global engine
    if engine is None:
        engine = create_engine(
            DATABASE_URL,
            pool_size=10,  # Maximum number of connections to keep in the pool
            max_overflow=20,  # Maximum number of connections that can be created beyond pool_size
            pool_timeout=30,  # Seconds to wait before giving up on getting a connection
            pool_recycle=3600,  # Recycle connections after 1 hour
            pool_pre_ping=True,  # Verify connections before using them
            echo=False  # Set to True for SQL query logging
        )
    return engine


def get_session_local():
    """Get or create the session factory."""
    global SessionLocal
    if SessionLocal is None:
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return SessionLocal


def get_db():
    """
    Dependency function to get database session.
    
    Yields:
        Session: SQLAlchemy database session
        
    Usage:
        @app.get("/endpoint")
        def endpoint(db: Session = Depends(get_db)):
            # Use db session here
            pass
    """
    session_factory = get_session_local()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database by creating all tables.
    
    This should be called once during application startup.
    In production, use Alembic migrations instead.
    """
    from backend.models import User, Room, Message, RoomMembership, Session
    Base.metadata.create_all(bind=get_engine())
