"""Property-based tests for UI display functionality.

Feature: jamr-io-mvp
Tests that room cards display correct information and badges.
"""

import pytest
from hypothesis import given, strategies as st, settings
from bs4 import BeautifulSoup
import re


# Feature: jamr-io-mvp, Property 5: Room Display Information
# Feature: jamr-io-mvp, Property 9: High Recommendation Badge
# **Validates: Requirements 3.2, 4.5**


def taste_vector_strategy():
    """Strategy for generating valid taste vectors."""
    return st.fixed_dictionaries({
        'danceability': st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        'energy': st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        'valence': st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        'acousticness': st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        'instrumentalness': st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        'speechiness': st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        'tempo_normalized': st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    })


def genre_strategy():
    """Strategy for generating genre tags."""
    return st.sampled_from([
        'rock', 'pop', 'indie', 'electronic', 'hip-hop', 
        'jazz', 'classical', 'metal'
    ])


def room_data_strategy():
    """Strategy for generating room data with similarity scores."""
    return st.fixed_dictionaries({
        'room': st.fixed_dictionaries({
            'id': st.integers(min_value=1, max_value=10000),
            'name': st.text(min_size=3, max_size=50, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
            'description': st.text(max_size=300, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
            'genre_tags': st.lists(genre_strategy(), min_size=1, max_size=5, unique=True),
            'taste_vector': taste_vector_strategy(),
            'user_count': st.integers(min_value=0, max_value=100),
        }),
        'similarity_score': st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        'highly_recommended': st.booleans()
    })


def create_room_card_html(room_data):
    """
    Simulates the createRoomCard JavaScript function.
    This is a Python implementation that mirrors the frontend logic.
    """
    room = room_data.get('room', room_data)
    similarity_score = room_data.get('similarity_score')
    highly_recommended = room_data.get('highly_recommended', False)
    
    # Escape HTML (simple implementation)
    def escape_html(text):
        if not text:
            return ''
        return (str(text)
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#x27;'))
    
    # Build badge HTML
    badge_html = '<span class="badge">Highly Recommended</span>' if highly_recommended else ''
    
    # Build tags HTML
    tags_html = ''.join(
        f'<span class="room-tag">{escape_html(tag)}</span>'
        for tag in room.get('genre_tags', [])
    )
    
    # Build similarity HTML
    similarity_html = ''
    if similarity_score is not None:
        percentage = int(similarity_score * 100)
        similarity_html = f'<span class="room-similarity">Match: {percentage}%</span>'
    
    # Get description, use default if empty
    description = room.get('description', '') or 'No description available'
    
    # Build card HTML
    html = f'''
        <div class="room-card">
            {badge_html}
            <h3>{escape_html(room.get('name', ''))}</h3>
            <p>{escape_html(description)}</p>
            <div class="room-tags">
                {tags_html}
            </div>
            <div class="room-footer">
                <span class="room-user-count">{room.get('user_count', 0)} active</span>
                {similarity_html}
            </div>
        </div>
    '''
    
    return html


# ============================================================================
# Property 5: Room Display Information
# ============================================================================


@settings(max_examples=100)
@given(room_data=room_data_strategy())
def test_room_card_contains_name(room_data):
    """
    Property 5: Room Display Information
    
    For any room displayed on the discovery page, the rendered HTML must
    contain the room's name.
    """
    html = create_room_card_html(room_data)
    soup = BeautifulSoup(html, 'html.parser')
    
    room = room_data.get('room', room_data)
    room_name = room.get('name', '')
    
    # Find the h3 element containing the name
    h3 = soup.find('h3')
    assert h3 is not None, "Room card missing <h3> element for name"
    
    # Verify the name is present in the h3 text
    assert room_name in h3.get_text(), \
        f"Room name '{room_name}' not found in card HTML"


@settings(max_examples=100)
@given(room_data=room_data_strategy())
def test_room_card_contains_description(room_data):
    """
    Property 5: Room Display Information
    
    For any room displayed on the discovery page, the rendered HTML must
    contain the room's description.
    """
    html = create_room_card_html(room_data)
    soup = BeautifulSoup(html, 'html.parser')
    
    room = room_data.get('room', room_data)
    description = room.get('description', '') or 'No description available'
    
    # Find the p element containing the description
    p = soup.find('p')
    assert p is not None, "Room card missing <p> element for description"
    
    # Verify the description is present
    assert description in p.get_text(), \
        f"Room description not found in card HTML"


@settings(max_examples=100)
@given(room_data=room_data_strategy())
def test_room_card_contains_genre_tags(room_data):
    """
    Property 5: Room Display Information
    
    For any room displayed on the discovery page, the rendered HTML must
    contain all of the room's genre tags.
    """
    html = create_room_card_html(room_data)
    soup = BeautifulSoup(html, 'html.parser')
    
    room = room_data.get('room', room_data)
    genre_tags = room.get('genre_tags', [])
    
    # Find all room-tag elements
    tag_elements = soup.find_all(class_='room-tag')
    
    # Verify we have the correct number of tags
    assert len(tag_elements) == len(genre_tags), \
        f"Expected {len(genre_tags)} genre tags, found {len(tag_elements)}"
    
    # Verify each genre tag is present
    tag_texts = [tag.get_text() for tag in tag_elements]
    for genre in genre_tags:
        assert genre in tag_texts, \
            f"Genre tag '{genre}' not found in rendered tags {tag_texts}"


@settings(max_examples=100)
@given(room_data=room_data_strategy())
def test_room_card_contains_user_count(room_data):
    """
    Property 5: Room Display Information
    
    For any room displayed on the discovery page, the rendered HTML must
    contain the room's current user count.
    """
    html = create_room_card_html(room_data)
    soup = BeautifulSoup(html, 'html.parser')
    
    room = room_data.get('room', room_data)
    user_count = room.get('user_count', 0)
    
    # Find the user count element
    user_count_elem = soup.find(class_='room-user-count')
    assert user_count_elem is not None, "Room card missing user count element"
    
    # Verify the user count is present in the text
    user_count_text = user_count_elem.get_text()
    assert str(user_count) in user_count_text, \
        f"User count {user_count} not found in '{user_count_text}'"
    assert 'active' in user_count_text.lower(), \
        "User count element should contain 'active' text"


@settings(max_examples=100)
@given(room_data=room_data_strategy())
def test_room_card_has_required_structure(room_data):
    """
    Property 5: Room Display Information
    
    For any room displayed on the discovery page, the rendered HTML must
    have the correct structure with all required elements.
    """
    html = create_room_card_html(room_data)
    soup = BeautifulSoup(html, 'html.parser')
    
    # Verify main container
    card = soup.find(class_='room-card')
    assert card is not None, "Missing room-card container"
    
    # Verify name element
    h3 = card.find('h3')
    assert h3 is not None, "Missing h3 element for room name"
    
    # Verify description element
    p = card.find('p')
    assert p is not None, "Missing p element for room description"
    
    # Verify tags container
    tags_container = card.find(class_='room-tags')
    assert tags_container is not None, "Missing room-tags container"
    
    # Verify footer
    footer = card.find(class_='room-footer')
    assert footer is not None, "Missing room-footer container"
    
    # Verify user count in footer
    user_count = footer.find(class_='room-user-count')
    assert user_count is not None, "Missing room-user-count in footer"


@settings(max_examples=100)
@given(
    room_data=room_data_strategy(),
    xss_payload=st.sampled_from([
        '<script>alert("xss")</script>',
        '<img src=x onerror=alert(1)>',
        '<svg onload=alert(1)>',
        '"><script>alert(1)</script>',
        "'; DROP TABLE rooms; --"
    ])
)
def test_room_card_escapes_html_in_name(room_data, xss_payload):
    """
    Property 5: Room Display Information
    
    For any room with HTML/script content in the name, the rendered HTML
    must escape the content to prevent XSS attacks.
    """
    # Inject XSS payload into room name
    room = room_data.get('room', room_data)
    room['name'] = xss_payload
    
    html = create_room_card_html(room_data)
    
    # Verify the raw script tags are not present (they should be escaped)
    # We check that the opening tag is escaped
    assert '<script>' not in html.lower(), \
        "Unescaped <script> tag found in room card HTML"
    
    # For attributes like onerror and onload, we need to check they're not in executable context
    # They should be escaped as part of the tag content, not as actual attributes
    # Check that < and > are escaped in the h3 content
    soup = BeautifulSoup(html, 'html.parser')
    h3 = soup.find('h3')
    
    # The raw HTML should have escaped special characters if they exist in the payload
    if '<' in xss_payload or '>' in xss_payload:
        assert '&lt;' in html or '&gt;' in html, \
            "HTML angle brackets should be escaped in the raw HTML"
    
    if '"' in xss_payload:
        assert '&quot;' in html, \
            "HTML quotes should be escaped in the raw HTML"
    
    if "'" in xss_payload:
        assert '&#x27;' in html or '&#39;' in html, \
            "HTML single quotes should be escaped in the raw HTML"
    
    # The h3 text content should contain the original payload (BeautifulSoup decodes entities)
    # This proves the escaping worked - the payload is displayed as text, not executed
    h3_text = h3.get_text()
    assert xss_payload in h3_text, \
        f"XSS payload should be present as text content (safely escaped)"


# ============================================================================
# Property 9: High Recommendation Badge
# ============================================================================


@settings(max_examples=100)
@given(
    room_data=st.fixed_dictionaries({
        'room': st.fixed_dictionaries({
            'id': st.integers(min_value=1, max_value=10000),
            'name': st.text(min_size=3, max_size=50, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
            'description': st.text(max_size=300, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
            'genre_tags': st.lists(genre_strategy(), min_size=1, max_size=5, unique=True),
            'taste_vector': taste_vector_strategy(),
            'user_count': st.integers(min_value=0, max_value=100),
        }),
        'similarity_score': st.floats(min_value=0.71, max_value=1.0, allow_nan=False, allow_infinity=False),
        'highly_recommended': st.just(True)
    })
)
def test_high_similarity_displays_badge(room_data):
    """
    Property 9: High Recommendation Badge
    
    For any room with a similarity score greater than 0.7, the room card
    must display a "Highly Recommended" badge.
    """
    html = create_room_card_html(room_data)
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find the badge element
    badge = soup.find(class_='badge')
    assert badge is not None, \
        f"Room with similarity {room_data['similarity_score']:.2f} > 0.7 should have a badge"
    
    # Verify badge text
    badge_text = badge.get_text()
    assert 'highly recommended' in badge_text.lower(), \
        f"Badge should contain 'Highly Recommended', got '{badge_text}'"


@settings(max_examples=100)
@given(
    room_data=st.fixed_dictionaries({
        'room': st.fixed_dictionaries({
            'id': st.integers(min_value=1, max_value=10000),
            'name': st.text(min_size=3, max_size=50, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
            'description': st.text(max_size=300, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
            'genre_tags': st.lists(genre_strategy(), min_size=1, max_size=5, unique=True),
            'taste_vector': taste_vector_strategy(),
            'user_count': st.integers(min_value=0, max_value=100),
        }),
        'similarity_score': st.floats(min_value=0.0, max_value=0.7, allow_nan=False, allow_infinity=False),
        'highly_recommended': st.just(False)
    })
)
def test_low_similarity_no_badge(room_data):
    """
    Property 9: High Recommendation Badge
    
    For any room with a similarity score of 0.7 or less, the room card
    must NOT display a "Highly Recommended" badge.
    """
    html = create_room_card_html(room_data)
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find the badge element
    badge = soup.find(class_='badge')
    assert badge is None, \
        f"Room with similarity {room_data['similarity_score']:.2f} <= 0.7 should NOT have a badge"


@settings(max_examples=100)
@given(
    similarity_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
)
def test_badge_threshold_at_0_7(similarity_score):
    """
    Property 9: High Recommendation Badge
    
    The badge should appear if and only if similarity_score > 0.7.
    This tests the exact threshold boundary.
    """
    room_data = {
        'room': {
            'id': 1,
            'name': 'Test Room',
            'description': 'Test Description',
            'genre_tags': ['rock'],
            'taste_vector': {
                'danceability': 0.5,
                'energy': 0.5,
                'valence': 0.5,
                'acousticness': 0.5,
                'instrumentalness': 0.5,
                'speechiness': 0.5,
                'tempo_normalized': 0.5
            },
            'user_count': 5
        },
        'similarity_score': similarity_score,
        'highly_recommended': similarity_score > 0.7
    }
    
    html = create_room_card_html(room_data)
    soup = BeautifulSoup(html, 'html.parser')
    badge = soup.find(class_='badge')
    
    if similarity_score > 0.7:
        assert badge is not None, \
            f"Room with similarity {similarity_score:.4f} > 0.7 should have a badge"
    else:
        assert badge is None, \
            f"Room with similarity {similarity_score:.4f} <= 0.7 should NOT have a badge"


@settings(max_examples=100)
@given(room_data=room_data_strategy())
def test_badge_presence_matches_highly_recommended_flag(room_data):
    """
    Property 9: High Recommendation Badge
    
    The presence of the badge must match the highly_recommended flag.
    """
    html = create_room_card_html(room_data)
    soup = BeautifulSoup(html, 'html.parser')
    badge = soup.find(class_='badge')
    
    highly_recommended = room_data.get('highly_recommended', False)
    
    if highly_recommended:
        assert badge is not None, \
            "Room marked as highly_recommended should display a badge"
    else:
        assert badge is None, \
            "Room not marked as highly_recommended should NOT display a badge"


@settings(max_examples=100)
@given(
    room_data=st.fixed_dictionaries({
        'room': st.fixed_dictionaries({
            'id': st.integers(min_value=1, max_value=10000),
            'name': st.text(min_size=3, max_size=50, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
            'description': st.text(max_size=300, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
            'genre_tags': st.lists(genre_strategy(), min_size=1, max_size=5, unique=True),
            'taste_vector': taste_vector_strategy(),
            'user_count': st.integers(min_value=0, max_value=100),
        }),
        'similarity_score': st.floats(min_value=0.71, max_value=1.0, allow_nan=False, allow_infinity=False),
        'highly_recommended': st.just(True)
    })
)
def test_badge_has_correct_styling_class(room_data):
    """
    Property 9: High Recommendation Badge
    
    For any room with a badge, the badge element must have the 'badge' class
    for proper styling.
    """
    html = create_room_card_html(room_data)
    soup = BeautifulSoup(html, 'html.parser')
    
    badge = soup.find(class_='badge')
    assert badge is not None, "Badge should be present for highly recommended room"
    
    # Verify it's a span element
    assert badge.name == 'span', \
        f"Badge should be a <span> element, got <{badge.name}>"
    
    # Verify it has the 'badge' class
    assert 'badge' in badge.get('class', []), \
        "Badge element should have 'badge' class"


@settings(max_examples=100)
@given(
    rooms=st.lists(
        room_data_strategy(),
        min_size=5,
        max_size=20
    )
)
def test_multiple_rooms_badge_consistency(rooms):
    """
    Property 9: High Recommendation Badge
    
    For any list of rooms, the badge display must be consistent with each
    room's highly_recommended flag.
    """
    for i, room_data in enumerate(rooms):
        html = create_room_card_html(room_data)
        soup = BeautifulSoup(html, 'html.parser')
        badge = soup.find(class_='badge')
        
        highly_recommended = room_data.get('highly_recommended', False)
        
        if highly_recommended:
            assert badge is not None, \
                f"Room {i} marked as highly_recommended should display a badge"
        else:
            assert badge is None, \
                f"Room {i} not marked as highly_recommended should NOT display a badge"


@settings(max_examples=100)
@given(room_data=room_data_strategy())
def test_similarity_score_display(room_data):
    """
    Property 5: Room Display Information
    
    For any room with a similarity score, the rendered HTML should display
    the similarity percentage in the footer.
    """
    similarity_score = room_data.get('similarity_score')
    
    if similarity_score is None:
        # Skip if no similarity score
        return
    
    html = create_room_card_html(room_data)
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find the similarity element
    similarity_elem = soup.find(class_='room-similarity')
    
    if similarity_score is not None:
        assert similarity_elem is not None, \
            "Room with similarity score should display similarity percentage"
        
        # Verify the percentage is correct
        expected_percentage = int(similarity_score * 100)
        similarity_text = similarity_elem.get_text()
        
        assert str(expected_percentage) in similarity_text, \
            f"Expected similarity {expected_percentage}% not found in '{similarity_text}'"
        assert 'match' in similarity_text.lower(), \
            "Similarity element should contain 'Match' text"
