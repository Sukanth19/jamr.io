"""Input validation and sanitization utilities.

This module provides functions to validate and sanitize user inputs
to prevent XSS attacks and ensure data integrity.
"""

import html
import re
from typing import Tuple


def sanitize_html(text: str) -> str:
    """
    Escape HTML special characters to prevent XSS attacks.
    
    Converts HTML special characters (<, >, &, ", ') to their HTML entity equivalents.
    
    Args:
        text: The text to sanitize
        
    Returns:
        The sanitized text with HTML characters escaped
        
    Example:
        >>> sanitize_html("<script>alert('xss')</script>")
        "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"
    """
    if not text:
        return text
    
    return html.escape(text, quote=True)


def validate_spotify_jam_link(link: str) -> Tuple[bool, str]:
    """
    Validate Spotify Jam link format.
    
    A valid Spotify Jam link must match the pattern:
    https://open.spotify.com/jam/<alphanumeric_id>
    
    Args:
        link: The Spotify Jam link to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if the link is valid, False otherwise
        - error_message: Empty string if valid, error description if invalid
        
    Example:
        >>> validate_spotify_jam_link("https://open.spotify.com/jam/abc123")
        (True, "")
        >>> validate_spotify_jam_link("https://example.com/jam/abc123")
        (False, "Invalid Spotify Jam link format")
    """
    if not link:
        return False, "Spotify Jam link cannot be empty"
    
    # Pattern: https://open.spotify.com/jam/<alphanumeric_id>
    pattern = r'^https://open\.spotify\.com/jam/[a-zA-Z0-9]+$'
    
    if not re.match(pattern, link):
        return False, "Invalid Spotify Jam link format. Must be https://open.spotify.com/jam/<id>"
    
    return True, ""


def validate_room_name(name: str) -> Tuple[bool, str]:
    """
    Validate room name.
    
    Room names must be between 3 and 50 characters (inclusive) after trimming whitespace.
    
    Args:
        name: The room name to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if the name is valid, False otherwise
        - error_message: Empty string if valid, error description if invalid
        
    Example:
        >>> validate_room_name("My Room")
        (True, "")
        >>> validate_room_name("AB")
        (False, "Room name must be between 3 and 50 characters")
    """
    if not name:
        return False, "Room name cannot be empty"
    
    # Trim whitespace for validation - length check is on trimmed string
    trimmed_name = name.strip()
    
    if len(trimmed_name) < 3:
        return False, "Room name must be at least 3 characters"
    
    if len(trimmed_name) > 50:
        return False, "Room name must be at most 50 characters"
    
    return True, ""


def validate_room_description(description: str) -> Tuple[bool, str]:
    """
    Validate room description.
    
    Room descriptions must not exceed 300 characters.
    Empty descriptions are allowed.
    
    Args:
        description: The room description to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if the description is valid, False otherwise
        - error_message: Empty string if valid, error description if invalid
        
    Example:
        >>> validate_room_description("A great room for music lovers")
        (True, "")
        >>> validate_room_description("A" * 301)
        (False, "Room description must be at most 300 characters")
    """
    # Empty descriptions are allowed
    if not description:
        return True, ""
    
    if len(description) > 300:
        return False, "Room description must be at most 300 characters"
    
    return True, ""


def validate_message_content(content: str) -> Tuple[bool, str]:
    """
    Validate chat message content.
    
    Messages must not be empty and must not exceed 500 characters.
    
    Args:
        content: The message content to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if the content is valid, False otherwise
        - error_message: Empty string if valid, error description if invalid
        
    Example:
        >>> validate_message_content("Hello, world!")
        (True, "")
        >>> validate_message_content("")
        (False, "Message content cannot be empty")
        >>> validate_message_content("A" * 501)
        (False, "Message content must be at most 500 characters")
    """
    if not content:
        return False, "Message content cannot be empty"
    
    # Trim whitespace for validation
    content = content.strip()
    
    if len(content) == 0:
        return False, "Message content cannot be empty"
    
    if len(content) > 500:
        return False, "Message content must be at most 500 characters"
    
    return True, ""
