"""Integration tests for landing page functionality.

Feature: jamr-io-mvp
Task: 10. Frontend - Landing page
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_landing_page_serves_html():
    """
    Test that the root endpoint serves the landing page HTML.
    
    **Validates: Requirements 11.1**
    """
    response = client.get("/")
    
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert b"jamr.io" in response.content
    assert b"Sign up" in response.content


def test_landing_page_has_hero_section():
    """
    Test that the landing page includes a hero section.
    
    **Validates: Requirements 11.2**
    """
    response = client.get("/")
    
    assert response.status_code == 200
    assert b"Find your music community" in response.content
    assert b"hero" in response.content


def test_landing_page_has_signup_and_login_buttons():
    """
    Test that the landing page links to sign up and log in (Spotify is
    optional, offered on the login page).
    
    **Validates: Requirements 11.3**
    """
    response = client.get("/")
    
    assert response.status_code == 200
    assert b'href="/login?mode=signup"' in response.content
    assert b'href="/login"' in response.content


def test_login_page_offers_password_and_spotify_login():
    response = client.get("/login")
    
    assert response.status_code == 200
    assert b'id="auth-form"' in response.content
    assert b'href="/auth/spotify"' in response.content


def test_landing_page_has_statistics_section():
    """
    Test that the landing page includes statistics section.
    
    **Validates: Requirements 11.5**
    """
    response = client.get("/")
    
    assert response.status_code == 200
    assert b"active-users" in response.content
    assert b"active-rooms" in response.content
    assert b"Active Users" in response.content
    assert b"Active Rooms" in response.content


def test_landing_page_has_featured_rooms_section():
    """
    Test that the landing page includes featured rooms section.
    
    **Validates: Requirements 11.4**
    """
    response = client.get("/")
    
    assert response.status_code == 200
    assert b"Featured Rooms" in response.content
    assert b"rooms-container" in response.content


def test_landing_page_loads_css():
    """
    Test that the landing page references CSS files.
    
    **Validates: Requirements 10.1, 10.2, 10.3, 10.4**
    """
    response = client.get("/")
    
    assert response.status_code == 200
    assert b"/static/css/main.css" in response.content
    assert b"/static/css/landing.css" in response.content


def test_landing_page_loads_javascript():
    """
    Test that the landing page references JavaScript file.
    
    **Validates: Requirements 11.4, 11.5**
    """
    response = client.get("/")
    
    assert response.status_code == 200
    assert b"/static/js/landing.js" in response.content


def test_static_css_files_accessible():
    """
    Test that CSS files are accessible via static file serving.
    
    **Validates: Requirements 10.1, 10.2, 10.3, 10.4**
    """
    # Test main.css
    response = client.get("/static/css/main.css")
    assert response.status_code == 200
    assert "text/css" in response.headers.get("content-type", "")
    
    # Test landing.css
    response = client.get("/static/css/landing.css")
    assert response.status_code == 200
    assert "text/css" in response.headers.get("content-type", "")


def test_static_javascript_accessible():
    """
    Test that JavaScript file is accessible via static file serving.
    
    **Validates: Requirements 11.4, 11.5**
    """
    response = client.get("/static/js/landing.js")
    
    assert response.status_code == 200
    assert "javascript" in response.headers.get("content-type", "").lower() or \
           "text/plain" in response.headers.get("content-type", "")


def test_landing_page_responsive_meta_tag():
    """
    Test that the landing page includes responsive viewport meta tag.
    
    **Validates: Requirements 10.1, 10.2, 10.3**
    """
    response = client.get("/")
    
    assert response.status_code == 200
    assert b'name="viewport"' in response.content
    assert b"width=device-width" in response.content


def test_featured_rooms_endpoint_is_public_and_hides_messages(db_session):
    """
    The landing page's featured rooms endpoint works without login and only
    exposes room summaries.
    """
    from backend.database import get_db
    from backend.models import Room, Message, User
    
    owner = User(spotify_id="featured_owner", display_name="Owner",
                 access_token_encrypted="x", taste_vector={})
    db_session.add(owner)
    db_session.commit()
    busy = Room(name="Busy", genre_tags=["rock"], taste_vector={}, owner_id=owner.id, user_count=5)
    quiet = Room(name="Quiet", genre_tags=["jazz"], taste_vector={}, owner_id=owner.id, user_count=1)
    db_session.add_all([busy, quiet])
    db_session.commit()
    db_session.add(Message(room_id=busy.id, user_id=owner.id, content="secret"))
    db_session.commit()
    
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client.cookies.clear()
        response = client.get("/api/rooms/featured")
    finally:
        app.dependency_overrides.clear()
    
    assert response.status_code == 200
    data = response.json()
    assert [r["name"] for r in data["rooms"]][:2] == ["Busy", "Quiet"]
    assert data["stats"]["active_users"] >= 6
    assert set(data["rooms"][0]) == {"id", "name", "description", "genre_tags", "user_count"}
    assert "secret" not in response.text
