"""FastAPI application entry point for jamr.io."""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create FastAPI application
app = FastAPI(
    title="jamr.io API",
    description="Real-time music matchmaking platform API",
    version="1.0.0"
)

# Import Socket.IO server
from backend.socketio_server import socket_app

# Configure CORS middleware
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)


# Security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    
    Adds the following headers:
    - Strict-Transport-Security (HSTS): Forces HTTPS connections
    - X-Content-Type-Options: Prevents MIME type sniffing
    - X-Frame-Options: Prevents clickjacking
    - X-XSS-Protection: Enables XSS filtering in older browsers
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Get environment (default to development)
        environment = os.getenv("ENVIRONMENT", "development")
        
        # Only add HSTS header in production (requires HTTPS)
        if environment == "production":
            # HSTS: Force HTTPS for 1 year, include subdomains
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Make browsers revalidate pages and static files on every load (cheap
        # 304s via ETag/Last-Modified) so they never mix old CSS/JS with new HTML
        path = request.url.path
        if path.startswith("/static/") or path in ("/", "/discover", "/room", "/admin"):
            response.headers["Cache-Control"] = "no-cache"

        # Add other security headers (safe for both dev and prod)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        return response


# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Import routers
from backend.auth import router as auth_router
from backend.rooms import router as rooms_router
from backend.admin import router as admin_router

# Include routers
app.include_router(auth_router)
app.include_router(rooms_router)
app.include_router(admin_router)

# Mount static files directory for frontend
# This will serve HTML, CSS, and JavaScript files
if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Mount Socket.IO application
app.mount("/socket.io", socket_app)


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    # Import here to avoid circular imports
    from backend.database import init_db
    from backend.error_handlers import register_exception_handlers
    from backend.logging_config import configure_logging
    
    # Configure logging
    configure_logging()
    
    # Register exception handlers
    register_exception_handlers(app)
    
    # Initialize database (create tables if they don't exist)
    # In production, use Alembic migrations instead
    try:
        init_db()
        print("Database initialized successfully")
        reset_room_presence()
    except Exception as e:
        print(f"Database initialization error: {e}")


def reset_room_presence():
    """
    Clear room memberships and user counts left over from before a restart.
    
    Presence is tracked per Socket.IO connection, and a restart drops every
    connection without running disconnect cleanup. Open pages rejoin their
    room automatically when the socket reconnects.
    """
    from backend.database import get_session_local
    from backend.models import Room, RoomMembership
    
    db = get_session_local()()
    try:
        db.query(RoomMembership).delete()
        db.query(Room).update({Room.user_count: 0})
        db.commit()
    finally:
        db.close()


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        dict: Health status of the application
    """
    return {
        "status": "healthy",
        "service": "jamr.io API",
        "version": "1.0.0"
    }


@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint - Serve landing page.
    
    Returns:
        FileResponse: The landing page HTML file
    """
    # Check if frontend directory and index.html exist
    if os.path.exists("frontend/index.html"):
        return FileResponse("frontend/index.html")
    
    # Fallback to JSON response if frontend not found
    return {
        "message": "Welcome to jamr.io API",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/discover", tags=["Pages"], include_in_schema=False)
async def discover_page():
    """Serve the room discovery page."""
    return FileResponse("frontend/discover.html")


@app.get("/admin", tags=["Pages"], include_in_schema=False)
async def admin_page():
    """Serve the control panel page (the API enforces who can use it)."""
    return FileResponse("frontend/admin.html")


@app.get("/room", tags=["Pages"], include_in_schema=False)
async def room_page():
    """Serve the room chat page (room ID is passed as ?id=<room_id>)."""
    return FileResponse("frontend/room.html")


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handle 404 errors."""
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "code": "NOT_FOUND",
                "message": "The requested resource was not found"
            }
        }
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Handle 500 errors."""
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal server error occurred"
            }
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
