#!/usr/bin/env python3
"""
Setup verification script for jamr.io
Checks if all prerequisites are configured correctly
"""

import os
import sys
from pathlib import Path

def check_env_file():
    """Check if .env file exists and has required variables"""
    print("🔍 Checking .env file...")
    
    if not Path(".env").exists():
        print("❌ .env file not found")
        print("   Run: cp .env.example .env")
        return False
    
    required_vars = [
        "DATABASE_URL",
        "SPOTIFY_CLIENT_ID",
        "SPOTIFY_CLIENT_SECRET",
        "ENCRYPTION_KEY",
        "SESSION_SECRET"
    ]
    
    missing = []
    with open(".env") as f:
        content = f.read()
        for var in required_vars:
            if f"{var}=" not in content or f"{var}=your_" in content or f"{var}=\n" in content:
                missing.append(var)
    
    if missing:
        print(f"❌ Missing or unconfigured variables: {', '.join(missing)}")
        return False
    
    print("✅ .env file configured")
    return True

def check_venv():
    """Check if virtual environment is activated"""
    print("\n🔍 Checking virtual environment...")
    
    if sys.prefix == sys.base_prefix:
        print("❌ Virtual environment not activated")
        print("   Run: source venv/bin/activate")
        return False
    
    print(f"✅ Virtual environment active: {sys.prefix}")
    return True

def check_dependencies():
    """Check if required packages are installed"""
    print("\n🔍 Checking dependencies...")
    
    required_packages = [
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "psycopg2",
        "alembic",
        "socketio",  # python-socketio
        "cryptography",
        "httpx",
        "dotenv"  # python-dotenv
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"❌ Missing packages: {', '.join(missing)}")
        print("   Run: pip install -r requirements.txt")
        return False
    
    print("✅ All dependencies installed")
    return True

def check_database():
    """Check database connection"""
    print("\n🔍 Checking database connection...")
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        from sqlalchemy import text
        from backend.database import get_engine
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
            print("✅ Database connection successful")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("   Make sure PostgreSQL is running")
        print("   Check DATABASE_URL in .env")
        return False

def check_migrations():
    """Check if migrations are up to date"""
    print("\n🔍 Checking database migrations...")
    
    try:
        import subprocess
        # Run alembic from this interpreter so it works without an activated venv
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "current"],
            capture_output=True,
            text=True
        )
        
        # "alembic current" marks the revision with "(head)" when up to date
        if result.returncode == 0 and "(head)" in result.stdout:
            print("✅ Migrations are up to date")
            return True
        else:
            print("⚠️  Migrations may need to be run")
            print("   Run: alembic upgrade head")
            return False
    except Exception as e:
        print(f"⚠️  Could not check migrations: {e}")
        return False

def check_spotify_config():
    """Verify Spotify OAuth configuration"""
    print("\n🔍 Checking Spotify configuration...")
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")
        
        if not client_id or "your_" in client_id:
            print("❌ SPOTIFY_CLIENT_ID not configured")
            return False
        
        if not client_secret or "your_" in client_secret:
            print("❌ SPOTIFY_CLIENT_SECRET not configured")
            return False
        
        if redirect_uri != "http://127.0.0.1:8000/auth/callback":
            print(f"⚠️  SPOTIFY_REDIRECT_URI is {redirect_uri}")
            print("   Make sure this matches your Spotify app settings")
        
        print("✅ Spotify OAuth configured")
        print(f"   Client ID: {client_id[:10]}...")
        print(f"   Redirect URI: {redirect_uri}")
        return True
        
    except Exception as e:
        print(f"❌ Error checking Spotify config: {e}")
        return False

def main():
    print("=" * 60)
    print("🎵 jamr.io Setup Verification")
    print("=" * 60)
    
    checks = [
        check_env_file,
        check_venv,
        check_dependencies,
        check_database,
        check_migrations,
        check_spotify_config
    ]
    
    results = [check() for check in checks]
    
    print("\n" + "=" * 60)
    print("📊 Summary")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Passed: {passed}/{total} checks")
    
    if all(results):
        print("\n✅ All checks passed! You're ready to run the app.")
        print("\n🚀 Start the server with:")
        print("   ./start_dev.sh")
        print("   or")
        print("   uvicorn backend.main:app --reload")
    else:
        print("\n⚠️  Some checks failed. Please fix the issues above.")
        print("\n📖 See RUNNING_LOCALLY.md for detailed setup instructions")
    
    print("=" * 60)
    
    return 0 if all(results) else 1

if __name__ == "__main__":
    sys.exit(main())
