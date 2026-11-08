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
let tasteModal;
let tasteForm;
let tasteFormError;
let tasteGenresDisplay;

// Logged-in user (includes favorite_genres)
let currentUser = null;

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
    modalCloseBtn = createRoomModal.querySelector('.modal-close');
    modalCancelBtn = createRoomModal.querySelector('.modal-cancel');
    formError = document.getElementById('form-error');
    tasteModal = document.getElementById('taste-modal');
    tasteForm = document.getElementById('taste-form');
    tasteFormError = document.getElementById('taste-form-error');
    tasteGenresDisplay = document.getElementById('taste-genres');
    
    // Set up event listeners
    setupEventListeners();
    
    // Load the user's taste; ask for genres if they haven't picked any yet
    await loadCurrentUser();
    if (currentUser && currentUser.favorite_genres.length === 0) {
        openTasteModal();
    }
    
    // Load initial rooms
    await loadRooms();
}

/**
 * Load the logged-in user and show their favorite genres
 */
async function loadCurrentUser() {
    try {
        currentUser = await getCurrentUser();
        initTopbar(currentUser);
        updateTasteDisplay();
    } catch (error) {
        console.error('Error loading user:', error);
    }
}

/**
 * Show the user's favorite genres in the taste summary
 */
function updateTasteDisplay() {
    const genres = currentUser ? currentUser.favorite_genres : [];
    tasteGenresDisplay.innerHTML = genres.length > 0
        ? genres.map(g => `<span class="chip chip-accent">${escapeHtml(g)}</span>`).join('')
        : 'Not set yet';
}

/**
 * Open the favorite genres modal, pre-checking the current picks
 */
function openTasteModal() {
    const picked = currentUser ? currentUser.favorite_genres : [];
    tasteForm.querySelectorAll('input[name="favorite_genres"]').forEach(cb => {
        cb.checked = picked.includes(cb.value);
    });
    hideTasteFormError();
    
    tasteModal.classList.add('active');
    tasteModal.setAttribute('aria-hidden', 'false');
}

/**
 * Close the favorite genres modal
 */
function closeTasteModal() {
    tasteModal.classList.remove('active');
    tasteModal.setAttribute('aria-hidden', 'true');
}

/**
 * Handle favorite genres form submission
 * @param {Event} e - Submit event
 */
async function handleSaveTaste(e) {
    e.preventDefault();
    hideTasteFormError();
    
    const genres = Array.from(tasteForm.querySelectorAll('input[name="favorite_genres"]:checked'))
        .map(cb => cb.value);
    
    if (genres.length < 1 || genres.length > 5) {
        showTasteFormError('Pick between 1 and 5 genres');
        return;
    }
    
    const submitBtn = tasteForm.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Saving...';
    
    try {
        currentUser = await setFavoriteGenres(genres);
        updateTasteDisplay();
        closeTasteModal();
        
        // Re-rank rooms with the new taste
        await loadRooms();
    } catch (error) {
        console.error('Error saving genres:', error);
        showTasteFormError(error.message || 'Failed to save genres. Please try again.');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Save';
    }
}

/**
 * Show favorite genres form error message
 * @param {string} message - Error message
 */
function showTasteFormError(message) {
    tasteFormError.textContent = message;
    tasteFormError.classList.add('active');
}

/**
 * Hide favorite genres form error message
 */
function hideTasteFormError() {
    tasteFormError.textContent = '';
    tasteFormError.classList.remove('active');
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
    
    // Favorite genres modal
    document.getElementById('edit-taste-btn').addEventListener('click', openTasteModal);
    document.getElementById('taste-modal-close').addEventListener('click', closeTasteModal);
    tasteModal.addEventListener('click', (e) => {
        if (e.target === tasteModal) {
            closeTasteModal();
        }
    });
    tasteForm.addEventListener('submit', handleSaveTaste);
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
    card.setAttribute('role', 'link');
    card.tabIndex = 0;
    
    // Navigate to the room on click or Enter
    const openRoom = () => {
        window.location.href = `/room?id=${room.id}`;
    };
    card.addEventListener('click', openRoom);
    card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') openRoom();
    });
    
    const hasPickedGenres = currentUser && currentUser.favorite_genres.length > 0;
    const matchPercent = Math.round((room.similarity_score || 0) * 100);
    const isHighlyRecommended = room.similarity_score && room.similarity_score > 0.7;
    const matched = new Set(room.matched_genres || []);
    const userCount = room.user_count || 0;
    
    const tagsHtml = room.genre_tags
        .map(tag => `<span class="room-tag${matched.has(tag) ? ' matched' : ''}">${escapeHtml(tag)}</span>`)
        .join('');
    
    card.innerHTML = `
        <div class="room-card-header">
            <h3 class="room-card-title">${escapeHtml(room.name)}</h3>
            ${hasPickedGenres ? `<span class="match-pill${isHighlyRecommended ? ' high' : ''}">${matchPercent}% match</span>` : ''}
        </div>
        <p class="room-card-description${room.description ? '' : ' empty'}">${escapeHtml(room.description || 'No description yet')}</p>
        <div class="room-card-tags">${tagsHtml}</div>
        ${formatSharedArtists(room.shared_artists)}
        <div class="room-card-footer">
            <span class="room-user-count${userCount > 0 ? ' live' : ''}">${userCount > 0 ? `${userCount} listening now` : 'Nobody here yet'}</span>
            ${isHighlyRecommended ? '<span class="badge badge-recommended">Top match</span>' : ''}
        </div>
    `;
    
    return card;
}

/**
 * Describe the artists the user shares with people in a room
 * @param {Array<string>} artists - Shared artist names, most listened first
 * @returns {string} - HTML line, or '' if none are shared
 */
function formatSharedArtists(artists) {
    if (!artists || artists.length === 0) return '';
    
    const shown = artists.slice(0, 2).map(name => `<strong>${escapeHtml(name)}</strong>`).join(', ');
    const more = artists.length > 2 ? ` +${artists.length - 2} more` : '';
    return `<p class="room-shared">🎧 People here also love ${shown}${more}</p>`;
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
        window.location.href = `/room?id=${newRoom.id}`;
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
