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
 * Fetch and display active user and room counts
 */
async function loadStatistics() {
    try {
        // Fetch rooms to calculate statistics
        const response = await fetchAPI('/api/rooms');
        
        // Handle different response formats
        const rooms = response.rooms || response || [];
        
        // Calculate total active users across all rooms
        const totalUsers = rooms.reduce((sum, roomData) => {
            // Handle both nested and flat room structures
            const room = roomData.room || roomData;
            return sum + (room.user_count || 0);
        }, 0);
        
        // Count total active rooms
        const totalRooms = rooms.length;
        
        // Update the DOM
        document.getElementById('active-users').textContent = totalUsers;
        document.getElementById('active-rooms').textContent = totalRooms;
    } catch (error) {
        console.error('Failed to load statistics:', error);
        // Show 0 for unauthenticated users or on error
        document.getElementById('active-users').textContent = '0';
        document.getElementById('active-rooms').textContent = '0';
    }
}

/**
 * Create a room card element
 */
function createRoomCard(roomData) {
    const room = roomData.room || roomData;
    
    const card = document.createElement('div');
    card.className = 'room-card';
    
    // Create tags HTML
    const tagsHtml = (room.genre_tags || [])
        .map(tag => `<span class="room-tag">${escapeHtml(tag)}</span>`)
        .join('');
    
    card.innerHTML = `
        <h3>${escapeHtml(room.name)}</h3>
        <p>${escapeHtml(room.description || 'No description available')}</p>
        <div class="room-tags">
            ${tagsHtml}
        </div>
        <div class="room-footer">
            <span class="room-user-count">${room.user_count || 0} active</span>
        </div>
    `;
    
    return card;
}

/**
 * Fetch and display featured rooms
 */
async function loadFeaturedRooms() {
    const container = document.getElementById('rooms-container');
    
    try {
        // Show loading state
        container.innerHTML = '<div class="loading">Loading rooms...</div>';
        
        // Fetch rooms from API
        const response = await fetchAPI('/api/rooms');
        
        // Handle different response formats
        const rooms = response.rooms || response || [];
        
        // Clear loading state
        container.innerHTML = '';
        
        if (rooms.length === 0) {
            container.innerHTML = '<div class="empty-state">No rooms available yet. Be the first to create one!</div>';
            return;
        }
        
        // Display up to 6 featured rooms
        const featuredRooms = rooms.slice(0, 6);
        
        featuredRooms.forEach(roomData => {
            const card = createRoomCard(roomData);
            container.appendChild(card);
        });
        
    } catch (error) {
        console.error('Failed to load featured rooms:', error);
        
        // For unauthenticated users, show a friendly message
        if (error.message.includes('401') || error.message.includes('Unauthorized')) {
            container.innerHTML = '<div class="empty-state">Log in with Spotify to discover rooms that match your music taste!</div>';
        } else {
            container.innerHTML = '<div class="error">Failed to load rooms. Please try again later.</div>';
        }
    }
}

/**
 * Initialize the landing page
 */
async function initLandingPage() {
    // Load statistics and featured rooms in parallel
    await Promise.all([
        loadStatistics(),
        loadFeaturedRooms()
    ]);
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLandingPage);
} else {
    initLandingPage();
}
