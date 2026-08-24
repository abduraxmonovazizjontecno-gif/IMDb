(function () {
    'use strict';

    const THEME_KEY = 'cinema-theme';
    const THEMES = { LIGHT: 'light', DARK: 'dark' };

    function getSystemTheme() {
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return THEMES.DARK;
        }
        return THEMES.LIGHT;
    }

    function getSavedTheme() {
        try {
            return localStorage.getItem(THEME_KEY);
        } catch {
            return null;
        }
    }

    function saveTheme(theme) {
        try {
            localStorage.setItem(THEME_KEY, theme);
        } catch {
            // Fallback for private browsing
        }
    }

    function applyTheme(theme) {
        const isDark = theme === THEMES.DARK;
        if (isDark) {
            document.documentElement.removeAttribute('data-theme');
        } else {
            document.documentElement.setAttribute('data-theme', THEMES.LIGHT);
        }
        document.documentElement.style.colorScheme = theme;
    }

    function initTheme() {
        const savedTheme = getSavedTheme();
        const theme = savedTheme || getSystemTheme();
        applyTheme(theme);
    }

    function toggleTheme() {
        const current = document.documentElement.getAttribute('data-theme') || THEMES.DARK;
        const newTheme = current === THEMES.DARK ? THEMES.LIGHT : THEMES.DARK;
        applyTheme(newTheme);
        saveTheme(newTheme);
    }

    // Initialize theme on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTheme);
    } else {
        initTheme();
    }

    // Setup theme toggle button
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }

    // Listen for system theme changes
    if (window.matchMedia) {
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
            if (!getSavedTheme()) {
                applyTheme(e.matches ? THEMES.DARK : THEMES.LIGHT);
            }
        });
    }
})();
