/**
 * Room Page JavaScript for jamr.io
 * Manages room state, chat messages, and real-time updates
 */

// Room state
let currentRoom = null;
let currentRoomId = null;
let currentUser = null;
let activeUsers = [];
let messages = [];

// Consecutive messages from the same person within this window are grouped
const MESSAGE_GROUP_WINDOW_MS = 5 * 60 * 1000;

/**
 * Initialize room page
 */
async function initRoomPage() {
    // Get room ID from URL
    currentRoomId = getRoomIdFromUrl();
    
    if (!currentRoomId) {
        showError('Invalid room ID');
        setTimeout(() => {
            window.location.href = '/discover';
        }, 2000);
        return;
    }
    
    // Load the logged-in user (for the top bar and to mark own messages)
    try {
        currentUser = await getCurrentUser();
        initTopbar(currentUser);
    } catch (error) {
        console.error('Error loading user:', error);
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
            window.location.href = '/discover';
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
            tagSpan.className = 'chip';
            tagSpan.textContent = tag;
            tagsContainer.appendChild(tagSpan);
        });
    }
    
    // Update Jam link if exists
    if (room.active_jam_link) {
        updateJamLinkDisplay(room.active_jam_link);
    }
    
    // Owners and staff who outrank the owner can delete the room
    document.getElementById('delete-room-btn').hidden = !canManageRoom();
    
    updateSuspendedState();
}

/**
 * Whether the current user may manage this room (mirrors can_manage_room)
 * @returns {boolean}
 */
function canManageRoom() {
    if (!currentUser || !currentRoom) return false;
    if (currentRoom.owner_id === currentUser.id) return true;
    return isStaff(currentUser) && roleLevel(currentUser.role) > roleLevel(currentRoom.owner_role);
}

/**
 * Whether the current user may delete a message (mirrors can_delete_message)
 * @param {number} authorId - Message author's user ID
 * @param {string} authorRole - Message author's role
 * @returns {boolean}
 */
function canDeleteMessage(authorId, authorRole) {
    if (!currentUser || !currentRoom) return false;
    if (authorId === currentUser.id) return true;
    const mine = roleLevel(currentUser.role);
    const theirs = roleLevel(authorRole);
    if (currentRoom.owner_id === currentUser.id && mine >= theirs) return true;
    return isStaff(currentUser) && mine > theirs;
}

/**
 * Disable posting while the user is suspended
 */
function updateSuspendedState() {
    const suspended = isSuspended(currentUser);
    const notice = document.getElementById('suspended-notice');
    
    notice.hidden = !suspended;
    if (suspended) {
        notice.textContent = `You're suspended from posting ${formatSuspension(currentUser.suspended_until)}. You can still read along.`;
    }
    
    ['message-input', 'send-message-btn', 'jam-link-input', 'update-jam-link-btn'].forEach(id => {
        document.getElementById(id).disabled = suspended;
    });
}

/**
 * Delete the room after confirmation, then go back to the room list
 */
async function deleteRoom() {
    if (!confirm('Delete this room and all its messages? This can\'t be undone.')) return;
    
    try {
        await apiRequest(`/api/rooms/${currentRoomId}`, { method: 'DELETE' });
        window.location.href = '/discover';
    } catch (error) {
        showToast(error.message, 'error');
    }
}

/**
 * Delete a message (the server broadcasts message_deleted to everyone)
 * @param {number} messageId - Message ID
 */
async function deleteMessage(messageId) {
    try {
        await apiRequest(`/api/rooms/${currentRoomId}/messages/${messageId}`, { method: 'DELETE' });
    } catch (error) {
        showToast(error.message, 'error');
    }
}

/**
 * Remove a deleted message from the chat
 * @param {number} messageId - Message ID
 */
