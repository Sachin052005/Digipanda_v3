/**
 * TECHPANDA CRM - Global Command Palette (Ctrl+K / Cmd+K)
 * Fast, keyboard-first navigation and lead search with strict RBAC branch scoping.
 */
(function () {
  'use strict';

  var backdrop = document.getElementById('tp-command-palette');
  var input = document.getElementById('tp-palette-input');
  var body = document.getElementById('tp-palette-body');
  var triggerBtn = document.getElementById('tp-search-trigger-btn');
  var debounceTimer = null;
  var selectedIndex = -1;
  var currentItems = [];

  if (!backdrop || !input || !body) {
    return;
  }

  function openPalette() {
    backdrop.classList.add('is-open');
    input.value = '';
    renderDefaultState();
    setTimeout(function () {
      input.focus();
    }, 50);
  }

  function closePalette() {
    backdrop.classList.remove('is-open');
    input.blur();
    selectedIndex = -1;
    currentItems = [];
  }

  function renderDefaultState() {
    selectedIndex = -1;
    currentItems = [];
    body.innerHTML = 
      '<div style="padding: 28px 16px; text-align: center; color: var(--tp-text-muted);">' +
        '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" style="margin-bottom: 8px; opacity: 0.7;">' +
          '<circle cx="11" cy="11" r="8"></circle>' +
          '<line x1="21" y1="21" x2="16.65" y2="16.65"></line>' +
        '</svg>' +
        '<div style="font-weight: 600; font-size: 0.95rem; color: var(--tp-text-primary);">Search Leads & Navigation</div>' +
        '<div style="font-size: 0.8rem; margin-top: 4px;">Type at least 2 characters to search by lead name, phone number, or email...</div>' +
      '</div>';
  }

  function renderLoading() {
    body.innerHTML = 
      '<div style="padding: 24px 16px; text-align: center; color: var(--tp-text-muted);">' +
        '<div style="display: inline-block; width: 22px; height: 22px; border: 2px solid var(--tp-surface-border); border-top-color: var(--tp-primary-500); border-radius: 50%; animation: spin 0.8s linear infinite;"></div>' +
        '<div style="font-size: 0.82rem; margin-top: 8px;">Searching...</div>' +
      '</div>';
  }

  function renderResults(data) {
    var leads = data.leads || [];
    var actions = data.actions || [];
    currentItems = [];
    selectedIndex = -1;

    if (leads.length === 0 && actions.length === 0) {
      body.innerHTML = 
        '<div style="padding: 28px 16px; text-align: center; color: var(--tp-text-muted);">' +
          '<div style="font-weight: 600; font-size: 0.9rem; color: var(--tp-text-primary);">No matching results found</div>' +
          '<div style="font-size: 0.8rem; margin-top: 4px;">Try searching with a different name, phone, or keyword.</div>' +
        '</div>';
      return;
    }

    var html = '';

    if (actions.length > 0) {
      html += '<div class="tp-palette-section-title">Navigation & Shortcuts</div>';
      actions.forEach(function (act) {
        var itemIndex = currentItems.length;
        currentItems.push(act);
        html += 
          '<a href="' + act.url + '" class="tp-palette-item" data-index="' + itemIndex + '">' +
            '<div class="tp-palette-item-icon">' +
              '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>' +
            '</div>' +
            '<div class="tp-palette-item-content">' +
              '<div class="tp-palette-item-title">' + escapeHtml(act.title) + '</div>' +
            '</div>' +
            '<span class="tp-kbd-shortcut">↵ Go</span>' +
          '</a>';
      });
    }

    if (leads.length > 0) {
      html += '<div class="tp-palette-section-title">Leads (' + leads.length + ')</div>';
      leads.forEach(function (lead) {
        var itemIndex = currentItems.length;
        currentItems.push(lead);
        html += 
          '<a href="' + lead.url + '" class="tp-palette-item" data-index="' + itemIndex + '">' +
            '<div class="tp-palette-item-icon">' +
              '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>' +
            '</div>' +
            '<div class="tp-palette-item-content">' +
              '<div class="tp-palette-item-title">' + escapeHtml(lead.name) + '</div>' +
              '<div class="tp-palette-item-subtitle">' +
                '<span>' + escapeHtml(lead.phone) + '</span>' +
                (lead.branch ? '<span class="tp-palette-badge">' + escapeHtml(lead.branch) + '</span>' : '') +
              '</div>' +
            '</div>' +
            '<span class="tp-palette-badge" style="margin-left: auto;">' + escapeHtml(lead.status) + '</span>' +
          '</a>';
      });
    }

    body.innerHTML = html;

    if (currentItems.length > 0) {
      setSelectedIndex(0);
    }
  }

  function setSelectedIndex(idx) {
    var items = body.querySelectorAll('.tp-palette-item');
    items.forEach(function (el) {
      el.classList.remove('is-selected');
    });

    if (idx >= 0 && idx < items.length) {
      selectedIndex = idx;
      items[selectedIndex].classList.add('is-selected');
      items[selectedIndex].scrollIntoView({ block: 'nearest' });
    } else {
      selectedIndex = -1;
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // Keyboard navigation & search input events
  input.addEventListener('input', function () {
    var query = input.value.trim();
    clearTimeout(debounceTimer);

    if (query.length < 2) {
      renderDefaultState();
      return;
    }

    renderLoading();
    debounceTimer = setTimeout(function () {
      fetch('/api/quick-search/?q=' + encodeURIComponent(query), {
        headers: { 'Accept': 'application/json' }
      })
      .then(function (res) {
        if (!res.ok) throw new Error('Network error');
        return res.json();
      })
      .then(function (data) {
        renderResults(data);
      })
      .catch(function (err) {
        body.innerHTML = 
          '<div style="padding: 20px; text-align: center; color: var(--tp-call-failed); font-size: 0.85rem;">' +
            'Failed to load search results. Please check your connection.' +
          '</div>';
      });
    }, 180);
  });

  input.addEventListener('keydown', function (e) {
    var items = body.querySelectorAll('.tp-palette-item');

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (items.length > 0) {
        var next = (selectedIndex + 1) % items.length;
        setSelectedIndex(next);
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (items.length > 0) {
        var prev = (selectedIndex - 1 + items.length) % items.length;
        setSelectedIndex(prev);
      }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (selectedIndex >= 0 && selectedIndex < currentItems.length) {
        var targetUrl = currentItems[selectedIndex].url;
        if (targetUrl) {
          window.location.href = targetUrl;
        }
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      closePalette();
    }
  });

  // Global keydown: Ctrl+K / Cmd+K
  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
      e.preventDefault();
      if (backdrop.classList.contains('is-open')) {
        closePalette();
      } else {
        openPalette();
      }
    }
  });

  // Trigger button click
  if (triggerBtn) {
    triggerBtn.addEventListener('click', function () {
      openPalette();
    });
  }

  // Backdrop click dismissal
  backdrop.addEventListener('click', function (e) {
    if (e.target === backdrop) {
      closePalette();
    }
  });

  var closeBtn = document.getElementById('tp-palette-close-btn');
  if (closeBtn) {
    closeBtn.addEventListener('click', function () {
      closePalette();
    });
  }

})();
