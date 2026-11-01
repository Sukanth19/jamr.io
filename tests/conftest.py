"""Pytest configuration and fixtures for database testing."""

import pytest
import os
import tempfile
from hypothesis import settings
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.models import User, Room, Message, RoomMembership, Session

# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)

# Disable Hypothesis' per-example deadline: database-backed examples
# occasionally exceed 200ms under load, causing flaky failures
settings.register_profile("default", deadline=None)
settings.load_profile("default")

# Use a temporary file for SQLite testing
_test_db_file = None
_test_engine = None


def get_test_engine():
    """Get or create the test database engine."""
    global _test_engine, _test_db_file
    if _test_engine is None:
        # Create a temporary file for the database
        fd, _test_db_file = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        TEST_DATABASE_URL = f"sqlite:///{_test_db_file}"
        _test_engine = create_engine(
            TEST_DATABASE_URL,
            connect_args={"check_same_thread": False}
        )
        
        # Enable foreign key constraints in SQLite
        @event.listens_for(_test_engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        
        Base.metadata.create_all(bind=_test_engine)
    
    return _test_engine


def get_test_session():
    """Create a new test database session."""
    engine = get_test_engine()
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return TestingSessionLocal()


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Set up test database once for the session."""
    engine = get_test_engine()
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    
    # Clean up the temporary database file
    global _test_db_file
    if _test_db_file and os.path.exists(_test_db_file):
        try:
            os.unlink(_test_db_file)
        except:
            pass


@pytest.fixture(autouse=True)
def clear_active_connections():
    """Reset global Socket.IO state (sid mapping, chat rate limits) between tests."""
    from backend.socketio_server import active_connections, message_rate_limiter
    active_connections.clear()
    message_rate_limiter.clear_all()
    yield
    active_connections.clear()
    message_rate_limiter.clear_all()


@pytest.fixture
def db_session():
    """Provide a clean database session for each test."""
    session = get_test_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        # Clean up all data after each test
        session.query(Session).delete()
        session.query(RoomMembership).delete()
        session.query(Message).delete()
        session.query(Room).delete()
        session.query(User).delete()
        session.commit()
        session.close()
