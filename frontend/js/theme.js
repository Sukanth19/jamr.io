/**
 * Light / dark mode.
 *
 * Loaded in <head> (not deferred) so the theme is set before the page paints:
 * no flash of the wrong colours. Until the user picks a mode with the toggle,
 * the site follows the system setting (and updates live if that changes).
 * The choice is saved in localStorage under "jamr-theme".
 */
(function () {
    const STORAGE_KEY = 'jamr-theme';
    const root = document.documentElement;
    const systemDark = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

    function savedTheme() {
        try {
            const value = localStorage.getItem(STORAGE_KEY);
            return value === 'light' || value === 'dark' ? value : null;
        } catch (e) {
            return null; // storage blocked (private mode etc.)
        }
    }

    function currentTheme() {
        return savedTheme() || (systemDark && systemDark.matches ? 'dark' : 'light');
    }

    function updateToggle(theme) {
        const button = document.getElementById('theme-toggle');
        if (!button) return;
        const label = theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
        button.setAttribute('aria-label', label);
        button.title = label;
    }

    function applyTheme(theme) {
        root.dataset.theme = theme;
        updateToggle(theme);
    }

    function setTheme(theme) {
        try {
            localStorage.setItem(STORAGE_KEY, theme);
        } catch (e) {
            // Not saved, but still switch for this page
        }
        // Fade colours over instead of snapping
        root.classList.add('theme-switching');
        applyTheme(theme);
        window.setTimeout(() => root.classList.remove('theme-switching'), 300);
    }

    function toggleTheme() {
        setTheme(currentTheme() === 'dark' ? 'light' : 'dark');
    }

    applyTheme(currentTheme());

    if (systemDark) {
        const onSystemChange = () => {
            if (!savedTheme()) applyTheme(currentTheme());
        };
        if (systemDark.addEventListener) systemDark.addEventListener('change', onSystemChange);
        else if (systemDark.addListener) systemDark.addListener(onSystemChange);
    }

    document.addEventListener('DOMContentLoaded', () => {
        const button = document.getElementById('theme-toggle');
        if (!button) return;
        updateToggle(currentTheme());
        button.addEventListener('click', toggleTheme);
    });

    window.jamrTheme = { current: currentTheme, set: setTheme, toggle: toggleTheme };
})();
