/**
 * Room Discovery Page JavaScript
 * Handles room loading, filtering, search, and room creation
 */

// State management
let currentFilters = {
    search: '',
    genres: []
};

// DOM elements
let searchInput;
let genreCheckboxes;
let roomsContainer;
let createRoomBtn;
let createRoomModal;
let createRoomForm;
let modalCloseBtn;
let modalCancelBtn;
let formError;

/**
 * Initialize the discover page
 */
async function initDiscoverPage() {
    // Get DOM elements
    searchInput = document.getElementById('search-input');
    genreCheckboxes = document.querySelectorAll('.genre-checkbox input[type="checkbox"]');
    roomsContainer = document.getElementById('rooms-container');
    createRoomBtn = document.getElementById('create-room-btn');
    createRoomModal = document.getElementById('create-room-modal');
    createRoomForm = document.getElementById('create-room-form');
    modalCloseBtn = document.querySelector('.modal-close');
    modalCancelBtn = document.querySelector('.modal-cancel');
    formError = document.getElementById('form-error');
    
    // Set up event listeners
    setupEventListeners();
    
    // Load initial rooms
    await loadRooms();
}

/**
 * Set up all event listeners
 */
function setupEventListeners() {
    // Search input with debouncing (300ms delay)
    searchInput.addEventListener('input', debounce(handleSearchChange, 300));
    
    // Genre filter checkboxes
    genreCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', handleGenreFilterChange);
    });
    
    // Create room button
    createRoomBtn.addEventListener('click', openCreateRoomModal);
    
    // Modal close buttons
    modalCloseBtn.addEventListener('click', closeCreateRoomModal);
    modalCancelBtn.addEventListener('click', closeCreateRoomModal);
    
    // Close modal when clicking outside
    createRoomModal.addEventListener('click', (e) => {
        if (e.target === createRoomModal) {
            closeCreateRoomModal();
        }
    });
    
    // Create room form submission
    createRoomForm.addEventListener('submit', handleCreateRoom);
}

/**
 * Handle search input change
 */
function handleSearchChange() {
    currentFilters.search = searchInput.value.trim();
    loadRooms();
}

/**
 * Handle genre filter change
 */
function handleGenreFilterChange() {
    // Get all checked genre values
    currentFilters.genres = Array.from(genreCheckboxes)
        .filter(checkbox => checkbox.checked)
        .map(checkbox => checkbox.value);
    
    loadRooms();
}

/**
 * Load and display rooms with current filters
 */
async function loadRooms() {
    try {
        // Show loading state
        showLoading(roomsContainer, 'Loading rooms...');
        
        // Fetch rooms with filters
        const rooms = await getRooms(currentFilters);
        
        // Render rooms
        renderRooms(rooms);
    } catch (error) {
        console.error('Error loading rooms:', error);
        showError('Failed to load rooms. Please try again.', roomsContainer);
    }
}

/**
 * Render rooms in the grid
 * @param {Array} rooms - Array of room objects
 */
function renderRooms(rooms) {
    // Clear container
    roomsContainer.innerHTML = '';
    
    // Check if no rooms found
    if (!rooms || rooms.length === 0) {
        showEmptyState(roomsContainer, 'No rooms found. Try adjusting your filters or create a new room!');
        return;
    }
    
    // Create room cards
    rooms.forEach(room => {
        const roomCard = createRoomCard(room);
        roomsContainer.appendChild(roomCard);
    });
}

/**
 * Create a room card element
 * @param {Object} room - Room data
 * @returns {HTMLElement} - Room card element
 */
function createRoomCard(room) {
    const card = document.createElement('div');
    card.className = 'room-card';
    card.setAttribute('data-room-id', room.id);
    
    // Add click handler to navigate to room
    card.addEventListener('click', () => {
        window.location.href = `/room.html?id=${room.id}`;
    });
    
    // Build card HTML
    const isHighlyRecommended = room.similarity_score && room.similarity_score > 0.7;
    
    card.innerHTML = `
        <div class="room-card-header">
            <h3 class="room-card-title">${escapeHtml(room.name)}</h3>
            ${isHighlyRecommended ? '<span class="badge badge-recommended">Highly Recommended</span>' : ''}
        </div>
        <p class="room-card-description">${escapeHtml(room.description || 'No description provided')}</p>
        <div class="room-card-tags">
            ${room.genre_tags.map(tag => `<span class="room-tag">${escapeHtml(tag)}</span>`).join('')}
        </div>
        <div class="room-card-footer">
            <span class="room-user-count">${room.user_count || 0} ${room.user_count === 1 ? 'user' : 'users'}</span>
        </div>
    `;
    
    return card;
}

/**
 * Open create room modal
 */
function openCreateRoomModal() {
    createRoomModal.classList.add('active');
    createRoomModal.setAttribute('aria-hidden', 'false');
    
    // Reset form
    createRoomForm.reset();
    hideFormError();
    
    // Focus on first input
    document.getElementById('room-name').focus();
}

/**
 * Close create room modal
 */
function closeCreateRoomModal() {
    createRoomModal.classList.remove('active');
    createRoomModal.setAttribute('aria-hidden', 'true');
    
    // Reset form
    createRoomForm.reset();
    hideFormError();
}

/**
 * Handle create room form submission
 * @param {Event} e - Submit event
 */
async function handleCreateRoom(e) {
    e.preventDefault();
    
    // Hide previous errors
    hideFormError();
    
    // Get form data
    const formData = new FormData(createRoomForm);
    const name = formData.get('name').trim();
    const description = formData.get('description').trim();
    
    // Get selected genre tags
    const genreTagCheckboxes = createRoomForm.querySelectorAll('input[name="genre_tags"]:checked');
    const genre_tags = Array.from(genreTagCheckboxes).map(cb => cb.value);
    
    // Validate form
    if (!name || name.length < 3 || name.length > 50) {
        showFormError('Room name must be between 3 and 50 characters');
        return;
    }
    
    if (description && description.length > 300) {
        showFormError('Description must be 300 characters or less');
        return;
    }
    
    if (genre_tags.length === 0) {
        showFormError('Please select at least one genre tag');
        return;
    }
    
    // Prepare room data
    const roomData = {
        name,
        description: description || null,
        genre_tags
    };
    
    try {
        // Disable submit button
        const submitBtn = createRoomForm.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Creating...';
        
        // Create room
        const newRoom = await createRoom(roomData);
        
        // Close modal
        closeCreateRoomModal();
        
        // Navigate to the new room
        window.location.href = `/room.html?id=${newRoom.id}`;
    } catch (error) {
        console.error('Error creating room:', error);
        showFormError(error.message || 'Failed to create room. Please try again.');
        
        // Re-enable submit button
        const submitBtn = createRoomForm.querySelector('button[type="submit"]');
        submitBtn.disabled = false;
        submitBtn.textContent = 'Create Room';
    }
}

/**
 * Show form error message
 * @param {string} message - Error message
 */
function showFormError(message) {
    formError.textContent = message;
    formError.classList.add('active');
}

/**
 * Hide form error message
 */
function hideFormError() {
    formError.textContent = '';
    formError.classList.remove('active');
}

// Initialize page when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDiscoverPage);
} else {
    initDiscoverPage();
}