function removeMessageElement(messageId) {
    const element = document.querySelector(`.message[data-message-id="${messageId}"]`);
    if (!element) return;
    
    // If this message carried the name/time header, hand it to the next one in its group
    const next = element.nextElementSibling;
    if (!element.classList.contains('grouped') && next && next.classList.contains('grouped')
        && next.dataset.userId === element.dataset.userId) {
        next.classList.remove('grouped');
    }
    element.remove();
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
    
    // The API returns newest first; show oldest at the top
    const chronological = [...messageList].sort(
        (a, b) => new Date(a.created_at) - new Date(b.created_at)
    );
    chronological.forEach(msg => {
        appendMessage(msg.username, msg.content, msg.created_at, false, msg.user_id, msg.id, msg.user_role);
    });
}

/**
 * Append a message to the chat
 * @param {string} username - Sender username
 * @param {string} content - Message content
 * @param {string} timestamp - Message timestamp
 * @param {boolean} shouldScroll - Whether to scroll to bottom
 * @param {number} userId - Sender user ID (to mark own messages and group runs)
 * @param {number} messageId - Message ID (for deleting)
 * @param {string} role - Sender's site role (for the staff badge)
 */
function appendMessage(username, content, timestamp, shouldScroll = true, userId = null, messageId = null, role = null) {
    const chatMessages = document.getElementById('chat-messages');
    
    // Remove empty state if exists
    const emptyState = chatMessages.querySelector('.empty-state');
    if (emptyState) {
        emptyState.remove();
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message';
    messageDiv.dataset.userId = userId;
    messageDiv.dataset.timestamp = timestamp;
    if (messageId !== null) {
        messageDiv.dataset.messageId = messageId;
    }
    
    if (currentUser && userId === currentUser.id) {
        messageDiv.classList.add('own');
    }
    
    // Group with the previous message if it's from the same person, shortly before
    const previous = chatMessages.lastElementChild;
    if (previous && previous.classList.contains('message')
        && userId !== null && previous.dataset.userId === String(userId)
        && new Date(timestamp) - new Date(previous.dataset.timestamp) < MESSAGE_GROUP_WINDOW_MS) {
        messageDiv.classList.add('grouped');
    }
    
    const messageHeader = document.createElement('div');
    messageHeader.className = 'message-header';
    
    const usernameSpan = document.createElement('span');
    usernameSpan.className = 'message-username';
    usernameSpan.textContent = username;
    
    const timestampSpan = document.createElement('span');
    timestampSpan.className = 'message-timestamp';
    timestampSpan.textContent = formatTimestamp(timestamp);
    
    messageHeader.appendChild(usernameSpan);
    const badge = createRoleBadge(role);
    if (badge) {
        messageHeader.appendChild(badge);
    }
    messageHeader.appendChild(timestampSpan);
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    messageContent.textContent = content;
    
    // Bubble plus a delete button (shown on hover) for people allowed to delete it
    const messageRow = document.createElement('div');
    messageRow.className = 'message-row';
    messageRow.appendChild(messageContent);
    
    if (messageId !== null && canDeleteMessage(userId, role)) {
        const deleteButton = document.createElement('button');
        deleteButton.className = 'message-delete';
        deleteButton.type = 'button';
        deleteButton.textContent = 'Delete';
        deleteButton.setAttribute('aria-label', 'Delete message');
        deleteButton.addEventListener('click', () => deleteMessage(messageId));
        messageRow.appendChild(deleteButton);
    }
    
    messageDiv.appendChild(messageHeader);
    messageDiv.appendChild(messageRow);
    
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
        autoResizeMessageInput();
    }
}

/**
 * Update Spotify Jam link
 */
function updateJamLink() {
    const input = document.getElementById('jam-link-input');
    
    // Drop the share-tracking query string Spotify adds (?si=...&utm_...)
    const link = input.value.trim().split('#')[0].split('?')[0];
    
    if (link.length === 0) {
        showToast('Please enter a Spotify Jam link', 'error');
        return;
    }
    
    // Same formats as the server: open.spotify.com/socialsession/<id>,
    // open.spotify.com/jam/<id> or spotify.link/<code>
    const jamLinkPattern = /^https:\/\/(open\.spotify\.com\/(socialsession|jam)\/[a-zA-Z0-9]+|spotify\.link\/[a-zA-Z0-9]+)$/;
    if (!jamLinkPattern.test(link)) {
        showToast('That doesn\'t look like a Spotify Jam link. In Spotify, start a Jam, tap Share and copy the link.', 'error');
        return;
    }
    
    // Emit update via Socket.IO and report any server-side rejection
    emitEvent('update_jam_link', { room_id: currentRoomId, link: link }, (response) => {
        if (response && response.error) {
            showToast(response.error, 'error');
            return;
        }
        input.value = '';
    });
}

