/**
 * Room Page JavaScript for jamr.io
 * Manages room state, chat messages, and real-time updates
 */

// Room state
let currentRoom = null;
let currentRoomId = null;
let activeUsers = [];
let messages = [];

/**
 * Initialize room page
 */
async function initRoomPage() {
    // Get room ID from URL
    currentRoomId = getRoomIdFromUrl();
    
    if (!currentRoomId) {
        showError('Invalid room ID');
        setTimeout(() => {
            window.location.href = '/static/discover.html';
        }, 2000);
        return;
    }
    
    // Load room details and messages
    await loadRoomData();
    
    // Set up event listeners
    setupEventListeners();
    
    // Wait for socket connection before joining room
    if (isSocketConnected()) {
        joinRoom();
    } else {
        window.addEventListener('socket:connected', () => {
            joinRoom();
        });
    }
    
    // Handle reconnection
    window.addEventListener('socket:reconnected', () => {
        joinRoom();
    });
}

/**
 * Get room ID from URL
 * @returns {number|null} - Room ID or null
 */
function getRoomIdFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const roomId = params.get('id');
    return roomId ? parseInt(roomId, 10) : null;
}

/**
 * Load room data from API
 */
async function loadRoomData() {
    try {
        showLoading(document.getElementById('chat-messages'), 'Loading room...');
        
        // Load room details
        currentRoom = await getRoom(currentRoomId);
        
        // Update UI with room details
        updateRoomHeader(currentRoom);
        
        // Load recent messages
        messages = await getMessages(currentRoomId);
        renderMessages(messages);
        
        // Scroll to bottom
        scrollChatToBottom();
        
    } catch (error) {
        console.error('Error loading room data:', error);
        showError(error.message);
        
        // Redirect to discover page after error
        setTimeout(() => {
            window.location.href = '/static/discover.html';
        }, 3000);
    }
}

/**
 * Update room header with room details
 * @param {Object} room - Room data
 */
function updateRoomHeader(room) {
    document.getElementById('room-name').textContent = room.name;
    document.getElementById('room-description').textContent = room.description || '';
    
    // Render genre tags
    const tagsContainer = document.getElementById('room-tags');
    tagsContainer.innerHTML = '';
    
    if (room.genre_tags && room.genre_tags.length > 0) {
        room.genre_tags.forEach(tag => {
            const tagSpan = document.createElement('span');
            tagSpan.className = 'tag';
            tagSpan.textContent = tag;
            tagsContainer.appendChild(tagSpan);
        });
    }
    
    // Update Jam link if exists
    if (room.active_jam_link) {
        updateJamLinkDisplay(room.active_jam_link);
    }
}

/**
 * Render messages in chat area
 * @param {Array} messageList - List of messages
 */
function renderMessages(messageList) {
    const chatMessages = document.getElementById('chat-messages');
    chatMessages.innerHTML = '';
    
    if (messageList.length === 0) {
        showEmptyState(chatMessages, 'No messages yet. Start the conversation!');
        return;
    }
    
    messageList.forEach(msg => {
        appendMessage(msg.username, msg.content, msg.created_at, false);
    });
}

/**
 * Append a message to the chat
 * @param {string} username - Sender username
 * @param {string} content - Message content
 * @param {string} timestamp - Message timestamp
 * @param {boolean} shouldScroll - Whether to scroll to bottom
 */
