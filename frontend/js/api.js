/**
 * API Client Utility for jamr.io
 * Provides helper functions for making API requests
 */

const API_BASE = window.location.origin;

/**
 * Generic API request helper with error handling
 * @param {string} endpoint - API endpoint path
 * @param {Object} options - Fetch options
 * @returns {Promise<any>} - Response data
 */
async function apiRequest(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            credentials: 'include', // Send cookies with request
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });

        // Logged out or session expired: go log in, then come back here
        if (response.status === 401 && window.location.pathname !== '/login') {
            const here = window.location.pathname + window.location.search;
            window.location.href = `/login?next=${encodeURIComponent(here)}`;
        }
        
        // Handle non-OK responses
        if (!response.ok) {
            let errorMessage = `HTTP error! status: ${response.status}`;
            
            try {
                const errorData = await response.json();
                errorMessage = errorData.error?.message
                    || errorData.detail?.error?.message
                    || errorData.message
                    || errorMessage;
            } catch (e) {
                // If response is not JSON, use status text
                errorMessage = response.statusText || errorMessage;
            }
            
            throw new Error(errorMessage);
        }

        // Parse and return JSON response (204 No Content has no body)
        if (response.status === 204) {
            return null;
        }
        return await response.json();
    } catch (error) {
        console.error('API request error:', error);
        throw error;
    }
}

/**
 * Get list of rooms with optional filters
 * @param {Object} filters - Optional filters (search, genres)
 * @returns {Promise<Array>} - List of rooms
 */
async function getRooms(filters = {}) {
    const params = new URLSearchParams();
    
    if (filters.search) {
        params.append('search', filters.search);
    }
    
    if (filters.genres && filters.genres.length > 0) {
        // Send genres as comma-separated string
        params.append('genres', filters.genres.join(','));
    }
    
    const queryString = params.toString();
    const endpoint = queryString ? `/api/rooms?${queryString}` : '/api/rooms';
    
    // API responds with { rooms: [...], total }
    const data = await apiRequest(endpoint);
    return data.rooms || [];
}

/**
 * Create a new room
 * @param {Object} roomData - Room data (name, description, genre_tags)
 * @returns {Promise<Object>} - Created room data
 */
async function createRoom(roomData) {
    return await apiRequest('/api/rooms', {
        method: 'POST',
        body: JSON.stringify(roomData)
    });
}

/**
 * Get room details by ID
 * @param {number} roomId - Room ID
 * @returns {Promise<Object>} - Room details
 */
async function getRoom(roomId) {
    return await apiRequest(`/api/rooms/${roomId}`);
}

/**
 * Join a room
 * @param {number} roomId - Room ID
 * @returns {Promise<Object>} - Success response
 */
async function joinRoom(roomId) {
    return await apiRequest(`/api/rooms/${roomId}/join`, {
        method: 'POST'
    });
}

/**
 * Leave a room
 * @param {number} roomId - Room ID
 * @returns {Promise<Object>} - Success response
 */
async function leaveRoom(roomId) {
    return await apiRequest(`/api/rooms/${roomId}/leave`, {
        method: 'POST'
    });
}

/**
 * Get messages for a room
 * @param {number} roomId - Room ID
 * @returns {Promise<Array>} - List of messages
 */
async function getMessages(roomId) {
    // API responds with { room_id, messages: [...], total }
    const data = await apiRequest(`/api/rooms/${roomId}/messages`);
    return data.messages || [];
}

/**
 * Update Spotify Jam link for a room
 * @param {number} roomId - Room ID
 * @param {string} link - Spotify Jam link
 * @returns {Promise<Object>} - Success response
 */
async function updateJamLink(roomId, link) {
    return await apiRequest(`/api/rooms/${roomId}/jam-link`, {
        method: 'PUT',
        body: JSON.stringify({ link })
    });
}

/**
 * Get current authenticated user
 * @returns {Promise<Object>} - User data
 */
async function getCurrentUser() {
    return await apiRequest('/auth/me');
}

/**
 * Set the current user's favorite genres (drives room recommendations)
 * @param {Array<string>} genres - 1-5 genre names
 * @returns {Promise<Object>} - Updated user data
 */
async function setFavoriteGenres(genres) {
    return await apiRequest('/auth/me/genres', {
        method: 'PUT',
        body: JSON.stringify({ genres })
    });
}

/**
 * Logout current user
 * @returns {Promise<Object>} - Success response
 */
async function logout() {
    return await apiRequest('/auth/logout', {
        method: 'POST'
    });
}

/**
 * Escape HTML to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} - Escaped text
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Show error message to user
 * 
 * Displays error messages in toast notifications (default) or inline alerts.
 * Toast notifications auto-dismiss after 5 seconds and appear at the bottom of the screen.
 * Inline alerts replace the container content and remain until cleared.
 * 
 * **Validates: Requirements 10.7**
 * 
 * @param {string} message - Error message to display
 * @param {HTMLElement} container - Optional container element for inline display
 */
function showError(message, container = null) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.setAttribute('role', 'alert');
    errorDiv.setAttribute('aria-live', 'assertive');
    
    // Create error icon
    const iconSpan = document.createElement('span');
    iconSpan.className = 'error-icon';
    iconSpan.textContent = '⚠️';
    iconSpan.setAttribute('aria-hidden', 'true');
    
    // Create error text
    const textSpan = document.createElement('span');
    textSpan.className = 'error-text';
    textSpan.textContent = message;
    
    errorDiv.appendChild(iconSpan);
    errorDiv.appendChild(textSpan);
    
    if (container) {
        // Inline error display
        container.innerHTML = '';
        container.appendChild(errorDiv);
    } else {
        // Toast notification display (styled by .error-toast in main.css)
        errorDiv.classList.add('error-toast');
        
        // Add close button
        const closeButton = document.createElement('button');
        closeButton.className = 'error-close';
        closeButton.textContent = '×';
        closeButton.setAttribute('aria-label', 'Close error message');
        closeButton.onclick = () => errorDiv.remove();
        
        errorDiv.appendChild(closeButton);
        document.body.appendChild(errorDiv);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.style.animation = 'toastOut 0.2s ease-in forwards';
                setTimeout(() => errorDiv.remove(), 200);
            }
        }, 5000);
    }
}

