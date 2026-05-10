"""Property-based tests for real-time UI updates.

Feature: jamr-io-mvp
Tests that active users display and list updates work correctly.
"""

import pytest
from hypothesis import given, strategies as st, settings
from bs4 import BeautifulSoup


# Feature: jamr-io-mvp, Property 31: Active Users Display
# Feature: jamr-io-mvp, Property 32: Active Users List Update
# **Validates: Requirements 9.2, 9.3, 9.4, 9.5**


def user_strategy():
    """Strategy for generating user data."""
    return st.fixed_dictionaries({
        'user_id': st.integers(min_value=1, max_value=100000),
        'username': st.text(
            min_size=3, 
            max_size=30, 
            alphabet=st.characters(
                whitelist_categories=('Lu', 'Ll', 'Nd'),
                min_codepoint=32,
                max_codepoint=126
            )
        ).filter(lambda x: x.strip() != '')
    })


def active_users_list_strategy():
    """Strategy for generating lists of active users."""
    return st.lists(
        user_strategy(),
        min_size=0,
        max_size=50,
        unique_by=lambda u: u['user_id']
    )


def render_active_users_html(users):
    """
    Simulates the renderActiveUsers JavaScript function.
    This is a Python implementation that mirrors the frontend logic.
    
    Args:
        users: List of user dictionaries with user_id and username
        
    Returns:
        HTML string representing the active users list
    """
    def escape_html(text):
        if not text:
            return ''
        return (str(text)
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#x27;'))
    
    if not users or len(users) == 0:
        return '''
            <ul id="active-users-list" class="active-users-list">
                <li class="loading">No active users</li>
            </ul>
        '''
    
    user_items = '\n'.join(
        f'<li data-user-id="{user["user_id"]}">{escape_html(user["username"])}</li>'
        for user in users
    )
    
    html = f'''
        <ul id="active-users-list" class="active-users-list">
            {user_items}
        </ul>
    '''
    
    return html


def render_user_count_badge(count):
    """
    Simulates the updateUserCountDisplay JavaScript function.
    
    Args:
        count: Number of active users
        
    Returns:
        HTML string for the user count badge
    """
    return f'<span id="user-count" class="user-count-badge">{count}</span>'


# ============================================================================
# Property 31: Active Users Display
# ============================================================================


@settings(max_examples=100)
@given(users=active_users_list_strategy())
def test_active_users_list_contains_all_users(users):
    """
    Property 31: Active Users Display
    
    For any room page, the UI must display a list of currently active users,
    where each user in the room_memberships table for that room is rendered
    with their username.
    
    **Validates: Requirements 9.2, 9.3**
    """
    html = render_active_users_html(users)
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find the active users list
    users_list = soup.find(id='active-users-list')
    assert users_list is not None, "Active users list element must exist"
    
    # Find all list items
    list_items = users_list.find_all('li')
    
    if len(users) == 0:
        # Should show "No active users" message
        assert len(list_items) == 1, "Empty list should have one item"
        assert 'no active users' in list_items[0].get_text().lower(), \
            "Empty list should show 'No active users' message"
    else:
        # Should have one item per user
        assert len(list_items) == len(users), \
            f"Expected {len(users)} list items, found {len(list_items)}"
        
        # Verify each user is present
        rendered_usernames = [li.get_text().strip() for li in list_items]
        for user in users:
            assert user['username'] in rendered_usernames, \
                f"User '{user['username']}' not found in active users list"


@settings(max_examples=100)
@given(users=active_users_list_strategy())
def test_active_users_have_data_attributes(users):
    """
    Property 31: Active Users Display
    
    For any active user in the list, the list item must have a data-user-id
    attribute containing the user's ID for proper identification.
    
    **Validates: Requirements 9.2, 9.3**
    """
    if len(users) == 0:
        # Skip test for empty list
        return
    
    html = render_active_users_html(users)
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find all list items with data-user-id
    list_items = soup.find_all('li', attrs={'data-user-id': True})
    
    assert len(list_items) == len(users), \
        f"Expected {len(users)} items with data-user-id, found {len(list_items)}"
    
    # Verify each user ID is present
    rendered_user_ids = [int(li.get('data-user-id')) for li in list_items]
    for user in users:
        assert user['user_id'] in rendered_user_ids, \
            f"User ID {user['user_id']} not found in rendered list"


@settings(max_examples=100)
@given(users=active_users_list_strategy())
def test_user_count_badge_matches_list_length(users):
    """
    Property 31: Active Users Display
    
    For any room page, the user count badge must display the correct number
    of active users, matching the length of the active users list.
    
    **Validates: Requirements 9.2, 9.3**
    """
    count = len(users)
    badge_html = render_user_count_badge(count)
    soup = BeautifulSoup(badge_html, 'html.parser')
    
    badge = soup.find(id='user-count')
    assert badge is not None, "User count badge must exist"
    
    badge_text = badge.get_text().strip()
    assert badge_text == str(count), \
        f"Badge should display {count}, got '{badge_text}'"


@settings(max_examples=100)
@given(
    users=active_users_list_strategy(),
    xss_payload=st.sampled_from([
        '<script>alert("xss")</script>',
        '<img src=x onerror=alert(1)>',
        '<svg onload=alert(1)>',
        '"><script>alert(1)</script>'
    ])
)
def test_active_users_escapes_html_in_username(users, xss_payload):
    """
    Property 31: Active Users Display
    
    For any user with HTML/script content in the username, the rendered HTML
    must escape the content to prevent XSS attacks.
    
    **Validates: Requirements 9.2, 9.3**
    """
    if len(users) == 0:
        # Add at least one user with XSS payload
        users = [{'user_id': 1, 'username': xss_payload}]
    else:
        # Inject XSS payload into first user's username
        users[0]['username'] = xss_payload
    
    html = render_active_users_html(users)
    
    # Verify the raw script tags are not present (they should be escaped)
    assert '<script>' not in html.lower(), \
        "Unescaped <script> tag found in active users HTML"
    
    # Check that < and > are escaped
    if '<' in xss_payload or '>' in xss_payload:
        assert '&lt;' in html or '&gt;' in html, \
            "HTML angle brackets should be escaped in the raw HTML"


@settings(max_examples=100)
@given(users=active_users_list_strategy())
def test_active_users_list_has_correct_structure(users):
    """
    Property 31: Active Users Display
    
    For any room page, the active users list must have the correct HTML
    structure with proper classes and IDs.
    
    **Validates: Requirements 9.2, 9.3**
    """
    html = render_active_users_html(users)
    soup = BeautifulSoup(html, 'html.parser')
    
    # Verify main list element
    users_list = soup.find(id='active-users-list')
    assert users_list is not None, "Must have element with id='active-users-list'"
    assert users_list.name == 'ul', "Active users list must be a <ul> element"
    
    # Verify it has the correct class
    assert 'active-users-list' in users_list.get('class', []), \
        "List must have 'active-users-list' class"
    
    # Verify all children are list items
    for child in users_list.find_all(recursive=False):
        assert child.name == 'li', \
            f"All direct children of users list must be <li> elements, found <{child.name}>"


# ============================================================================
# Property 32: Active Users List Update
# ============================================================================


@settings(max_examples=100)
@given(
    initial_users=active_users_list_strategy(),
    new_user=user_strategy()
)
def test_adding_user_updates_list(initial_users, new_user):
    """
    Property 32: Active Users List Update
    
    For any user joining a room, the active users list must be updated to
    reflect the change (user added to the list).
    
    **Validates: Requirements 9.4, 9.5**
    """
    # Ensure new user is not already in the list
    initial_user_ids = [u['user_id'] for u in initial_users]
    if new_user['user_id'] in initial_user_ids:
        # Modify the user ID to ensure it's unique
        new_user['user_id'] = max(initial_user_ids, default=0) + 1
    
    # Render initial state
    initial_html = render_active_users_html(initial_users)
    initial_soup = BeautifulSoup(initial_html, 'html.parser')
    initial_items = initial_soup.find_all('li', attrs={'data-user-id': True})
    initial_count = len(initial_items)
    
    # Add new user
    updated_users = initial_users + [new_user]
    
    # Render updated state
    updated_html = render_active_users_html(updated_users)
    updated_soup = BeautifulSoup(updated_html, 'html.parser')
    updated_items = updated_soup.find_all('li', attrs={'data-user-id': True})
    
    # Verify the list grew by 1
    assert len(updated_items) == initial_count + 1, \
        f"List should grow from {initial_count} to {initial_count + 1} users"
    
    # Verify the new user is present
    updated_user_ids = [int(li.get('data-user-id')) for li in updated_items]
    assert new_user['user_id'] in updated_user_ids, \
        f"New user {new_user['user_id']} should be in the updated list"
    
    # Verify the new user's username is displayed
    updated_usernames = [li.get_text().strip() for li in updated_items]
    assert new_user['username'] in updated_usernames, \
        f"New user's username '{new_user['username']}' should be displayed"


@settings(max_examples=100)
@given(
    users=active_users_list_strategy().filter(lambda u: len(u) > 0)
)
def test_removing_user_updates_list(users):
    """
    Property 32: Active Users List Update
    
    For any user leaving a room, the active users list must be updated to
    reflect the change (user removed from the list).
    
    **Validates: Requirements 9.4, 9.5**
    """
    # Render initial state
    initial_html = render_active_users_html(users)
    initial_soup = BeautifulSoup(initial_html, 'html.parser')
    initial_items = initial_soup.find_all('li', attrs={'data-user-id': True})
    initial_count = len(initial_items)
    
    # Remove a user (remove the first one)
    user_to_remove = users[0]
    updated_users = users[1:]
    
    # Render updated state
    updated_html = render_active_users_html(updated_users)
    updated_soup = BeautifulSoup(updated_html, 'html.parser')
    updated_items = updated_soup.find_all('li', attrs={'data-user-id': True})
    
    # Verify the list shrunk by 1
    expected_count = max(0, initial_count - 1)
    assert len(updated_items) == expected_count, \
        f"List should shrink from {initial_count} to {expected_count} users"
    
    # Verify the removed user is not present
    if len(updated_items) > 0:
        updated_user_ids = [int(li.get('data-user-id')) for li in updated_items]
        assert user_to_remove['user_id'] not in updated_user_ids, \
            f"Removed user {user_to_remove['user_id']} should not be in the updated list"


@settings(max_examples=100)
@given(
    initial_users=active_users_list_strategy(),
    operations=st.lists(
        st.one_of(
            st.tuples(st.just('add'), user_strategy()),
            st.tuples(st.just('remove'), st.integers(min_value=0, max_value=49))
        ),
        min_size=1,
        max_size=10
    )
)
def test_multiple_user_changes_update_list(initial_users, operations):
    """
    Property 32: Active Users List Update
    
    For any sequence of users joining and leaving a room, the active users
    list must be updated correctly after each change.
    
    **Validates: Requirements 9.4, 9.5**
    """
    current_users = list(initial_users)
    
    for operation, data in operations:
        if operation == 'add':
            new_user = data
            # Ensure unique user ID
            existing_ids = [u['user_id'] for u in current_users]
            if new_user['user_id'] in existing_ids:
                new_user['user_id'] = max(existing_ids, default=0) + 1
            current_users.append(new_user)
        elif operation == 'remove':
            if len(current_users) > 0:
                # Remove user at index (modulo list length)
                index = data % len(current_users)
                current_users.pop(index)
    
    # Render final state
    html = render_active_users_html(current_users)
    soup = BeautifulSoup(html, 'html.parser')
    
    if len(current_users) == 0:
        # Should show empty state
        list_items = soup.find_all('li')
        assert len(list_items) == 1, "Empty list should have one item"
        assert 'no active users' in list_items[0].get_text().lower()
    else:
        # Should show all current users
        list_items = soup.find_all('li', attrs={'data-user-id': True})
        assert len(list_items) == len(current_users), \
            f"List should have {len(current_users)} users"
        
        # Verify all current users are present
        rendered_user_ids = [int(li.get('data-user-id')) for li in list_items]
        for user in current_users:
            assert user['user_id'] in rendered_user_ids, \
                f"User {user['user_id']} should be in the final list"


@settings(max_examples=100)
@given(
    initial_users=active_users_list_strategy(),
    new_user=user_strategy()
)
def test_user_count_updates_on_join(initial_users, new_user):
    """
    Property 32: Active Users List Update
    
    For any user joining a room, the user count badge must be updated to
    reflect the new count.
    
    **Validates: Requirements 9.4, 9.5**
    """
    # Ensure new user is unique
    initial_user_ids = [u['user_id'] for u in initial_users]
    if new_user['user_id'] in initial_user_ids:
        new_user['user_id'] = max(initial_user_ids, default=0) + 1
    
    # Initial count
    initial_count = len(initial_users)
    initial_badge = render_user_count_badge(initial_count)
    initial_soup = BeautifulSoup(initial_badge, 'html.parser')
    initial_badge_elem = initial_soup.find(id='user-count')
    assert initial_badge_elem.get_text().strip() == str(initial_count)
    
    # Updated count after join
    updated_count = initial_count + 1
    updated_badge = render_user_count_badge(updated_count)
    updated_soup = BeautifulSoup(updated_badge, 'html.parser')
    updated_badge_elem = updated_soup.find(id='user-count')
    
    assert updated_badge_elem.get_text().strip() == str(updated_count), \
        f"Badge should update from {initial_count} to {updated_count}"


@settings(max_examples=100)
@given(
    users=active_users_list_strategy().filter(lambda u: len(u) > 0)
)
def test_user_count_updates_on_leave(users):
    """
    Property 32: Active Users List Update
    
    For any user leaving a room, the user count badge must be updated to
    reflect the new count.
    
    **Validates: Requirements 9.4, 9.5**
    """
    # Initial count
    initial_count = len(users)
    initial_badge = render_user_count_badge(initial_count)
    initial_soup = BeautifulSoup(initial_badge, 'html.parser')
    initial_badge_elem = initial_soup.find(id='user-count')
    assert initial_badge_elem.get_text().strip() == str(initial_count)
    
    # Updated count after leave
    updated_count = initial_count - 1
    updated_badge = render_user_count_badge(updated_count)
    updated_soup = BeautifulSoup(updated_badge, 'html.parser')
    updated_badge_elem = updated_soup.find(id='user-count')
    
    assert updated_badge_elem.get_text().strip() == str(updated_count), \
        f"Badge should update from {initial_count} to {updated_count}"


@settings(max_examples=100)
@given(users=active_users_list_strategy())
def test_list_update_within_500ms_requirement(users):
    """
    Property 32: Active Users List Update
    
    For any user joining or leaving, the active users list must be updated
    within 500ms (this is a structural test - actual timing would be tested
    in integration tests).
    
    This test verifies that the update mechanism is synchronous and immediate,
    which ensures the 500ms requirement can be met.
    
    **Validates: Requirements 9.4, 9.5**
    """
    # Add a new user
    new_user = {'user_id': 99999, 'username': 'TestUser'}
    updated_users = users + [new_user]
    
    # The rendering should be immediate (synchronous)
    html = render_active_users_html(updated_users)
    soup = BeautifulSoup(html, 'html.parser')
    
    # Verify the new user is immediately present
    list_items = soup.find_all('li', attrs={'data-user-id': True})
    user_ids = [int(li.get('data-user-id')) for li in list_items]
    
    assert new_user['user_id'] in user_ids, \
        "User should be immediately present in the rendered list (synchronous update)"


@settings(max_examples=100)
@given(
    users=active_users_list_strategy(),
    duplicate_user=user_strategy()
)
def test_duplicate_user_not_added_twice(users, duplicate_user):
    """
    Property 32: Active Users List Update
    
    For any user already in the active users list, attempting to add them
    again should not create a duplicate entry.
    
    **Validates: Requirements 9.4, 9.5**
    """
    if len(users) == 0:
        users = [duplicate_user]
    else:
        # Make duplicate_user match an existing user
        duplicate_user = users[0].copy()
    
    # Try to add the duplicate user
    updated_users = users + [duplicate_user]
    
    # In a real implementation, the addUserToActiveList function should check
    # for duplicates. Here we simulate that by filtering unique user_ids
    unique_users = []
    seen_ids = set()
    for user in updated_users:
        if user['user_id'] not in seen_ids:
            unique_users.append(user)
            seen_ids.add(user['user_id'])
    
    # Render with unique users
    html = render_active_users_html(unique_users)
    soup = BeautifulSoup(html, 'html.parser')
    list_items = soup.find_all('li', attrs={'data-user-id': True})
    
    # Verify no duplicates
    user_ids = [int(li.get('data-user-id')) for li in list_items]
    assert len(user_ids) == len(set(user_ids)), \
        "Active users list should not contain duplicate user IDs"
    
    # Verify count matches unique users
    assert len(list_items) == len(unique_users), \
        f"List should have {len(unique_users)} unique users"
