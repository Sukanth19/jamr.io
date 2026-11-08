// Landing page JavaScript - Fetch and display featured rooms and statistics

const API_BASE = window.location.origin;

/**
 * Fetch data from API endpoint
 */
async function fetchAPI(endpoint) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('API fetch error:', error);
        throw error;
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Create a room card element
 */
function createRoomCard(room) {
    const card = document.createElement('div');
    card.className = 'room-card';

    // Create tags HTML
    const tagsHtml = (room.genre_tags || [])
        .map(tag => `<span class="room-tag">${escapeHtml(tag)}</span>`)
        .join('');

    const count = room.user_count || 0;

    card.innerHTML = `
        <h3>${escapeHtml(room.name)}</h3>
        <p>${escapeHtml(room.description || 'No description yet')}</p>
        <div class="room-tags">
            ${tagsHtml}
        </div>
        <div class="room-footer">
            <span class="room-user-count">${count > 0 ? `${count} listening now` : 'Nobody here yet'}</span>
        </div>
    `;

    return card;
}

/**
 * Fetch and display statistics and featured rooms (public endpoint, no login)
 */
async function loadFeaturedRooms() {
    const container = document.getElementById('rooms-container');

    try {
        const data = await fetchAPI('/api/rooms/featured');

        document.getElementById('active-users').textContent = data.stats.active_users;
        document.getElementById('active-rooms').textContent = data.stats.rooms;

        container.innerHTML = '';

        if (data.rooms.length === 0) {
            container.innerHTML = '<div class="empty-state">No rooms yet. Log in and start the first one!</div>';
            return;
        }

        data.rooms.forEach(room => {
            container.appendChild(createRoomCard(room));
        });
    } catch (error) {
        console.error('Failed to load featured rooms:', error);
        document.getElementById('active-users').textContent = '–';
        document.getElementById('active-rooms').textContent = '–';
        container.innerHTML = '<div class="empty-state">Couldn\'t load rooms right now.</div>';
    }
}

/**
 * If the visitor is already logged in, point the buttons at their rooms
 */
async function updateCallsToAction() {
    try {
        await fetchAPI('/auth/me');
    } catch (error) {
        return;  // Not logged in: keep "Login with Spotify"
    }

    const heroCta = document.getElementById('hero-cta');
    heroCta.href = '/discover';
    heroCta.textContent = 'Open your rooms';

    const topbarCta = document.getElementById('topbar-cta');
    topbarCta.href = '/discover';
    topbarCta.textContent = 'Your rooms';
}

/**
 * Initialize the landing page
 */
async function initLandingPage() {
    await Promise.all([
        loadFeaturedRooms(),
        updateCallsToAction()
    ]);
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLandingPage);
} else {
    initLandingPage();
}