/**
 * Show loading state
 * 
 * Displays a loading indicator with an optional message while async operations
 * are in progress. The loading state replaces the container content.
 * 
 * **Validates: Requirements 10.6**
 * 
 * @param {HTMLElement} container - Container element to show loading state in
 * @param {string} message - Loading message (default: 'Loading...')
 */
function showLoading(container, message = 'Loading...') {
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'loading-state';
    loadingDiv.setAttribute('role', 'status');
    loadingDiv.setAttribute('aria-live', 'polite');
    
    // Create spinner (styled by .loading-spinner in main.css)
    const spinner = document.createElement('div');
    spinner.className = 'loading-spinner';
    spinner.setAttribute('aria-hidden', 'true');
    
    // Create loading text
    const textSpan = document.createElement('span');
    textSpan.className = 'loading-text';
    textSpan.textContent = message;
    
    loadingDiv.appendChild(spinner);
    loadingDiv.appendChild(textSpan);
    
    container.innerHTML = '';
    container.appendChild(loadingDiv);
}

/**
 * Hide loading state
 * 
 * Removes the loading indicator from a container. Should be called after
 * async operations complete (success or failure).
 * 
 * **Validates: Requirements 10.6**
 * 
 * @param {HTMLElement} container - Container element to clear loading state from
 */
function hideLoading(container) {
    if (container) {
        const loadingState = container.querySelector('.loading-state');
        if (loadingState) {
            loadingState.remove();
        }
    }
}

/**
 * Show empty state
 * @param {HTMLElement} container - Container element
 * @param {string} message - Empty state message
 */
function showEmptyState(container, message) {
    container.innerHTML = `<div class="empty-state">${escapeHtml(message)}</div>`;
}

/**
 * Debounce function to limit rate of function calls
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} - Debounced function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Site roles, lowest to highest (mirrors backend/permissions.py)
const ROLE_LEVEL = { user: 0, mod: 1, admin: 2, overseer: 3 };
const ROLE_LABEL = { mod: 'Mod', admin: 'Admin', overseer: 'Overseer' };

/**
 * Numeric rank of a role (unknown or missing roles count as user)
 * @param {string} role - Role name
 * @returns {number} - Rank
 */
function roleLevel(role) {
    return ROLE_LEVEL[role] ?? 0;
}

/**
 * Whether a user is staff (mod and up)
 * @param {Object} user - User from getCurrentUser()
 * @returns {boolean}
 */
function isStaff(user) {
    return Boolean(user) && roleLevel(user.role) >= ROLE_LEVEL.mod;
}

/**
 * Whether a user is currently suspended from posting
 * @param {Object} user - User from getCurrentUser()
 * @returns {boolean}
 */
function isSuspended(user) {
    return Boolean(user && user.suspended_until) && new Date(user.suspended_until) > new Date();
}

/**
 * Describe when a suspension ends
 * @param {string} until - ISO timestamp
 * @returns {string} - e.g. "until Nov 10, 14:00" or "until staff lift it"
 */
function formatSuspension(until) {
    const date = new Date(until);
    if (date.getFullYear() >= 9999) return 'until staff lift it';
    return `until ${date.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`;
}

/**
 * Small badge for staff roles; null for regular users
 * @param {string} role - Role name
 * @returns {HTMLElement|null}
 */
function createRoleBadge(role) {
    if (!ROLE_LABEL[role]) return null;
    const badge = document.createElement('span');
    badge.className = `role-badge role-${role}`;
    badge.textContent = ROLE_LABEL[role];
    return badge;
}

/**
 * Fill in the top bar with the logged-in user and wire up the logout button
 * @param {Object} user - User from getCurrentUser()
 */
function initTopbar(user) {
    const container = document.getElementById('topbar-user');
    if (!container || !user) return;
    
    document.getElementById('topbar-user-name').textContent = user.display_name;
    
    // Staff get a link to the control panel
    if (isStaff(user) && !document.getElementById('topbar-control')) {
        const link = document.createElement('a');
        link.id = 'topbar-control';
        link.href = '/admin';
        link.className = 'btn btn-ghost btn-sm';
        link.textContent = 'Control';
        container.prepend(link);
    }
    
    // Show the Spotify profile picture, or the first letter of the name
    const avatar = document.getElementById('topbar-avatar');
    if (user.profile_image_url) {
        const img = document.createElement('img');
        img.id = 'topbar-avatar';
        img.className = 'avatar';
        img.src = user.profile_image_url;
        img.alt = '';
        avatar.replaceWith(img);
    } else {
        avatar.textContent = (user.display_name || '?').charAt(0).toUpperCase();
    }
    
    // Pages may call this again after the user changes (e.g. a new display name)
    const logoutButton = document.getElementById('logout-btn');
    if (!logoutButton.dataset.bound) {
        logoutButton.dataset.bound = 'true';
        logoutButton.addEventListener('click', async () => {
            try {
                await logout();
            } finally {
                window.location.href = '/';
            }
        });
    }
    
    container.hidden = false;
}
