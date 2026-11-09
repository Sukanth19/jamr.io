/**
 * Log in / Sign up Page JavaScript for jamr.io
 */

let mode = 'login';

const MODES = {
    login: {
        title: 'Welcome back',
        subtitle: 'Log in to find your rooms.',
        submit: 'Log in',
        busy: 'Logging in...',
        passwordAutocomplete: 'current-password'
    },
    signup: {
        title: 'Create your account',
        subtitle: 'Pick a username and find people who love the same music.',
        submit: 'Sign up',
        busy: 'Creating account...',
        passwordAutocomplete: 'new-password'
    }
};

/**
 * Where to go after logging in: the page that sent people here, if it's on this site
 * @returns {string} - A same-site path
 */
function nextPath() {
    const next = new URLSearchParams(window.location.search).get('next');
    return next && next.startsWith('/') && !next.startsWith('//') ? next : '/discover';
}

/**
 * Switch between the log in and sign up forms
 * @param {string} newMode - 'login' or 'signup'
 */
function setMode(newMode) {
    mode = newMode;
    const config = MODES[mode];
    const signingUp = mode === 'signup';

    document.getElementById('tab-login').setAttribute('aria-selected', String(!signingUp));
    document.getElementById('tab-signup').setAttribute('aria-selected', String(signingUp));
    document.getElementById('auth-title').textContent = config.title;
    document.getElementById('auth-subtitle').textContent = config.subtitle;
    document.getElementById('auth-submit').textContent = config.submit;
    document.getElementById('password').autocomplete = config.passwordAutocomplete;

    // Sign up shows the display name field and the username/password rules
    document.getElementById('display-name-group').hidden = !signingUp;
    document.getElementById('username-hint').hidden = !signingUp;
    document.getElementById('password-hint').hidden = !signingUp;

    hideAuthError();
    document.getElementById('username').focus();
}

function showAuthError(message) {
    const error = document.getElementById('auth-error');
    error.textContent = message;
    error.classList.add('active');
}

function hideAuthError() {
    const error = document.getElementById('auth-error');
    error.textContent = '';
    error.classList.remove('active');
}

/**
 * Check the form before sending it (the server checks again)
 * @returns {string|null} - An error message, or null if it looks fine
 */
function validateForm(username, password) {
    if (!username || !password) {
        return 'Enter a username and password.';
    }
    if (mode === 'signup') {
        if (!/^[A-Za-z0-9_-]{3,24}$/.test(username)) {
            return 'Usernames are 3-24 characters: letters, numbers, _ or -.';
        }
        if (password.length < 8) {
            return 'Passwords need at least 8 characters.';
        }
    }
    return null;
}

/**
 * Log in or sign up
 * @param {Event} e - Submit event
 */
async function handleSubmit(e) {
    e.preventDefault();
    hideAuthError();

    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const invalid = validateForm(username, password);
    if (invalid) {
        showAuthError(invalid);
        return;
    }

    const body = { username, password };
    if (mode === 'signup') {
        const displayName = document.getElementById('display-name').value.trim();
        if (displayName) body.display_name = displayName;
    }

    const submit = document.getElementById('auth-submit');
    submit.disabled = true;
    submit.textContent = MODES[mode].busy;

    try {
        await apiRequest(mode === 'signup' ? '/auth/signup' : '/auth/login', {
            method: 'POST',
            body: JSON.stringify(body)
        });
        window.location.href = nextPath();
    } catch (error) {
        showAuthError(error.message);
        submit.disabled = false;
        submit.textContent = MODES[mode].submit;
    }
}

/**
 * Initialize the page
 */
function initLoginPage() {
    document.getElementById('tab-login').addEventListener('click', () => setMode('login'));
    document.getElementById('tab-signup').addEventListener('click', () => setMode('signup'));
    document.getElementById('auth-form').addEventListener('submit', handleSubmit);

    setMode(new URLSearchParams(window.location.search).get('mode') === 'signup' ? 'signup' : 'login');

    // Already logged in: skip this page
    getCurrentUser().then(() => {
        window.location.href = nextPath();
    }).catch(() => {});
}

// Initialize page when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLoginPage);
} else {
    initLoginPage();
}
