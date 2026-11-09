/**
 * Control Page JavaScript for jamr.io
 * Staff manage people's roles and suspensions (the API enforces who may do what)
 */

const SUSPEND_OPTIONS = [
    { label: '1 hour', hours: 1 },
    { label: '1 day', hours: 24 },
    { label: '1 week', hours: 24 * 7 },
    { label: 'Until lifted', hours: null }
];

let users = [];
let viewerId = null;

/**
 * Show a short notice (the control page has no socket.js, which defines showToast elsewhere)
 * @param {string} message - Notice text
 * @param {string} type - success or error
 */
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

/**
 * Initialize the control page
 */
async function initControlPage() {
    let me;
    try {
        me = await getCurrentUser();
    } catch (error) {
        window.location.href = '/';
        return;
    }
    initTopbar(me);
    viewerId = me.id;

    if (!isStaff(me)) {
        document.getElementById('control-intro').textContent = 'Only moderators and up can use this page.';
        document.getElementById('user-list').innerHTML = '';
        document.querySelector('.control-toolbar').hidden = true;
        return;
    }

    document.getElementById('control-intro').textContent = roleLevel(me.role) >= ROLE_LEVEL.admin
        ? 'Change roles and suspend people ranked below you.'
        : 'Suspend people ranked below you. Admins can change roles.';

    document.getElementById('user-search').addEventListener('input', renderUsers);
    await loadUsers();
}

/**
 * Load everyone from the API
 */
async function loadUsers() {
    try {
        const data = await apiRequest('/api/admin/users');
        users = data.users;
        renderUsers();
    } catch (error) {
        showError(error.message, document.getElementById('user-list'));
    }
}

/**
 * Render the (filtered) list of people
 */
function renderUsers() {
    const list = document.getElementById('user-list');
    const query = document.getElementById('user-search').value.trim().toLowerCase();
    const shown = users.filter(u => u.display_name.toLowerCase().includes(query));

    document.getElementById('user-total').textContent = `${shown.length} of ${users.length}`;
    list.innerHTML = '';

    if (shown.length === 0) {
        list.innerHTML = '<li class="empty-state">Nobody matches that search.</li>';
        return;
    }

    shown.forEach(user => list.appendChild(createUserRow(user)));
}

/**
 * One person with their role, status and the actions the viewer may take
 * @param {Object} user - User row from the API
 * @returns {HTMLElement}
 */
function createUserRow(user) {
    const li = document.createElement('li');
    li.className = 'user-row';

    // Who
    const who = document.createElement('div');
    who.className = 'user-who';

    const avatar = document.createElement(user.profile_image_url ? 'img' : 'span');
    avatar.className = 'avatar';
    if (user.profile_image_url) {
        avatar.src = user.profile_image_url;
        avatar.alt = '';
    } else {
        avatar.textContent = user.display_name.charAt(0).toUpperCase();
    }

    const text = document.createElement('div');
    const name = document.createElement('div');
    name.className = 'user-name';
    name.textContent = user.display_name;
    const badge = createRoleBadge(user.role);
    if (badge) name.appendChild(badge);

    const meta = document.createElement('div');
    meta.className = 'user-meta';
    meta.textContent = user.suspended
        ? `Suspended ${formatSuspension(user.suspended_until)}`
        : `Joined ${new Date(user.created_at).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })}`;
    if (user.suspended) meta.classList.add('suspended');

    text.append(name, meta);
    who.append(avatar, text);
    li.appendChild(who);

    // Actions
    const actions = document.createElement('div');
    actions.className = 'user-actions';

    if (user.assignable_roles.length > 0) {
        const select = document.createElement('select');
        select.className = 'input select';
        select.setAttribute('aria-label', `Role for ${user.display_name}`);
        user.assignable_roles.forEach(role => {
            const option = document.createElement('option');
            option.value = role;
            option.textContent = role.charAt(0).toUpperCase() + role.slice(1);
            option.selected = role === user.role;
            select.appendChild(option);
        });
        select.addEventListener('change', () => changeRole(user, select.value));
        actions.appendChild(select);
    }

    if (user.can_moderate) {
        if (user.suspended) {
            const lift = document.createElement('button');
            lift.className = 'btn btn-secondary btn-sm';
            lift.textContent = 'Lift suspension';
            lift.addEventListener('click', () => setSuspension(user, 'lift'));
            actions.appendChild(lift);
        } else {
            const select = document.createElement('select');
            select.className = 'input select';
            select.setAttribute('aria-label', `Suspend ${user.display_name}`);
            select.innerHTML = '<option value="">Suspend…</option>';
            SUSPEND_OPTIONS.forEach((opt, i) => {
                const option = document.createElement('option');
                option.value = String(i);
                option.textContent = opt.label;
                select.appendChild(option);
            });
            select.addEventListener('change', () => {
                if (select.value === '') return;
                setSuspension(user, SUSPEND_OPTIONS[Number(select.value)]);
            });
            actions.appendChild(select);
        }
    }

    if (!actions.hasChildNodes()) {
        const none = document.createElement('span');
        none.className = 'user-meta';
        none.textContent = user.id === viewerId ? "That's you" : 'Outranks you';
        actions.appendChild(none);
    }

    li.appendChild(actions);
    return li;
}

/**
 * Replace a user in the list with the API's updated version and re-render
 * @param {Object} updated - User row from the API
 */
function replaceUser(updated) {
    users = users.map(u => (u.id === updated.id ? updated : u));
    renderUsers();
}

/**
 * Change someone's role
 * @param {Object} user - User row
 * @param {string} role - New role
 */
async function changeRole(user, role) {
    try {
        const updated = await apiRequest(`/api/admin/users/${user.id}/role`, {
            method: 'PUT',
            body: JSON.stringify({ role })
        });
        replaceUser(updated);
        showToast(`${user.display_name} is now ${role === 'user' ? 'a regular user' : `a ${role}`}`, 'success');
    } catch (error) {
        showToast(error.message, 'error');
        renderUsers();
    }
}

/**
 * Suspend someone, or lift their suspension
 * @param {Object} user - User row
 * @param {Object|string} option - A SUSPEND_OPTIONS entry, or 'lift'
 */
async function setSuspension(user, option) {
    try {
        const updated = option === 'lift'
            ? await apiRequest(`/api/admin/users/${user.id}/suspend`, { method: 'DELETE' })
            : await apiRequest(`/api/admin/users/${user.id}/suspend`, {
                method: 'POST',
                body: JSON.stringify({ hours: option.hours })
            });
        replaceUser(updated);
        showToast(option === 'lift' ? `Lifted ${user.display_name}'s suspension` : `Suspended ${user.display_name}`, 'success');
    } catch (error) {
        showToast(error.message, 'error');
        renderUsers();
    }
}

// Initialize page when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initControlPage);
} else {
    initControlPage();
}
