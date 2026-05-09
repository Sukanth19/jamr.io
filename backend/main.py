"""FastAPI application entry point for jamr.io."""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create FastAPI application
app = FastAPI(
    title="jamr.io API",
    description="Real-time music matchmaking platform API",
    version="1.0.0"
)

# Configure CORS middleware
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Import routers
from backend.auth import router as auth_router
from backend.rooms import router as rooms_router

# Include routers
app.include_router(auth_router)
app.include_router(rooms_router)

# Mount static files directory for frontend
# This will serve HTML, CSS, and JavaScript files
if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    # Import here to avoid circular imports
    from backend.database import init_db
    
    # Initialize database (create tables if they don't exist)
    # In production, use Alembic migrations instead
    try:
        init_db()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")


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
    Root endpoint.
    
    Returns:
        dict: Welcome message and API information
    """
    return {
        "message": "Welcome to jamr.io API",
        "docs": "/docs",
        "health": "/health"
    }


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
