/**
 * Account Page JavaScript for jamr.io
 * Display name, username/password and the optional Spotify connection
 */

let me = null;

/**
 * Show a success or error message in a section
 * @param {string} id - Message element ID
 * @param {string} text - Message (empty clears it)
 * @param {boolean} isError - Error styling instead of success
 */
function setMessage(id, text, isError = false) {
    const el = document.getElementById(id);
    el.textContent = text;
    el.className = text ? (isError ? 'form-error active' : 'form-success') : '';
}

/**
 * Fill in the page from the current user
 */
function render() {
    document.getElementById('display-name').value = me.display_name;
    
    // Login: Spotify-made accounts pick a username the first time
    const hasPassword = me.has_password;
    document.getElementById('login-intro').textContent = hasPassword
        ? `You log in as @${me.username}.`
        : 'Pick a username and password so you can log in without Spotify.';
    document.getElementById('new-username-group').hidden = Boolean(me.username);
    document.getElementById('current-password-group').hidden = !hasPassword;
    document.getElementById('password-submit').textContent = hasPassword ? 'Change password' : 'Set username and password';
    
    // Spotify connection
    const status = document.getElementById('spotify-status');
    status.innerHTML = '';
    const label = document.createElement('span');
    
    if (me.spotify_connected) {
        label.innerHTML = '<strong>Connected</strong>. Shared artists are on.';
        status.appendChild(label);
        
        const disconnect = document.createElement('button');
        disconnect.type = 'button';
        disconnect.className = 'btn btn-secondary btn-sm';
        disconnect.textContent = 'Disconnect';
        disconnect.disabled = !hasPassword;
        disconnect.title = hasPassword ? '' : 'Set a password first, or you won\'t be able to log in';
        disconnect.addEventListener('click', disconnectSpotify);
        status.appendChild(disconnect);
    } else {
        label.textContent = 'Not connected.';
        status.appendChild(label);
        
        const connect = document.createElement('a');
        connect.className = 'btn btn-secondary btn-sm';
        connect.href = '/auth/spotify';
        connect.textContent = 'Connect Spotify';
        status.appendChild(connect);
    }
}

async function saveProfile(e) {
    e.preventDefault();
    const displayName = document.getElementById('display-name').value.trim();
    if (!displayName) {
        setMessage('profile-message', 'Display name can\'t be empty.', true);
        return;
    }
    
    try {
        me = await apiRequest('/auth/me', { method: 'PATCH', body: JSON.stringify({ display_name: displayName }) });
        initTopbar(me);
        render();
        setMessage('profile-message', 'Saved.');
    } catch (error) {
        setMessage('profile-message', error.message, true);
    }
}

async function savePassword(e) {
    e.preventDefault();
    const body = { new_password: document.getElementById('new-password').value };
    if (!me.username) body.username = document.getElementById('new-username').value.trim();
    if (me.has_password) body.current_password = document.getElementById('current-password').value;
    
    if (body.new_password.length < 8) {
        setMessage('password-message', 'Passwords need at least 8 characters.', true);
        return;
    }
    if (!me.username && !/^[A-Za-z0-9_-]{3,24}$/.test(body.username)) {
        setMessage('password-message', 'Usernames are 3-24 characters: letters, numbers, _ or -.', true);
        return;
    }
    
    try {
        const hadPassword = me.has_password;
        me = await apiRequest('/auth/me/password', { method: 'PUT', body: JSON.stringify(body) });
        document.getElementById('password-form').reset();
        render();
        setMessage('password-message', hadPassword ? 'Password changed.' : `Done. You can now log in as @${me.username}.`);
    } catch (error) {
        setMessage('password-message', error.message, true);
    }
}

async function disconnectSpotify() {
    if (!confirm('Disconnect Spotify? Shared artists will stop showing for you.')) return;
    
    try {
        me = await apiRequest('/auth/me/spotify', { method: 'DELETE' });
        render();
        setMessage('spotify-message', 'Spotify disconnected.');
    } catch (error) {
        setMessage('spotify-message', error.message, true);
    }
}

/**
 * Initialize the account page
 */
async function initAccountPage() {
    me = await getCurrentUser();
    initTopbar(me);
    render();
    
    document.getElementById('profile-form').addEventListener('submit', saveProfile);
    document.getElementById('password-form').addEventListener('submit', savePassword);
    
    // Coming back from connecting Spotify
    const result = new URLSearchParams(window.location.search).get('spotify');
    if (result === 'connected') {
        setMessage('spotify-message', 'Spotify connected. Your top artists will show up in rooms.');
    } else if (result === 'taken') {
        setMessage('spotify-message', 'That Spotify account is already connected to another jamr.io account.', true);
    }
    if (result) {
        history.replaceState(null, '', '/account');
    }
}

// Initialize page when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAccountPage);
} else {
    initAccountPage();
}
