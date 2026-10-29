/**
 * TECHPANDA CRM - Auto-Apply Filters Without Apply Button
 * Automatically applies filter changes upon selection/input, debounces text search,
 * synchronizes dependent dropdowns (e.g. Branch -> Telecaller / Counselor),
 * preserves pagination & sorting context, and prevents duplicate submissions.
 */
(function () {
  'use strict';

  function initAutoFilter() {
    var filterForms = document.querySelectorAll('form.filter-form');
    if (!filterForms.length) return;

    filterForms.forEach(function (form) {
      if (form._autoFilterInitialized) return;
      form._autoFilterInitialized = true;

      // 1. Remove / hide any Apply/Filter submit buttons
      var submitButtons = form.querySelectorAll('button[type="submit"], input[type="submit"]');
      submitButtons.forEach(function (btn) {
        var text = (btn.textContent || btn.value || '').trim().toLowerCase();
        // Check for apply / filter buttons
        if (text.includes('apply') || text.includes('filter') || text === 'search' || text === 'update') {
          btn.style.display = 'none';
        } else {
          btn.style.display = 'none';
        }
      });

      // 2. Identify dependent dropdowns (e.g. Branch -> Telecaller / Counselor)
      var branchSelect = form.querySelector('select[name="branch"]');
      var telecallerSelect = form.querySelector('select[name="telecaller"], select[name="caller"]');
      var counselorSelect = form.querySelector('select[name="counselor"]');

      function cacheOptions(selectEl) {
        if (!selectEl || selectEl._cachedOptions) return;
        var options = [];
        selectEl.querySelectorAll('option').forEach(function (opt) {
          options.push({
            value: opt.value,
            text: opt.textContent,
            branch: opt.getAttribute('data-branch') || '',
            selected: opt.selected
          });
        });
        selectEl._cachedOptions = options;
      }

      cacheOptions(telecallerSelect);
      cacheOptions(counselorSelect);

      function filterDependentDropdown(parentBranchSelect, depSelect) {
        if (!parentBranchSelect || !depSelect || !depSelect._cachedOptions) return;
        var selectedBranch = (parentBranchSelect.value || '').trim();
        var currentValue = depSelect.value;
        var matchingFound = false;

        // Clear existing options
        depSelect.innerHTML = '';

        depSelect._cachedOptions.forEach(function (opt) {
          // If option is placeholder (empty value) or matches branch, or no branch filter active
          var isCompatible = !opt.value || !selectedBranch || !opt.branch || opt.branch === selectedBranch;
          if (isCompatible) {
            var newOption = document.createElement('option');
            newOption.value = opt.value;
            newOption.textContent = opt.text;
            if (opt.branch) newOption.setAttribute('data-branch', opt.branch);
            if (opt.value === currentValue) {
              newOption.selected = true;
              matchingFound = true;
            }
            depSelect.appendChild(newOption);
          }
        });

        // Reset if selected person doesn't belong to the new branch
        if (!matchingFound && currentValue !== '') {
          depSelect.value = '';
        }
      }

      // Initial sync on page load (if branch was already selected)
      if (branchSelect && branchSelect.value) {
        if (telecallerSelect) filterDependentDropdown(branchSelect, telecallerSelect);
        if (counselorSelect) filterDependentDropdown(branchSelect, counselorSelect);
      }

      // 3. Serialize form state to detect real changes & prevent duplicate submissions
      function serializeFormState() {
        var formData = new FormData(form);
        var entries = [];
        for (var pair of formData.entries()) {
          entries.push(encodeURIComponent(pair[0]) + '=' + encodeURIComponent(pair[1]));
        }
        return entries.sort().join('&');
      }

      var lastSubmittedState = serializeFormState();
      var debounceTimer = null;

      function submitForm(originInput) {
        if (form._isSubmitting) return;

        var currentState = serializeFormState();
        if (currentState === lastSubmittedState) return;

        form._isSubmitting = true;
        lastSubmittedState = currentState;

        // Save focus and cursor position if triggered by text input
        if (originInput && (originInput.type === 'text' || originInput.type === 'search')) {
          try {
            sessionStorage.setItem('tp_autofilter_focus', originInput.name);
            if (typeof originInput.selectionStart === 'number') {
              sessionStorage.setItem('tp_autofilter_cursor', originInput.selectionStart.toString());
            }
          } catch (e) {}
        }

        // Submit GET form directly without screen dimming flash
        form.submit();
      }

      // 4. Listeners for Select Dropdowns (Immediate execution)
      var selects = form.querySelectorAll('select');
      selects.forEach(function (sel) {
        sel.addEventListener('change', function () {
          if (sel === branchSelect) {
            if (telecallerSelect) filterDependentDropdown(branchSelect, telecallerSelect);
            if (counselorSelect) filterDependentDropdown(branchSelect, counselorSelect);
          }
          submitForm(sel);
        });
      });

      // 5. Listeners for Checkboxes & Radios (Immediate execution)
      var checkables = form.querySelectorAll('input[type="checkbox"], input[type="radio"]');
      checkables.forEach(function (chk) {
        chk.addEventListener('change', function () {
          submitForm(chk);
        });
      });

      // 6. Listeners for Date Pickers (Execute upon complete date selection)
      var dateInputs = form.querySelectorAll('input[type="date"], input[type="datetime-local"]');
      dateInputs.forEach(function (dateInp) {
        dateInp.addEventListener('change', function () {
          submitForm(dateInp);
        });
      });

      // 7. Listeners for Text Search Inputs (Debounced 350ms)
      var textInputs = form.querySelectorAll('input[type="text"], input[type="search"]');
      textInputs.forEach(function (txt) {
        txt.addEventListener('input', function () {
          clearTimeout(debounceTimer);
          debounceTimer = setTimeout(function () {
            submitForm(txt);
          }, 380);
        });

        txt.addEventListener('keydown', function (e) {
          if (e.key === 'Enter') {
            e.preventDefault();
            clearTimeout(debounceTimer);
            submitForm(txt);
          }
        });

        txt.addEventListener('blur', function () {
          clearTimeout(debounceTimer);
          submitForm(txt);
        });
      });

      // 8. Restore Focus & Cursor Position on Page Load
      try {
        var focusFieldName = sessionStorage.getItem('tp_autofilter_focus');
        if (focusFieldName) {
          sessionStorage.removeItem('tp_autofilter_focus');
          var targetInp = form.querySelector('[name="' + focusFieldName + '"]');
          if (targetInp) {
            targetInp.focus();
            var cursorPos = parseInt(sessionStorage.getItem('tp_autofilter_cursor') || '', 10);
            sessionStorage.removeItem('tp_autofilter_cursor');
            if (!isNaN(cursorPos) && targetInp.setSelectionRange) {
              targetInp.setSelectionRange(cursorPos, cursorPos);
            }
          }
        }
      } catch (e) {}
    });
  }

  // Initialize on DOMContentLoaded or immediately if already loaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAutoFilter);
  } else {
    initAutoFilter();
  }
})();
