"""Socket.IO server configuration and initialization.

This module sets up the Socket.IO server for real-time communication in the jamr.io platform.
The server is configured with:
- AsyncServer for asynchronous operation with FastAPI
- CORS configuration matching the FastAPI CORS settings
- ASGIApp wrapper for integration with FastAPI

The Socket.IO server handles real-time events such as:
- User connections and disconnections
- Chat messages
- Room join/leave notifications
- Spotify Jam link updates
- Active user list updates

Integration with FastAPI:
The socket_app (ASGIApp) is mounted on the FastAPI application at the /socket.io path,
allowing Socket.IO clients to connect to ws://host:port/socket.io for real-time communication.

Requirements: 7.1 (Real-time chat using Socket.IO)
"""

import os
import socketio
from dotenv import load_dotenv
from datetime import datetime
from http.cookies import SimpleCookie

# Load environment variables
load_dotenv()

# Get CORS origins from environment
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

# Create Socket.IO AsyncServer with CORS configuration
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=CORS_ORIGINS,
    logger=True,
    engineio_logger=False
)

# Create ASGI application wrapper
socket_app = socketio.ASGIApp(
    socketio_server=sio,
    socketio_path='socket.io'
)

# Module-level mapping of sid → user_id for active connections
active_connections = {}


# Socket.IO event handlers
@sio.event
async def connect(sid, environ):
    """
    Handle client connection.
    
    Validates session token from cookies and stores sid → user_id mapping.
    Rejects connection if session is invalid or expired.
    
    **Validates: Requirements 14.4**
    
    Args:
        sid: Session ID of the connecting client
        environ: WSGI environment dictionary containing HTTP headers
        
    Returns:
        False to reject connection, None/True to accept
    """
    from backend.database import get_session_local
    from backend.models import Session as SessionModel
    
    # Extract session token from cookies
    session_token = None
    
    # Try to get cookies from HTTP_COOKIE header
    cookie_header = environ.get('HTTP_COOKIE', '')
    if cookie_header:
        cookies = SimpleCookie()
        cookies.load(cookie_header)
        if 'session_token' in cookies:
            session_token = cookies['session_token'].value
    
    # If not found, try ASGI scope (for ASGI servers)
    if not session_token:
        asgi_scope = environ.get('asgi.scope', {})
        cookies_dict = asgi_scope.get('cookies', {})
        session_token = cookies_dict.get('session_token')
    
    # Reject connection if no session token
    if not session_token:
        print(f"Connection rejected for {sid}: No session token")
        return False
    
    # Validate session token against database
    session_factory = get_session_local()
    db = session_factory()
    
    try:
        # Query session from database
        session = db.query(SessionModel).filter(
            SessionModel.token == session_token
        ).first()
        
        # Check if session exists
        if not session:
            print(f"Connection rejected for {sid}: Invalid session token")
            return False
        
        # Check if session has expired
        if session.expires_at < datetime.now():
            # Delete expired session
            db.delete(session)
            db.commit()
            print(f"Connection rejected for {sid}: Session expired")
            return False
        
        # Store sid → user_id mapping
        active_connections[sid] = session.user_id
        
        print(f"Client connected: {sid} (user_id: {session.user_id})")
        return True
        
    except Exception as e:
        print(f"Error during connection validation for {sid}: {e}")
        return False
    finally:
        db.close()


@sio.event
async def disconnect(sid):
    """
    Handle client disconnection.
    
    Cleans up user state by:
    - Removing user from all rooms they're in
    - Decrementing user_count for each room
    - Broadcasting user_left events to affected rooms
    - Cleaning up sid → user_id mapping
    
    **Validates: Requirements 14.4**
    
    Args:
        sid: Session ID of the disconnecting client
    """
    from backend.database import get_session_local
    from backend.models import RoomMembership, Room, User
    
    # Look up user_id from sid mapping
    user_id = active_connections.get(sid)
    
    if not user_id:
        print(f"Client disconnected: {sid} (no user mapping found)")
        return
    
    # Clean up user state in database
    session_factory = get_session_local()
    db = session_factory()
    
    try:
        # Get user info for broadcasting
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            print(f"Client disconnected: {sid} (user {user_id} not found)")
            return
        
        # Find all rooms the user is in
        memberships = db.query(RoomMembership).filter(
            RoomMembership.user_id == user_id
        ).all()
        
        # Process each room membership
        for membership in memberships:
            room_id = membership.room_id
            
            # Delete the membership record
            db.delete(membership)
            
            # Decrement room user count
            room = db.query(Room).filter(Room.id == room_id).first()
            if room:
                room.user_count = max(0, room.user_count - 1)
                room.updated_at = datetime.now()
            
            # Broadcast user_left event to room
            await sio.emit('user_left', {
                'user_id': user_id,
                'username': user.display_name,
                'room_id': room_id
            }, room=f'room_{room_id}')
            
            # Broadcast updated user count
            await sio.emit('user_count_updated', {
                'room_id': room_id,
                'count': room.user_count if room else 0
            }, room=f'room_{room_id}')
            
            # Leave the Socket.IO room
            await sio.leave_room(sid, f'room_{room_id}')
            
            print(f"User {user_id} ({user.display_name}) removed from room {room_id}")
        
        # Commit all changes
        db.commit()
        
        print(f"Client disconnected: {sid} (user_id: {user_id}, cleaned up {len(memberships)} rooms)")
        
    except Exception as e:
        print(f"Error during disconnection cleanup for {sid}: {e}")
        db.rollback()
    finally:
        db.close()
        # Clean up the sid → user_id mapping
        if sid in active_connections:
            del active_connections[sid]


# Export the Socket.IO server instance and ASGI app
__all__ = ['sio', 'socket_app']
