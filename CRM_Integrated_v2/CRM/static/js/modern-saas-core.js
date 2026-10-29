/**
 * DIGIPANDA CRM - MODERN SAAS CORE INTERACTION ENGINE
 * Keyboard-first shortcuts, one-click copy tooling, tactile feedback, and seamless UX utilities.
 */
(function () {
  'use strict';

  // 1. One-Click Copy Tooltip Engine
  function showCopyFeedback(targetEl, text) {
    if (!navigator.clipboard) return;

    navigator.clipboard.writeText(text).then(function () {
      var tooltip = document.createElement('div');
      tooltip.className = 'saas-copy-tooltip';
      tooltip.textContent = '✓ Copied';
      tooltip.style.cssText = [
        'position: absolute',
        'background: #10b981',
        'color: #ffffff',
        'font-family: var(--font-sans, sans-serif)',
        'font-size: 0.72rem',
        'font-weight: 700',
        'padding: 3px 8px',
        'border-radius: 6px',
        'box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4)',
        'z-index: 9999',
        'pointer-events: none',
        'transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
        'opacity: 0',
        'transform: translateY(4px)'
      ].join(';');

      document.body.appendChild(tooltip);

      var rect = targetEl.getBoundingClientRect();
      tooltip.style.left = (rect.left + rect.width / 2 - tooltip.offsetWidth / 2) + 'px';
      tooltip.style.top = (rect.top - 28) + 'px';

      requestAnimationFrame(function () {
        tooltip.style.opacity = '1';
        tooltip.style.transform = 'translateY(0)';
      });

      setTimeout(function () {
        tooltip.style.opacity = '0';
        tooltip.style.transform = 'translateY(-4px)';
        setTimeout(function () {
          if (tooltip.parentNode) tooltip.parentNode.removeChild(tooltip);
        }, 200);
      }, 1500);
    });
  }

  // 2. Attach Copy Listeners to Phone Links and ID Chips
  function initCopyableElements() {
    document.querySelectorAll('a[href^="tel:"]').forEach(function (link) {
      if (link.dataset.copyBound) return;
      link.dataset.copyBound = 'true';

      // Create little copy icon alongside phone if not already present
      var copyBtn = document.createElement('button');
      copyBtn.type = 'button';
      copyBtn.className = 'btn-copy-chip';
      copyBtn.title = 'Copy phone number';
      copyBtn.innerHTML = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>';
      copyBtn.style.cssText = 'border:none; background:transparent; cursor:pointer; padding:0 2px; color:var(--saas-text-muted); vertical-align:middle;';

      copyBtn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var phone = link.textContent.trim().replace(/[^0-9+]/g, '');
        showCopyFeedback(copyBtn, phone);
      });

      if (link.nextSibling) {
        link.parentNode.insertBefore(copyBtn, link.nextSibling);
      } else {
        link.parentNode.appendChild(copyBtn);
      }
    });

    // Copy on Lead IDs
    document.querySelectorAll('.lead-id, [data-copy-id]').forEach(function (el) {
      if (el.dataset.copyBound) return;
      el.dataset.copyBound = 'true';
      el.style.cursor = 'pointer';
      el.title = 'Click to copy ID';
      el.addEventListener('click', function (e) {
        e.stopPropagation();
        var text = el.textContent.trim().replace('#', '');
        showCopyFeedback(el, text);
      });
    });
  }

  // 3. Interactive Multi-Select Table Row Highlighting
  function initTableMultiSelect() {
    var checkboxes = document.querySelectorAll('.lead-row-select');
    checkboxes.forEach(function (cb) {
      cb.addEventListener('change', function () {
        var tr = cb.closest('tr');
        if (!tr) return;
        if (cb.checked) {
          tr.style.backgroundColor = 'rgba(14, 165, 233, 0.08)';
          tr.style.borderLeft = '3px solid var(--saas-cyan)';
        } else {
          tr.style.backgroundColor = '';
          tr.style.borderLeft = '';
        }
      });
    });
  }

  // 4. Global Keyboard Shortcuts Handler
  function initGlobalKeybindings() {
    window.addEventListener('keydown', function (e) {
      // Ctrl+K / Cmd+K -> Trigger Command Palette
      if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        var triggerBtn = document.getElementById('tp-search-trigger-btn');
        if (triggerBtn) triggerBtn.click();
      }

      // Escape -> Close any open modal or command palette
      if (e.key === 'Escape') {
        var palette = document.getElementById('tp-command-palette');
        if (palette && palette.classList.contains('is-open')) {
          var closeBtn = document.getElementById('tp-palette-close-btn');
          if (closeBtn) closeBtn.click();
        }
      }
    });
  }

  // Initialize once DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initCopyableElements();
      initTableMultiSelect();
      initGlobalKeybindings();
    });
  } else {
    initCopyableElements();
    initTableMultiSelect();
    initGlobalKeybindings();
  }

  // Re-run for dynamically loaded tables or AJAX updates
  window.saasRefreshElements = function () {
    initCopyableElements();
    initTableMultiSelect();
  };
})();