function appendMessage(username, content, timestamp, shouldScroll = true) {
    const chatMessages = document.getElementById('chat-messages');
    
    // Remove empty state if exists
    const emptyState = chatMessages.querySelector('.empty-state');
    if (emptyState) {
        emptyState.remove();
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message';
    
    const messageHeader = document.createElement('div');
    messageHeader.className = 'message-header';
    
    const usernameSpan = document.createElement('span');
    usernameSpan.className = 'message-username';
    usernameSpan.textContent = username;
    
    const timestampSpan = document.createElement('span');
    timestampSpan.className = 'message-timestamp';
    timestampSpan.textContent = formatTimestamp(timestamp);
    
    messageHeader.appendChild(usernameSpan);
    messageHeader.appendChild(timestampSpan);
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    messageContent.textContent = content;
    
    messageDiv.appendChild(messageHeader);
    messageDiv.appendChild(messageContent);
    
    chatMessages.appendChild(messageDiv);
    
    if (shouldScroll) {
        scrollChatToBottom();
    }
}

/**
 * Append a system message to the chat
 * @param {string} message - System message
 */
function appendSystemMessage(message) {
    const chatMessages = document.getElementById('chat-messages');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'system-message';
    messageDiv.textContent = message;
    
    chatMessages.appendChild(messageDiv);
    scrollChatToBottom();
}

/**
 * Format timestamp for display
 * @param {string} timestamp - ISO timestamp
 * @returns {string} - Formatted time
 */
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    
    // If today, show time only
    if (date.toDateString() === now.toDateString()) {
        return date.toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    }
    
    // Otherwise show date and time
    return date.toLocaleString('en-US', { 
        month: 'short', 
        day: 'numeric', 
        hour: '2-digit', 
        minute: '2-digit' 
    });
}

/**
 * Scroll chat to bottom
 */
function scrollChatToBottom() {
    const chatMessages = document.getElementById('chat-messages');
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Join room via Socket.IO
 */
function joinRoom() {
    if (!currentRoomId) return;
    
    console.log('Joining room:', currentRoomId);
    emitEvent('join_room', { room_id: currentRoomId });
}

/**
 * Send message
 */
function sendMessage() {
    const input = document.getElementById('message-input');
    const content = input.value.trim();
    
    if (content.length === 0) {
        return;
    }
    
    if (content.length > 500) {
        showToast('Message too long (max 500 characters)', 'error');
        return;
    }
    
    // Emit message via Socket.IO
    const success = emitEvent('send_message', {
        room_id: currentRoomId,
        content: content
    });
    
    if (success) {
        // Clear input
        input.value = '';
        updateCharCount();
    }
}

/**
 * Update Spotify Jam link
 */
function updateJamLink() {
    const input = document.getElementById('jam-link-input');
    const link = input.value.trim();
    
    if (link.length === 0) {
        showToast('Please enter a Spotify Jam link', 'error');
        return;
    }
    
    // Validate Spotify Jam link format
    const jamLinkPattern = /^https:\/\/open\.spotify\.com\/jam\/[a-zA-Z0-9]+/;
    if (!jamLinkPattern.test(link)) {
        showToast('Invalid Spotify Jam link format', 'error');
        return;
    }
    
    // Emit update via Socket.IO
    const success = emitEvent('update_jam_link', {
        room_id: currentRoomId,
        link: link
    });
    
    if (success) {
        // Clear input
        input.value = '';
    }
}

/**
 * Update Jam link display
 * @param {string} link - Spotify Jam link
 */
function updateJamLinkDisplay(link) {
    const display = document.getElementById('jam-link-display');
    
    if (link) {
        display.innerHTML = `
            <a href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">
                ${escapeHtml(link)}
            </a>
        `;
    } else {
        display.innerHTML = '<p class="no-link">No active Jam link. Share one below!</p>';
    }
}

/**
 * Leave room
 */
async function leaveRoom() {
    try {
        // Emit leave event via Socket.IO
        emitEvent('leave_room', { room_id: currentRoomId });
        
        // Call API to leave room
        await apiRequest(`/api/rooms/${currentRoomId}/leave`, {
            method: 'POST'
        });
        
        // Redirect to discover page
        window.location.href = '/static/discover.html';
        
    } catch (error) {
        console.error('Error leaving room:', error);
        showToast(error.message, 'error');
    }
}

/**
 * Update character count
 */
function updateCharCount() {
    const input = document.getElementById('message-input');
    const charCount = document.getElementById('char-count');
    const length = input.value.length;
    
    charCount.textContent = `${length}/500`;
    
    // Update styling based on length
    charCount.classList.remove('warning', 'error');
    if (length > 450) {
        charCount.classList.add('error');
    } else if (length > 400) {
        charCount.classList.add('warning');
    }
}

/**
 * Set up event listeners
 */
function setupEventListeners() {
    // Send message button
    document.getElementById('send-message-btn').addEventListener('click', sendMessage);
    
    // Message input - send on Enter (but not Shift+Enter)
    document.getElementById('message-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Message input - update character count
    document.getElementById('message-input').addEventListener('input', updateCharCount);
    
    // Update Jam link button
    document.getElementById('update-jam-link-btn').addEventListener('click', updateJamLink);
    
    // Jam link input - update on Enter
    document.getElementById('jam-link-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            updateJamLink();
        }
    });
    
    // Leave room button
    document.getElementById('leave-room-btn').addEventListener('click', () => {
        if (confirm('Are you sure you want to leave this room?')) {
            leaveRoom();
        }
    });
}

