/**
 * TECHPANDA CRM - Universal Modern Custom Dropdown & Action Menu Component
 * Enterprise progressive enhancement for <select> elements and .tp-dropdown menus.
 * Features:
 *  - 2D Collision Detection (Auto Flip Up/Down & Left/Right)
 *  - Instant Client-Side Search for High-Cardinality Lists (> 8 options)
 *  - Zero-Lag Surgical Selection (No DOM Thrashing or Re-render Loops)
 *  - Full Light & Dark Theme Parity with High-Contrast Tokens
 *  - W3C Combobox ARIA 1.2 & Keyboard Accessibility (Arrows, Enter, Esc)
 *  - HTML5 Form Validation Compatibility
 */
(function () {
  'use strict';

  function initCustomDropdowns() {
    var selectElements = document.querySelectorAll(
      'form.filter-form select, .filter-card select, .filter-conditions-list select, select.tp-custom-select, #admin-branch-select-form select'
    );

    selectElements.forEach(function (selectEl) {
      if (
        selectEl._cselectInitialized ||
        selectEl.classList.contains('lead-status-select-hidden') ||
        selectEl.classList.contains('tp-pill-select-overlay') ||
        selectEl.hasAttribute('multiple') ||
        selectEl.hasAttribute('data-no-custom') ||
        (selectEl.offsetWidth === 0 && selectEl.offsetHeight === 0 && !selectEl.closest('.filter-conditions-list'))
      ) {
        return;
      }
      selectEl._cselectInitialized = true;

      // 1. Wrapper Container
      var wrapper = document.createElement('div');
      wrapper.className = 'tp-cselect-wrapper';
      wrapper.style.position = 'relative';
      wrapper.style.display = 'block';
      wrapper.style.width = '100%';

      if (selectEl.style.width && selectEl.style.width !== '100%') {
        wrapper.style.width = selectEl.style.width;
      }

      // Hide native select visually without breaking HTML5 form validation focusability
      selectEl.setAttribute(
        'style',
        'position: absolute !important; top: 0 !important; left: 0 !important; width: 100% !important; height: 100% !important; opacity: 0 !important; pointer-events: none !important; z-index: -1 !important;'
      );
      selectEl.tabIndex = -1;

      // 2. Trigger Button
      var trigger = document.createElement('button');
      trigger.type = 'button';
      trigger.className = 'tp-cselect-trigger';
      trigger.setAttribute('aria-haspopup', 'listbox');
      trigger.setAttribute('aria-expanded', 'false');

      var valueSpan = document.createElement('span');
      valueSpan.className = 'tp-cselect-value';

      var chevronSpan = document.createElement('span');
      chevronSpan.className = 'tp-cselect-chevron';
      chevronSpan.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"></polyline></svg>';

      trigger.appendChild(valueSpan);
      trigger.appendChild(chevronSpan);

      // 3. Floating Menu
      var menu = document.createElement('div');
      menu.className = 'tp-cselect-menu';
      menu.setAttribute('role', 'listbox');
      menu.style.display = 'none';

      var searchWrap = null;
      var searchInput = null;
      var optionsListContainer = document.createElement('div');
      optionsListContainer.className = 'tp-cselect-options-list';
      menu.appendChild(optionsListContainer);

      var emptyMessage = document.createElement('div');
      emptyMessage.className = 'tp-cselect-empty';
      emptyMessage.textContent = 'No matching options';
      emptyMessage.style.display = 'none';
      menu.appendChild(emptyMessage);

      // 4. Render Options List
      function renderOptions() {
        if (selectEl._suppressRender) return;

        optionsListContainer.innerHTML = '';
        var options = selectEl.querySelectorAll('option');
        var selectedIdx = selectEl.selectedIndex >= 0 ? selectEl.selectedIndex : 0;
        var selectedText = '';

        // Add search input if options count > 8
        if (options.length > 8) {
          if (!searchWrap) {
            searchWrap = document.createElement('div');
            searchWrap.className = 'tp-cselect-search-wrap';
            searchWrap.innerHTML = '<svg class="tp-cselect-search-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>';
            searchInput = document.createElement('input');
            searchInput.type = 'text';
            searchInput.className = 'tp-cselect-search-input';
            searchInput.placeholder = 'Search options...';
            searchInput.autocomplete = 'off';

            function filterOptions(q) {
              var query = (q || '').toLowerCase().trim();
              var items = optionsListContainer.querySelectorAll('.tp-cselect-option');
              var visibleCount = 0;
              items.forEach(function (it) {
                var txt = (it.getAttribute('data-text') || '').toLowerCase();
                if (!query || txt.includes(query)) {
                  it.style.display = 'flex';
                  visibleCount++;
                } else {
                  it.style.display = 'none';
                }
              });
              emptyMessage.style.display = visibleCount === 0 ? 'block' : 'none';
            }

            searchInput.addEventListener('input', function (e) {
              filterOptions(e.target.value);
            });

            // Prevent closing when clicking inside search input
            searchInput.addEventListener('click', function (e) {
              e.stopPropagation();
            });

            searchInput.addEventListener('keydown', function (e) {
              if (e.key === 'ArrowDown') {
                e.preventDefault();
                var firstVisible = optionsListContainer.querySelector('.tp-cselect-option:not([style*="display: none"])');
                if (firstVisible) {
                  firstVisible.classList.add('is-highlighted');
                  firstVisible.scrollIntoView({ block: 'nearest' });
                  trigger.focus();
                }
              } else if (e.key === 'Escape') {
                closeMenu();
              }
            });

            searchWrap.appendChild(searchInput);
            menu.insertBefore(searchWrap, optionsListContainer);
          }
          if (searchInput) searchInput.value = '';
        } else if (searchWrap && searchWrap.parentNode) {
          searchWrap.parentNode.removeChild(searchWrap);
          searchWrap = null;
          searchInput = null;
        }

        options.forEach(function (opt, idx) {
          var isSelected = (idx === selectedIdx) || (selectEl.value && opt.value === selectEl.value);
          if (isSelected && !selectedText) {
            selectedText = opt.textContent;
          }

          var item = document.createElement('div');
          item.className = 'tp-cselect-option' + (isSelected ? ' is-selected' : '');
          item.setAttribute('role', 'option');
          item.setAttribute('data-value', opt.value);
          item.setAttribute('data-index', idx);
          item.setAttribute('data-text', opt.textContent.trim());

          var itemText = document.createElement('span');
          itemText.className = 'tp-cselect-option-text';
          itemText.textContent = opt.textContent;

          var itemCheck = document.createElement('span');
          itemCheck.className = 'tp-cselect-check';
          itemCheck.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>';

          item.appendChild(itemText);
          item.appendChild(itemCheck);

          item.addEventListener('click', function (e) {
            e.stopPropagation();
            selectOption(opt.value, opt.textContent);
            closeMenu();
          });

          optionsListContainer.appendChild(item);
        });

        if (!selectedText && options.length > 0) {
          selectedText = options[0].textContent;
        }
        valueSpan.textContent = (selectedText || 'Select...').trim();
      }

      renderOptions();

      // 5. Zero-Lag Surgical Selection (No DOM Thrashing!)
      function selectOption(val, text) {
        var changed = (selectEl.value !== val);
        selectEl.value = val;

        if (text) {
          valueSpan.textContent = text.trim();
        }

        // Surgically toggle .is-selected classes on existing elements
        var items = optionsListContainer.querySelectorAll('.tp-cselect-option');
        items.forEach(function (it) {
          if (it.getAttribute('data-value') === val) {
            it.classList.add('is-selected');
          } else {
            it.classList.remove('is-selected');
          }
        });

        // Suppress redundant re-render loops during change propagation
        selectEl._suppressRender = true;
        try {
          var changeEvent = new Event('change', { bubbles: true });
          selectEl.dispatchEvent(changeEvent);

          var onchangeAttr = selectEl.getAttribute('onchange') || '';
          if (changed && selectEl.form && (onchangeAttr.includes('submit') || selectEl.name === 'branch_id')) {
            selectEl.form.submit();
          }
        } finally {
          selectEl._suppressRender = false;
        }
      }

      // 6. Viewport Positioning & 2D Auto-Flip (Up/Down + Left/Right)
      function positionMenu() {
        var rect = trigger.getBoundingClientRect();
        var menuHeight = 280;
        var menuWidth = Math.max(rect.width, 220);

        // Vertical collision: Flip up if space below < 260px and more room above
        var spaceBelow = window.innerHeight - rect.bottom;
        var spaceAbove = rect.top;
        if (spaceBelow < 260 && spaceAbove > spaceBelow) {
          menu.classList.add('drop-up');
        } else {
          menu.classList.remove('drop-up');
        }

        // Horizontal collision: Align right edge if overflowing viewport right
        var spaceRight = window.innerWidth - rect.left;
        if (spaceRight < menuWidth && rect.right > menuWidth) {
          menu.classList.add('drop-left');
        } else {
          menu.classList.remove('drop-left');
        }
      }

      function openMenu() {
        // Dismiss other open dropdowns
        dismissAllOpen(menu);

        positionMenu();

        menu.style.display = 'block';
        menu.classList.add('is-open');
        wrapper.classList.add('is-open');
        trigger.classList.add('is-open');
        trigger.setAttribute('aria-expanded', 'true');

        // Reset search field if present
        if (searchInput) {
          searchInput.value = '';
          var items = optionsListContainer.querySelectorAll('.tp-cselect-option');
          items.forEach(function (it) { it.style.display = 'flex'; });
          emptyMessage.style.display = 'none';
          setTimeout(function () { searchInput.focus(); }, 30);
        }

        // Scroll selected item into view
        var selectedItem = optionsListContainer.querySelector('.tp-cselect-option.is-selected');
        if (selectedItem) {
          selectedItem.scrollIntoView({ block: 'nearest' });
        }
      }

      function closeMenu() {
        menu.style.display = 'none';
        menu.classList.remove('is-open');
        wrapper.classList.remove('is-open');
        trigger.classList.remove('is-open');
        trigger.setAttribute('aria-expanded', 'false');
      }

      trigger.addEventListener('click', function (e) {
        e.stopPropagation();
        if (menu.classList.contains('is-open')) {
          closeMenu();
        } else {
          openMenu();
        }
      });

      // 7. Full Keyboard Navigation Contract
      trigger.addEventListener('keydown', function (e) {
        var isOpen = menu.classList.contains('is-open');
        var visibleItems = Array.from(optionsListContainer.querySelectorAll('.tp-cselect-option')).filter(function (it) {
          return it.style.display !== 'none';
        });

        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
          e.preventDefault();
          if (!isOpen) {
            openMenu();
            return;
          }
          if (visibleItems.length === 0) return;

          var currIdx = visibleItems.findIndex(function (it) {
            return it.classList.contains('is-highlighted') || it.classList.contains('is-selected');
          });

          var nextIdx = e.key === 'ArrowDown'
            ? (currIdx < visibleItems.length - 1 ? currIdx + 1 : 0)
            : (currIdx > 0 ? currIdx - 1 : visibleItems.length - 1);

          visibleItems.forEach(function (it, idx) {
            if (idx === nextIdx) {
              it.classList.add('is-highlighted');
              it.scrollIntoView({ block: 'nearest' });
            } else {
              it.classList.remove('is-highlighted');
            }
          });
        } else if (e.key === 'Enter' || e.key === ' ') {
          if (!isOpen) {
            e.preventDefault();
            openMenu();
          } else {
            var highlighted = optionsListContainer.querySelector('.tp-cselect-option.is-highlighted');
            if (highlighted) {
              e.preventDefault();
              selectOption(highlighted.getAttribute('data-value'), highlighted.getAttribute('data-text'));
              closeMenu();
            }
          }
        } else if (e.key === 'Escape' || e.key === 'Tab') {
          closeMenu();
        }
      });

      // 8. Mutation Observer for External Dynamic Updates (e.g., auto-filter.js)
      var observer = new MutationObserver(function () {
        if (!selectEl._suppressRender) {
          renderOptions();
        }
      });
      observer.observe(selectEl, { childList: true, subtree: true, attributes: true });

      // Programmatic change sync
      selectEl.addEventListener('change', function () {
        if (!selectEl._suppressRender) {
          var selectedOpt = selectEl.options[selectEl.selectedIndex];
          if (selectedOpt) {
            valueSpan.textContent = selectedOpt.textContent.trim();
          }
        }
      });

      // Insert wrapper into DOM
      selectEl.parentNode.insertBefore(wrapper, selectEl);
      wrapper.appendChild(selectEl);
      wrapper.appendChild(trigger);
      wrapper.appendChild(menu);
    });
  }

  // 9. Standardized Action Menus (.tp-dropdown)
  function initActionDropdowns() {
    document.querySelectorAll('.tp-dropdown').forEach(function (dd) {
      if (dd._tpDropdownInit) return;
      dd._tpDropdownInit = true;

      var trigger = dd.querySelector('.tp-dropdown-toggle, [id$="-actions-dropdown"], [id*="dropdown-trigger"]');
      var menu = dd.querySelector('.tp-dropdown-menu, [id$="ActionsDropdown"]');
      if (!trigger || !menu) return;

      trigger.addEventListener('click', function (e) {
        e.stopPropagation();
        var isOpen = menu.style.display === 'block';
        dismissAllOpen(menu);
        if (isOpen) {
          menu.style.display = 'none';
          trigger.setAttribute('aria-expanded', 'false');
        } else {
          // 2D Positioning Check
          var rect = trigger.getBoundingClientRect();
          var spaceRight = window.innerWidth - rect.left;
          if (spaceRight < 240) {
            menu.style.right = '0';
            menu.style.left = 'auto';
          } else {
            menu.style.left = '0';
            menu.style.right = 'auto';
          }
          menu.style.display = 'block';
          trigger.setAttribute('aria-expanded', 'true');
        }
      });
    });
  }

  function dismissAllOpen(exceptMenu) {
    // Dismiss custom selects
    document.querySelectorAll('.tp-cselect-menu.is-open').forEach(function (m) {
      if (m !== exceptMenu) {
        m.style.display = 'none';
        m.classList.remove('is-open');
        var w = m.closest('.tp-cselect-wrapper');
        if (w) w.classList.remove('is-open');
        var tr = w ? w.querySelector('.tp-cselect-trigger') : null;
        if (tr) {
          tr.classList.remove('is-open');
          tr.setAttribute('aria-expanded', 'false');
        }
      }
    });

    // Dismiss action dropdowns
    document.querySelectorAll('.tp-dropdown-menu, [id$="ActionsDropdown"]').forEach(function (m) {
      if (m !== exceptMenu) {
        m.style.display = 'none';
        var trigger = m.parentElement ? m.parentElement.querySelector('button') : null;
        if (trigger) trigger.setAttribute('aria-expanded', 'false');
      }
    });

    // Also close notifications popover if open
    var notifPanel = document.getElementById('notification-panel');
    if (notifPanel && notifPanel !== exceptMenu && notifPanel.style.display !== 'none') {
      notifPanel.style.display = 'none';
    }
  }

  // Global Click Outside
  document.addEventListener('click', function (e) {
    if (!e.target.closest('.tp-cselect-wrapper') && !e.target.closest('.tp-dropdown')) {
      dismissAllOpen();
    }
  });

  // Global Escape Key
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      dismissAllOpen();
    }
  });

  // Expose API
  window.initCustomDropdowns = function () {
    initCustomDropdowns();
    initActionDropdowns();
  };
  window.dismissAllCustomDropdowns = dismissAllOpen;

  // Initialize on load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', window.initCustomDropdowns);
  } else {
    window.initCustomDropdowns();
  }
})();
