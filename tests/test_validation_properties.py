"""Property-based tests for input validation.

Feature: jamr-io-mvp
Tests input validation and sanitization properties.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from backend.validators import (
    sanitize_html,
    validate_spotify_jam_link,
    validate_room_name,
    validate_room_description,
    validate_message_content
)


# Property 10: Room Name Validation
# **Validates: Requirements 5.2**
@settings(max_examples=100)
@given(name=st.text(min_size=0, max_size=2))
def test_room_name_too_short_rejected(name):
    """
    Property 10: Room Name Validation (Part 1 - Too Short)
    
    For any room creation attempt, if the room name length is less than 3 characters,
    the platform must reject the creation and return a validation error.
    """
    is_valid, error_message = validate_room_name(name)
    
    assert is_valid is False
    assert len(error_message) > 0
    assert "3" in error_message or "empty" in error_message.lower()


@settings(max_examples=100)
@given(name=st.text(min_size=51, max_size=100, alphabet=st.characters(min_codepoint=33, max_codepoint=126)))
def test_room_name_too_long_rejected(name):
    """
    Property 10: Room Name Validation (Part 2 - Too Long)
    
    For any room creation attempt, if the room name length is greater than 50 characters,
    the platform must reject the creation and return a validation error.
    """
    is_valid, error_message = validate_room_name(name)
    
    assert is_valid is False
    assert len(error_message) > 0
    assert "50" in error_message


@settings(max_examples=100)
@given(name=st.text(min_size=3, max_size=50, alphabet=st.characters(min_codepoint=33, max_codepoint=126)))
def test_room_name_valid_range_accepted(name):
    """
    Property 10: Room Name Validation (Part 3 - Valid Range)
    
    For any room creation attempt, if the room name length is between 3 and 50 characters
    (inclusive), the platform must accept the name.
    """
    is_valid, error_message = validate_room_name(name)
    
    assert is_valid is True
    assert error_message == ""


# Property 11: Room Description Validation
# **Validates: Requirements 5.3**
@settings(max_examples=100)
@given(description=st.text(min_size=301, max_size=500))
def test_room_description_too_long_rejected(description):
    """
    Property 11: Room Description Validation (Part 1 - Too Long)
    
    For any room creation attempt, if the description length exceeds 300 characters,
    the platform must reject the creation and return a validation error.
    """
    is_valid, error_message = validate_room_description(description)
    
    assert is_valid is False
    assert len(error_message) > 0
    assert "300" in error_message


@settings(max_examples=100)
@given(description=st.text(max_size=300, alphabet=st.characters(blacklist_characters=['\x00'])))
def test_room_description_valid_range_accepted(description):
    """
    Property 11: Room Description Validation (Part 2 - Valid Range)
    
    For any room creation attempt, if the description length is at most 300 characters,
    the platform must accept the description.
    """
    is_valid, error_message = validate_room_description(description)
    
    assert is_valid is True
    assert error_message == ""


def test_room_description_empty_accepted():
    """
    Property 11: Room Description Validation (Part 3 - Empty Allowed)
    
    Empty descriptions should be accepted.
    """
    is_valid, error_message = validate_room_description("")
    
    assert is_valid is True
    assert error_message == ""


# Property 24: XSS Sanitization
# **Validates: Requirements 7.6**
@settings(max_examples=100)
@given(content=st.text(min_size=1, max_size=500))
def test_xss_sanitization_escapes_html(content):
    """
    Property 24: XSS Sanitization
    
    For any message content containing HTML special characters (<, >, &, ", '),
    the stored and broadcast content must have these characters escaped to their
    HTML entity equivalents.
    """
    sanitized = sanitize_html(content)
    
    # Verify that dangerous HTML characters are escaped
    # Note: html.escape converts characters to HTML entities like &lt;, &gt;, &amp;, &#x27;, &quot;
    if '<' in content:
        assert '<' not in sanitized or '&lt;' in sanitized
    if '>' in content:
        assert '>' not in sanitized or '&gt;' in sanitized
    
    # Verify that the sanitized content doesn't contain raw HTML tags
    if '<script>' in content:
        assert '<script>' not in sanitized
        assert '&lt;script&gt;' in sanitized


@settings(max_examples=100)
@given(
    tag=st.sampled_from(['script', 'img', 'iframe', 'object', 'embed', 'link', 'style']),
    content=st.text(min_size=0, max_size=100, alphabet=st.characters(blacklist_characters=['<', '>', '&']))
)
def test_xss_sanitization_prevents_common_xss_vectors(tag, content):
    """
    Property 24: XSS Sanitization (Part 2 - Common XSS Vectors)
    
    Verify that common XSS attack vectors are properly escaped.
    """
    xss_payload = f"<{tag}>{content}</{tag}>"
    sanitized = sanitize_html(xss_payload)
    
    # Verify that the tag is escaped
    assert f"<{tag}>" not in sanitized
    assert f"&lt;{tag}&gt;" in sanitized


def test_xss_sanitization_handles_empty_string():
    """
    Property 24: XSS Sanitization (Part 3 - Empty String)
    
    Empty strings should be handled gracefully.
    """
    sanitized = sanitize_html("")
    assert sanitized == ""


def test_xss_sanitization_handles_none():
    """
    Property 24: XSS Sanitization (Part 4 - None)
    
    None values should be handled gracefully.
    """
    sanitized = sanitize_html(None)
    assert sanitized is None


# Property 25: Message Length Validation
# **Validates: Requirements 7.7**
@settings(max_examples=100)
@given(content=st.text(min_size=501, max_size=1000))
def test_message_length_too_long_rejected(content):
    """
    Property 25: Message Length Validation (Part 1 - Too Long)
    
    For any message submission, if the content length exceeds 500 characters,
    the platform must reject the message and return a validation error.
    """
    is_valid, error_message = validate_message_content(content)
    
    assert is_valid is False
    assert len(error_message) > 0
    assert "500" in error_message


@settings(max_examples=100)
@given(content=st.text(min_size=1, max_size=500, alphabet=st.characters(blacklist_characters=['\x00'])))
def test_message_length_valid_range_accepted(content):
    """
    Property 25: Message Length Validation (Part 2 - Valid Range)
    
    For any message submission, if the content length is between 1 and 500 characters
    (inclusive), the platform must accept the message.
    """
    # Skip messages that are only whitespace
    assume(content.strip() != "")
    
    is_valid, error_message = validate_message_content(content)
    
    assert is_valid is True
    assert error_message == ""


def test_message_length_empty_rejected():
    """
    Property 25: Message Length Validation (Part 3 - Empty Rejected)
    
    Empty messages should be rejected.
    """
    is_valid, error_message = validate_message_content("")
    
    assert is_valid is False
    assert len(error_message) > 0
    assert "empty" in error_message.lower()


def test_message_length_whitespace_only_rejected():
    """
    Property 25: Message Length Validation (Part 4 - Whitespace Only Rejected)
    
    Messages containing only whitespace should be rejected.
    """
    is_valid, error_message = validate_message_content("   \t\n  ")
    
    assert is_valid is False
    assert len(error_message) > 0


# Property 26: Spotify Jam Link Validation
# **Validates: Requirements 8.2**
@settings(max_examples=100)
@given(
    jam_id=st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
)
def test_spotify_jam_link_valid_format_accepted(jam_id):
    """
    Property 26: Spotify Jam Link Validation (Part 1 - Valid Format)
    
    For any Spotify Jam link submission, if the link matches the pattern
    https://open.spotify.com/jam/<alphanumeric_id>, the platform must accept it.
    """
    link = f"https://open.spotify.com/jam/{jam_id}"
    is_valid, error_message = validate_spotify_jam_link(link)
    
    assert is_valid is True
    assert error_message == ""


@settings(max_examples=100)
@given(
    domain=st.sampled_from(['example.com', 'spotify.com', 'open.spotify.org', 'spotify.io']),
    jam_id=st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
)
def test_spotify_jam_link_invalid_domain_rejected(domain, jam_id):
    """
    Property 26: Spotify Jam Link Validation (Part 2 - Invalid Domain)
    
    For any Spotify Jam link submission, if the link does not match the pattern
    https://open.spotify.com/jam/*, the platform must reject it.
    """
    link = f"https://{domain}/jam/{jam_id}"
    is_valid, error_message = validate_spotify_jam_link(link)
    
    assert is_valid is False
    assert len(error_message) > 0


@settings(max_examples=100)
@given(
    path=st.sampled_from(['track', 'playlist', 'album', 'artist', 'session']),
    jam_id=st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
)
def test_spotify_jam_link_invalid_path_rejected(path, jam_id):
    """
    Property 26: Spotify Jam Link Validation (Part 3 - Invalid Path)
    
    For any Spotify link that is not a Jam link, the platform must reject it.
    """
    link = f"https://open.spotify.com/{path}/{jam_id}"
    is_valid, error_message = validate_spotify_jam_link(link)
    
    assert is_valid is False
    assert len(error_message) > 0


def test_spotify_jam_link_empty_rejected():
    """
    Property 26: Spotify Jam Link Validation (Part 4 - Empty Rejected)
    
    Empty Spotify Jam links should be rejected.
    """
    is_valid, error_message = validate_spotify_jam_link("")
    
    assert is_valid is False
    assert len(error_message) > 0


def test_spotify_jam_link_http_rejected():
    """
    Property 26: Spotify Jam Link Validation (Part 5 - HTTP Rejected)
    
    HTTP (non-HTTPS) Spotify Jam links should be rejected.
    """
    link = "http://open.spotify.com/jam/abc123"
    is_valid, error_message = validate_spotify_jam_link(link)
    
    assert is_valid is False
    assert len(error_message) > 0


def test_spotify_jam_link_with_special_chars_rejected():
    """
    Property 26: Spotify Jam Link Validation (Part 6 - Special Characters Rejected)
    
    Spotify Jam links with special characters in the ID should be rejected.
    """
    link = "https://open.spotify.com/jam/abc-123_xyz"
    is_valid, error_message = validate_spotify_jam_link(link)
    
    assert is_valid is False
    assert len(error_message) > 0