/**
 * Show error message
 * @param {string} message - Error message
 */
function showError(message) {
    showToast(message, 'error');
}

/**
 * Set up Socket.IO event listeners for real-time updates
 */
function setupSocketListeners() {
    // User joined event
    socket.on('user_joined', (data) => {
        console.log('User joined:', data);
        
        // Add user to active users list
        addUserToActiveList(data.user_id, data.username);
        
        // Show system message
        appendSystemMessage(`${data.username} joined the room`);
    });
    
    // User left event
    socket.on('user_left', (data) => {
        console.log('User left:', data);
        
        // Remove user from active users list
        removeUserFromActiveList(data.user_id);
        
        // Show system message
        appendSystemMessage(`${data.username} left the room`);
    });
    
    // New message event
    socket.on('new_message', (data) => {
        console.log('New message:', data);
        
        // Append message to chat
        appendMessage(data.username, data.content, data.timestamp, true);
    });
    
    // Jam link updated event
    socket.on('jam_link_updated', (data) => {
        console.log('Jam link updated:', data);
        
        // Update Jam link display
        updateJamLinkDisplay(data.link);
        
        // Show system message
        appendSystemMessage(`Spotify Jam link updated`);
    });
    
    // User count updated event
    socket.on('user_count_updated', (data) => {
        console.log('User count updated:', data);
        
        // Update user count badge
        updateUserCountDisplay(data.count);
    });
    
    // Active users updated event
    socket.on('active_users_updated', (data) => {
        console.log('Active users updated:', data);
        
        // Refresh active users list
        refreshActiveUsersList(data.users);
    });
}

/**
 * Add user to active users list
 * @param {number} userId - User ID
 * @param {string} username - Username
 */
function addUserToActiveList(userId, username) {
    // Check if user already exists
    const existingUser = activeUsers.find(u => u.user_id === userId);
    if (existingUser) return;
    
    // Add to active users array
    activeUsers.push({ user_id: userId, username: username });
    
    // Update UI
    renderActiveUsers();
}

/**
 * Remove user from active users list
 * @param {number} userId - User ID
 */
function removeUserFromActiveList(userId) {
    // Remove from active users array
    activeUsers = activeUsers.filter(u => u.user_id !== userId);
    
    // Update UI
    renderActiveUsers();
}

/**
 * Refresh active users list
 * @param {Array} users - List of active users
 */
function refreshActiveUsersList(users) {
    activeUsers = users || [];
    renderActiveUsers();
}

/**
 * Render active users list
 */
function renderActiveUsers() {
    const usersList = document.getElementById('active-users-list');
    usersList.innerHTML = '';
    
    if (activeUsers.length === 0) {
        const li = document.createElement('li');
        li.className = 'loading';
        li.textContent = 'No active users';
        usersList.appendChild(li);
        return;
    }
    
    activeUsers.forEach(user => {
        const li = document.createElement('li');
        li.textContent = user.username;
        li.dataset.userId = user.user_id;
        usersList.appendChild(li);
    });
    
    // Update count
    updateUserCountDisplay(activeUsers.length);
}

/**
 * Update user count display
 * @param {number} count - User count
 */
function updateUserCountDisplay(count) {
    const userCountBadge = document.getElementById('user-count');
    userCountBadge.textContent = count;
}

// Initialize page when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        initRoomPage();
        setupSocketListeners();
    });
} else {
    initRoomPage();
    setupSocketListeners();
}
