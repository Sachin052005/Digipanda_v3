/**
 * TECHPANDA CRM - Early Theme Manager (Zero-FOUC)
 * Executes immediately to set data-theme before DOM paint.
 */
(function() {
  'use strict';
  try {
    var THEME_KEY = 'techpanda_theme';
    var savedTheme = localStorage.getItem(THEME_KEY);
    if (!savedTheme) {
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        savedTheme = 'dark';
      } else {
        savedTheme = 'light';
      }
    }
    document.documentElement.setAttribute('data-theme', savedTheme);
  } catch (e) {
    // Graceful fallback if localStorage is blocked
  }
})();
