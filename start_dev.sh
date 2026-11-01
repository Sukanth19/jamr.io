#!/bin/bash

# jamr.io Development Server Startup Script

set -e

echo "🎵 Starting jamr.io Development Server..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "📝 Please copy .env.example to .env and configure it:"
    echo "   cp .env.example .env"
    echo ""
    echo "Then edit .env with your configuration."
    exit 1
fi

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Virtual environment not activated. Activating..."
    if [ -d "venv" ]; then
        source venv/bin/activate
        echo "✅ Virtual environment activated"
    else
        echo "❌ Error: venv directory not found!"
        echo "📝 Create a virtual environment first:"
        echo "   python -m venv venv"
        echo "   source venv/bin/activate"
        echo "   pip install -r requirements.txt"
        exit 1
    fi
fi

# Check if dependencies are installed
echo "📦 Checking dependencies..."
python -c "import fastapi" 2>/dev/null || {
    echo "❌ Dependencies not installed!"
    echo "📝 Installing dependencies..."
    pip install -r requirements.txt
}

# Check database connection
echo "🗄️  Checking database connection..."
python -c "
from backend.database import get_engine
try:
    with get_engine().connect() as conn:
        print('✅ Database connection successful')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    print('📝 Make sure PostgreSQL is running and DATABASE_URL in .env is correct')
    exit(1)
" || exit 1

# Run migrations
echo "🔄 Running database migrations..."
alembic upgrade head || {
    echo "⚠️  Migration failed, but continuing..."
}

echo ""
echo "✅ All checks passed!"
echo ""
echo "🚀 Starting FastAPI server..."
echo "📍 Backend: http://127.0.0.1:8000"
echo "📚 API Docs: http://127.0.0.1:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
