/**
 * Socket.IO Client Setup for jamr.io
 * Handles real-time WebSocket communication with the server
 */

// Initialize Socket.IO connection
const socket = io(window.location.origin, {
    withCredentials: true,  // Send cookies for authentication
    transports: ['websocket', 'polling'],  // Prefer WebSocket, fallback to polling
    reconnection: true,  // Enable automatic reconnection
    reconnectionDelay: 1000,  // Initial delay before reconnection attempt
    reconnectionDelayMax: 5000,  // Maximum delay between reconnection attempts
    reconnectionAttempts: Infinity  // Keep trying to reconnect
});

// Connection state tracking
let isConnected = false;
let connectionAttempts = 0;

/**
 * Connection event handler
 */
socket.on('connect', () => {
    console.log('Socket.IO connected:', socket.id);
    isConnected = true;
    connectionAttempts = 0;
    
    // Show connection success notification
    showToast('Connected to server', 'success');
    
    // Trigger custom event for other modules to handle
    window.dispatchEvent(new CustomEvent('socket:connected', {
        detail: { socketId: socket.id }
    }));
});

/**
 * Disconnection event handler
 */
socket.on('disconnect', (reason) => {
    console.log('Socket.IO disconnected:', reason);
    isConnected = false;
    
    // Show disconnection notification
    if (reason === 'io server disconnect') {
        // Server initiated disconnect
        showToast('Disconnected from server', 'error');
    } else {
        // Client-side disconnect or network issue
        showToast('Connection lost. Reconnecting...', 'info');
    }
    
    // Trigger custom event
    window.dispatchEvent(new CustomEvent('socket:disconnected', {
        detail: { reason }
    }));
});

/**
 * Reconnection attempt event handler
 */
socket.io.on('reconnect_attempt', (attemptNumber) => {
    connectionAttempts = attemptNumber;
    console.log(`Reconnection attempt ${attemptNumber}`);
});

/**
 * Reconnection success event handler
 */
socket.io.on('reconnect', (attemptNumber) => {
    console.log(`Reconnected after ${attemptNumber} attempts`);
    showToast('Reconnected to server', 'success');
    
    // Trigger custom event
    window.dispatchEvent(new CustomEvent('socket:reconnected', {
        detail: { attempts: attemptNumber }
    }));
});

/**
 * Reconnection error event handler
 */
socket.io.on('reconnect_error', (error) => {
    console.error('Reconnection error:', error);
    
    if (connectionAttempts > 5) {
        showToast('Unable to reconnect. Please refresh the page.', 'error');
    }
});

/**
 * Reconnection failed event handler
 */
socket.io.on('reconnect_failed', () => {
    console.error('Reconnection failed');
    showToast('Connection failed. Please refresh the page.', 'error');
});

/**
 * Connection error event handler
 */
socket.on('connect_error', (error) => {
    console.error('Connection error:', error);
    
    // Check if it's an authentication error
    if (error.message && error.message.includes('auth')) {
        showToast('Authentication failed. Please log in again.', 'error');
        setTimeout(() => {
            window.location.href = '/';
        }, 2000);
    }
});

/**
 * Generic error event handler
 */
socket.on('error', (error) => {
    console.error('Socket error:', error);
    showToast(error.message || 'An error occurred', 'error');
});

/**
 * Check if socket is connected
 * @returns {boolean} - Connection status
 */
function isSocketConnected() {
    return isConnected && socket.connected;
}

/**
 * Emit event with connection check
 * @param {string} eventName - Event name
 * @param {Object} data - Event data
 * @returns {boolean} - Whether event was emitted
 */
function emitEvent(eventName, data) {
    if (!isSocketConnected()) {
        console.warn('Socket not connected, cannot emit event:', eventName);
        showToast('Not connected to server. Please wait...', 'warning');
        return false;
    }
    
    socket.emit(eventName, data);
    return true;
}

/**
 * Show toast notification
 * @param {string} message - Toast message
 * @param {string} type - Toast type (success, error, info, warning)
 */
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    
    container.appendChild(toast);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 5000);
}

// Add slideOut animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Export for use in other modules
window.socket = socket;
window.isSocketConnected = isSocketConnected;
window.emitEvent = emitEvent;
window.showToast = showToast;