/**
 * Stop sharing the room's Jam link (the server broadcasts the change)
 */
async function clearJamLink() {
    try {
        await apiRequest(`/api/rooms/${currentRoomId}/jam-link`, { method: 'DELETE' });
    } catch (error) {
        showToast(error.message, 'error');
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
            <a href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(link)}">
                ▶ Join the Spotify Jam
            </a>
        `;
        
        // Owners and staff can stop sharing it
        if (canManageRoom()) {
            const removeButton = document.createElement('button');
            removeButton.type = 'button';
            removeButton.className = 'btn-link jam-link-remove';
            removeButton.textContent = 'Remove link';
            removeButton.addEventListener('click', clearJamLink);
            display.appendChild(removeButton);
        }
    } else {
        display.innerHTML = '<p class="no-link">No Jam running. Start one in Spotify and share the link.</p>';
    }
}

/**
 * Leave room
 */
function leaveRoom() {
    // Leave via Socket.IO only: it removes the membership and notifies the
    // room. Wait for the server's ack before redirecting.
    emitEvent('leave_room', { room_id: currentRoomId }, (response) => {
        if (response && response.error) {
            console.error('Error leaving room:', response.error);
            showToast(response.error, 'error');
            return;
        }

        // Redirect to discover page
        window.location.href = '/discover';
    });
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
 * Grow the message box with its content (capped by max-height in CSS)
 */
function autoResizeMessageInput() {
    const input = document.getElementById('message-input');
    input.style.height = 'auto';
    input.style.height = `${input.scrollHeight}px`;
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
    
    // Message input - update character count and grow with the text
    document.getElementById('message-input').addEventListener('input', () => {
        updateCharCount();
        autoResizeMessageInput();
    });
    
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
    
    // Delete room button (only visible to the owner and staff)
    document.getElementById('delete-room-btn').addEventListener('click', deleteRoom);
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
        appendMessage(data.username, data.content, data.timestamp, true, data.user_id, data.message_id, data.user_role);
    });
    
    // Jam link updated event
    socket.on('jam_link_updated', (data) => {
        console.log('Jam link updated:', data);
        
        // Update Jam link display
        updateJamLinkDisplay(data.link);
        
        // Show system message
        appendSystemMessage(data.link ? `${data.updated_by} shared a Spotify Jam` : `${data.updated_by} ended the shared Jam`);
    });
    
    // A message was deleted
    socket.on('message_deleted', (data) => {
        removeMessageElement(data.message_id);
    });
    
    // The room was deleted: everyone goes back to the room list
    socket.on('room_deleted', (data) => {
        showToast(`${data.deleted_by} deleted this room`, 'error');
        setTimeout(() => {
            window.location.href = '/discover';
        }, 2000);
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
        li.dataset.userId = user.user_id;
        
        const avatar = document.createElement('span');
        avatar.className = 'avatar';
        avatar.setAttribute('aria-hidden', 'true');
        avatar.textContent = (user.username || '?').charAt(0).toUpperCase();
        
        const name = document.createElement('span');
        name.textContent = user.username;
        
        li.appendChild(avatar);
        li.appendChild(name);
        
        const badge = createRoleBadge(user.role);
        if (badge) {
            li.appendChild(badge);
        }
        
        if (currentUser && user.user_id === currentUser.id) {
            const you = document.createElement('span');
            you.className = 'you-label';
            you.textContent = '(you)';
            li.appendChild(you);
        }
        
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
