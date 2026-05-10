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
 * 
 * Displays error messages in toast notifications (default) or inline alerts.
 * Toast notifications auto-dismiss after 5 seconds and appear in the top-right corner.
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
        // Toast notification display
        errorDiv.classList.add('error-toast');
        errorDiv.style.position = 'fixed';
        errorDiv.style.top = '20px';
        errorDiv.style.right = '20px';
        errorDiv.style.zIndex = '9999';
        errorDiv.style.maxWidth = '400px';
        errorDiv.style.padding = '12px 16px';
        errorDiv.style.backgroundColor = '#dc3545';
        errorDiv.style.color = '#ffffff';
        errorDiv.style.borderRadius = '4px';
        errorDiv.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.2)';
        errorDiv.style.display = 'flex';
        errorDiv.style.alignItems = 'center';
        errorDiv.style.gap = '8px';
        errorDiv.style.animation = 'slideInRight 0.3s ease-out';
        
        // Add close button
        const closeButton = document.createElement('button');
        closeButton.className = 'error-close';
        closeButton.textContent = '×';
        closeButton.setAttribute('aria-label', 'Close error message');
        closeButton.style.marginLeft = 'auto';
        closeButton.style.background = 'none';
        closeButton.style.border = 'none';
        closeButton.style.color = '#ffffff';
        closeButton.style.fontSize = '24px';
        closeButton.style.cursor = 'pointer';
        closeButton.style.padding = '0';
        closeButton.style.lineHeight = '1';
        closeButton.onclick = () => errorDiv.remove();
        
        errorDiv.appendChild(closeButton);
        document.body.appendChild(errorDiv);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.style.animation = 'slideOutRight 0.3s ease-in';
                setTimeout(() => errorDiv.remove(), 300);
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
    
    // Create spinner
    const spinner = document.createElement('div');
    spinner.className = 'loading-spinner';
    spinner.setAttribute('aria-hidden', 'true');
    spinner.style.width = '40px';
    spinner.style.height = '40px';
    spinner.style.border = '4px solid #f3f3f3';
    spinner.style.borderTop = '4px solid #3498db';
    spinner.style.borderRadius = '50%';
    spinner.style.animation = 'spin 1s linear infinite';
    spinner.style.margin = '0 auto 12px';
    
    // Create loading text
    const textSpan = document.createElement('span');
    textSpan.className = 'loading-text';
    textSpan.textContent = escapeHtml(message);
    
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
