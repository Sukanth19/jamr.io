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

        // Handle non-OK responses
        if (!response.ok) {
            let errorMessage = `HTTP error! status: ${response.status}`;
            
            try {
                const errorData = await response.json();
                errorMessage = errorData.error?.message || errorData.message || errorMessage;
            } catch (e) {
                // If response is not JSON, use status text
                errorMessage = response.statusText || errorMessage;
            }
            
            throw new Error(errorMessage);
        }

        // Parse and return JSON response
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
    
    return await apiRequest(endpoint);
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
    return await apiRequest(`/api/rooms/${roomId}/messages`);
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
 * @param {string} message - Error message
 * @param {HTMLElement} container - Container element (optional)
 */
function showError(message, container = null) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error';
    errorDiv.textContent = message;
    
    if (container) {
        container.innerHTML = '';
        container.appendChild(errorDiv);
    } else {
        // Show as toast notification (simple implementation)
        errorDiv.style.position = 'fixed';
        errorDiv.style.top = '20px';
        errorDiv.style.right = '20px';
        errorDiv.style.zIndex = '9999';
        errorDiv.style.maxWidth = '400px';
        document.body.appendChild(errorDiv);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            errorDiv.remove();
        }, 5000);
    }
}

/**
 * Show loading state
 * @param {HTMLElement} container - Container element
 * @param {string} message - Loading message
 */
function showLoading(container, message = 'Loading...') {
    container.innerHTML = `<div class="loading">${escapeHtml(message)}</div>`;
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
