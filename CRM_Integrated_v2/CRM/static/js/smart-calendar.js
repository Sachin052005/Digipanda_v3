/**
 * DigiPanda CRM — Smart Calendar Popover Component (Enhanced)
 * Provides an enterprise-grade dual-month calendar range picker with quick presets,
 * manual direct-typing inputs, real-time hover previews (DOM-retained),
 * 2D viewport collision auto-flipping, full keyboard accessibility,
 * and reliable form submission across all CRM dashboards and listing tables.
 */
(function () {
  'use strict';

  // Helper: Format date as YYYY-MM-DD in local time
  function formatYMD(d) {
    if (!d || isNaN(d.getTime())) return '';
    var year = d.getFullYear();
    var month = String(d.getMonth() + 1).padStart(2, '0');
    var day = String(d.getDate()).padStart(2, '0');
    return year + '-' + month + '-' + day;
  }

  // Helper: Format date for human display (e.g. "Oct 24, 2026")
  function formatHumanDate(d) {
    if (!d || isNaN(d.getTime())) return '';
    var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return months[d.getMonth()] + ' ' + d.getDate() + ', ' + d.getFullYear();
  }

  // Helper: Parse YYYY-MM-DD string into local Date object
  function parseYMD(str) {
    if (!str || typeof str !== 'string') return null;
    var parts = str.trim().split('-');
    if (parts.length !== 3) return null;
    var y = parseInt(parts[0], 10);
    var m = parseInt(parts[1], 10) - 1;
    var d = parseInt(parts[2], 10);
    var dt = new Date(y, m, d);
    return isNaN(dt.getTime()) ? null : dt;
  }

  // Calculate day difference (inclusive)
  function calcDurationDays(start, end) {
    if (!start || !end) return 0;
    var msPerDay = 24 * 60 * 60 * 1000;
    var s = new Date(start.getFullYear(), start.getMonth(), start.getDate());
    var e = new Date(end.getFullYear(), end.getMonth(), end.getDate());
    var diffMs = Math.abs(e.getTime() - s.getTime());
    return Math.round(diffMs / msPerDay) + 1;
  }

  // Presets definition
  function getPresets() {
    var today = new Date();
    today.setHours(0, 0, 0, 0);

    var yesterday = new Date(today);
    yesterday.setDate(today.getDate() - 1);

    var last7 = new Date(today);
    last7.setDate(today.getDate() - 6);

    var last30 = new Date(today);
    last30.setDate(today.getDate() - 29);

    var thisMonthStart = new Date(today.getFullYear(), today.getMonth(), 1);

    var lastMonthStart = new Date(today.getFullYear(), today.getMonth() - 1, 1);
    var lastMonthEnd = new Date(today.getFullYear(), today.getMonth(), 0);

    return [
      { id: 'today', label: 'Today', start: today, end: today },
      { id: 'yesterday', label: 'Yesterday', start: yesterday, end: yesterday },
      { id: 'last_7_days', label: 'Last 7 Days', start: last7, end: today },
      { id: 'last_30_days', label: 'Last 30 Days', start: last30, end: today },
      { id: 'this_month', label: 'This Month', start: thisMonthStart, end: today },
      { id: 'last_month', label: 'Last Month', start: lastMonthStart, end: lastMonthEnd },
      { id: 'custom', label: 'Custom Range', start: null, end: null }
    ];
  }

  // Core Smart Calendar instance creator
  function createSmartCalendar(container) {
    if (container._smartCalendarInitialized) return;
    container._smartCalendarInitialized = true;

    // 1. Identify input fields
    var startInput = container.querySelector('[data-smart-start], input[name="start_date"], input[name="from_date"], input[name="date_from"]');
    var endInput = container.querySelector('[data-smart-end], input[name="end_date"], input[name="to_date"], input[name="date_to"]');
    var periodInput = container.querySelector('input[name="period"]');

    if (!startInput || !endInput) return;

    var form = container.closest('form');

    // Hide native inputs visually but keep them form-accessible
    [startInput, endInput].forEach(function (inp) {
      inp.style.display = 'none';
    });

    // 2. State management
    var committedStart = parseYMD(startInput.value);
    var committedEnd = parseYMD(endInput.value);
    var pendingStart = committedStart ? new Date(committedStart) : null;
    var pendingEnd = committedEnd ? new Date(committedEnd) : null;
    var activePresetId = 'custom';

    // Check if initial dates match any known preset
    if (committedStart && committedEnd) {
      var sYMD = formatYMD(committedStart);
      var eYMD = formatYMD(committedEnd);
      var presets = getPresets();
      for (var i = 0; i < presets.length; i++) {
        var p = presets[i];
        if (p.start && p.end && formatYMD(p.start) === sYMD && formatYMD(p.end) === eYMD) {
          activePresetId = p.id;
          break;
        }
      }
    }

    // Base display month (left calendar). Defaults to start date or today
    var currentViewDate = pendingStart ? new Date(pendingStart) : new Date();
    currentViewDate.setDate(1);

    // 3. Create Trigger Button
    var trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'tp-smart-date-trigger';
    if (container.classList.contains('w-100')) {
      trigger.classList.add('w-100');
    }
    if (container.classList.contains('compact')) {
      trigger.classList.add('compact');
    }
    trigger.setAttribute('aria-haspopup', 'dialog');
    trigger.setAttribute('aria-expanded', 'false');

    var calIconSvg = '<svg class="tp-smart-date-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>';
    var chevronSvg = '<svg class="tp-smart-date-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"></polyline></svg>';

    var labelSpan = document.createElement('span');
    labelSpan.className = 'tp-smart-date-label';

    var dotSpan = document.createElement('span');
    dotSpan.className = 'tp-smart-date-dot';

    var resetBtn = document.createElement('button');
    resetBtn.type = 'button';
    resetBtn.className = 'tp-smart-date-quick-reset';
    resetBtn.title = 'Clear date filter';
    resetBtn.innerHTML = '&times;';
    resetBtn.style.display = 'none';

    var leftWrap = document.createElement('div');
    leftWrap.style.display = 'inline-flex';
    leftWrap.style.alignItems = 'center';
    leftWrap.style.gap = '8px';
    leftWrap.style.overflow = 'hidden';
    leftWrap.innerHTML = calIconSvg;
    leftWrap.appendChild(labelSpan);
    leftWrap.appendChild(dotSpan);

    var rightWrap = document.createElement('div');
    rightWrap.style.display = 'inline-flex';
    rightWrap.style.alignItems = 'center';
    rightWrap.style.gap = '4px';
    rightWrap.appendChild(resetBtn);
    rightWrap.insertAdjacentHTML('beforeend', chevronSvg);

    trigger.appendChild(leftWrap);
    trigger.appendChild(rightWrap);
    container.appendChild(trigger);

    // 4. Create Popover DOM
    var popover = document.createElement('div');
    popover.className = 'tp-smart-date-popover';
    popover.setAttribute('role', 'dialog');
    popover.setAttribute('aria-modal', 'true');
    popover.style.display = 'none';

    popover.innerHTML = [
      '<div class="tp-smart-date-body">',
      '  <!-- Left Sidebar: Presets -->',
      '  <div class="tp-smart-date-presets" role="menu"></div>',
      '  <!-- Right Main Area: Inputs & Dual Months -->',
      '  <div class="tp-smart-date-main">',
      '    <div class="tp-smart-date-header">',
      '      <div class="tp-smart-date-inputs">',
      '        <div class="tp-smart-date-box" id="startBox">',
      '          <span class="tp-box-label">START DATE</span>',
      '          <input type="text" class="tp-smart-date-input-field" id="startVal" placeholder="YYYY-MM-DD" maxlength="10" autocomplete="off">',
      '        </div>',
      '        <span class="tp-smart-date-arrow"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg></span>',
      '        <div class="tp-smart-date-box" id="endBox">',
      '          <span class="tp-box-label">END DATE</span>',
      '          <input type="text" class="tp-smart-date-input-field" id="endVal" placeholder="YYYY-MM-DD" maxlength="10" autocomplete="off">',
      '        </div>',
      '      </div>',
      '      <span class="tp-smart-date-duration" id="durationBadge">0 days</span>',
      '    </div>',
      '<div class="tp-smart-date-single-view">',
      '  <div class="tp-smart-month" id="singleMonth"></div>',
      '</div>',
      '  </div>',
      '</div>',
      '<div class="tp-smart-date-footer">',
      '  <div class="tp-smart-date-summary" id="rangeSummary">Select date range</div>',
      '  <div class="tp-smart-date-actions">',
      '    <button type="button" class="btn btn-sm tp-smart-btn-clear" id="smartClearBtn">Clear</button>',
      '    <button type="button" class="btn btn-sm tp-smart-btn-cancel" id="smartCancelBtn">Cancel</button>',
      '    <button type="button" class="btn btn-sm tp-smart-btn-apply" id="smartApplyBtn">Apply Range</button>',
      '  </div>',
      '</div>'
    ].join('');

    container.appendChild(popover);

    // References to inner elements
    var presetsContainer = popover.querySelector('.tp-smart-date-presets');
    var monthEl = popover.querySelector('#singleMonth');
    var startValInput = popover.querySelector('#startVal');
    var endValInput = popover.querySelector('#endVal');
    var durationBadge = popover.querySelector('#durationBadge');
    var rangeSummary = popover.querySelector('#rangeSummary');
    var clearBtn = popover.querySelector('#smartClearBtn');
    var cancelBtn = popover.querySelector('#smartCancelBtn');
    var applyBtn = popover.querySelector('#smartApplyBtn');

    // 5. Update Trigger Text & Visual State
    function updateTriggerState() {
      if (committedStart && committedEnd) {
        labelSpan.textContent = formatHumanDate(committedStart) + ' \u2013 ' + formatHumanDate(committedEnd);
        trigger.classList.add('has-filter');
        resetBtn.style.display = 'inline-flex';
        dotSpan.style.display = 'block';
      } else if (committedStart) {
        labelSpan.textContent = formatHumanDate(committedStart);
        trigger.classList.add('has-filter');
        resetBtn.style.display = 'inline-flex';
        dotSpan.style.display = 'block';
      } else {
        labelSpan.textContent = 'Custom Date';
        trigger.classList.remove('has-filter');
        resetBtn.style.display = 'none';
        dotSpan.style.display = 'none';
      }
    }

    // 6. Render Presets Sidebar
    function renderPresets() {
      presetsContainer.innerHTML = '';
      var presets = getPresets();

      presets.forEach(function (preset) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'tp-smart-preset-btn';
        btn.textContent = preset.label;
        btn.setAttribute('data-preset', preset.id);

        if (preset.id === activePresetId) {
          btn.classList.add('is-active');
        }

        btn.addEventListener('click', function (e) {
          e.stopPropagation();
          activePresetId = preset.id;
          if (preset.start && preset.end) {
            pendingStart = new Date(preset.start);
            pendingEnd = new Date(preset.end);
            currentViewDate = new Date(pendingStart);
            currentViewDate.setDate(1);
          } else if (preset.id === 'custom') {
            // Focus Start Input for manual entry
            startValInput.focus();
            startValInput.select();
          }
          renderPresets();
          renderCalendarMonth();
          updateSelectionDisplays();
        });

        presetsContainer.appendChild(btn);
      });
    }

    // 7. Update Displays (Start/End boxes, duration badge, footer summary)
    function updateSelectionDisplays() {
      startValInput.value = pendingStart ? formatYMD(pendingStart) : '';
      endValInput.value = pendingEnd ? formatYMD(pendingEnd) : '';

      if (pendingStart && pendingEnd) {
        var days = calcDurationDays(pendingStart, pendingEnd);
        durationBadge.textContent = days + (days === 1 ? ' day' : ' days');
        durationBadge.style.display = 'inline-block';
        rangeSummary.textContent = 'Selected: ' + formatHumanDate(pendingStart) + ' to ' + formatHumanDate(pendingEnd) + ' (' + days + ' days)';
        applyBtn.removeAttribute('disabled');
      } else if (pendingStart) {
        durationBadge.textContent = '1 day';
        durationBadge.style.display = 'inline-block';
        rangeSummary.textContent = 'Starting: ' + formatHumanDate(pendingStart) + ' (Pick end date or click Apply for single day)';
        applyBtn.removeAttribute('disabled');
      } else {
        durationBadge.style.display = 'none';
        rangeSummary.textContent = 'Select start and end dates';
      }
    }

    // Handle manual input in Start/End boxes
    function handleManualInput() {
      var s = parseYMD(startValInput.value);
      var e = parseYMD(endValInput.value);

      if (s) {
        pendingStart = s;
        currentViewDate = new Date(s);
        currentViewDate.setDate(1);
      }
      if (e) {
        pendingEnd = e;
      }
      activePresetId = 'custom';
      renderPresets();
      renderCalendarMonth();

      if (pendingStart && pendingEnd) {
        var days = calcDurationDays(pendingStart, pendingEnd);
        durationBadge.textContent = days + (days === 1 ? ' day' : ' days');
        durationBadge.style.display = 'inline-block';
        rangeSummary.textContent = 'Selected: ' + formatHumanDate(pendingStart) + ' to ' + formatHumanDate(pendingEnd) + ' (' + days + ' days)';
      }
    }

    startValInput.addEventListener('change', handleManualInput);
    endValInput.addEventListener('change', handleManualInput);
    startValInput.addEventListener('keydown', function(e) { if (e.key === 'Enter') handleManualInput(); });
    endValInput.addEventListener('keydown', function(e) { if (e.key === 'Enter') handleManualInput(); });

    // 8. Render a single calendar month with bidirectional navigation
    function renderMonth(containerEl, year, month) {
      containerEl.innerHTML = '';

      var monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
      var dayNames = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

      // Month Navigation Header (Both Prev & Next buttons for single month view)
      var header = document.createElement('div');
      header.className = 'tp-smart-month-header';

      var prevBtnHtml = '<button type="button" class="tp-month-nav-btn tp-nav-prev" title="Previous month"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15 18 9 12 15 6"></polyline></svg></button>';
      var nextBtnHtml = '<button type="button" class="tp-month-nav-btn tp-nav-next" title="Next month"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"></polyline></svg></button>';

      header.innerHTML = [
        prevBtnHtml,
        '<span class="tp-month-title">' + monthNames[month] + ' ' + year + '</span>',
        nextBtnHtml
      ].join('');

      containerEl.appendChild(header);

      // Month nav button clicks
      var prevBtn = header.querySelector('.tp-nav-prev');
      if (prevBtn) {
        prevBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          currentViewDate.setMonth(currentViewDate.getMonth() - 1);
          renderCalendarMonth();
        });
      }

      var nextBtn = header.querySelector('.tp-nav-next');
      if (nextBtn) {
        nextBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          currentViewDate.setMonth(currentViewDate.getMonth() + 1);
          renderCalendarMonth();
        });
      }

      // Weekday Row
      var weekdaysRow = document.createElement('div');
      weekdaysRow.className = 'tp-smart-weekdays';
      dayNames.forEach(function (dn) {
        var dEl = document.createElement('span');
        dEl.textContent = dn;
        weekdaysRow.appendChild(dEl);
      });
      containerEl.appendChild(weekdaysRow);

      // Days Grid
      var daysGrid = document.createElement('div');
      daysGrid.className = 'tp-smart-days-grid';

      var firstDayIndex = new Date(year, month, 1).getDay();
      var daysInMonth = new Date(year, month + 1, 0).getDate();
      var daysInPrevMonth = new Date(year, month, 0).getDate();

      var todayYMD = formatYMD(new Date());
      var startYMD = pendingStart ? formatYMD(pendingStart) : '';
      var endYMD = pendingEnd ? formatYMD(pendingEnd) : '';

      // Leading days (previous month)
      for (var p = firstDayIndex - 1; p >= 0; p--) {
        var prevDayNum = daysInPrevMonth - p;
        var prevDateObj = new Date(year, month - 1, prevDayNum);
        var prevYMD = formatYMD(prevDateObj);
        var cell = createDayCell(prevDayNum, prevYMD, true, todayYMD, startYMD, endYMD);
        daysGrid.appendChild(cell);
      }

      // Current month days
      for (var d = 1; d <= daysInMonth; d++) {
        var curDateObj = new Date(year, month, d);
        var curYMD = formatYMD(curDateObj);
        var curCell = createDayCell(d, curYMD, false, todayYMD, startYMD, endYMD);
        daysGrid.appendChild(curCell);
      }

      // Trailing days (next month) to fill 42 cells grid
      var totalCells = firstDayIndex + daysInMonth;
      var trailingDays = 42 - totalCells;
      if (trailingDays >= 7) trailingDays -= 7;

      for (var n = 1; n <= trailingDays; n++) {
        var nextDateObj = new Date(year, month + 1, n);
        var nextYMD = formatYMD(nextDateObj);
        var nextCell = createDayCell(n, nextYMD, true, todayYMD, startYMD, endYMD);
        daysGrid.appendChild(nextCell);
      }

      containerEl.appendChild(daysGrid);
    }

    // Helper: Create a single day cell in grid
    function createDayCell(dayNum, ymd, isOutside, todayYMD, startYMD, endYMD) {
      var cell = document.createElement('div');
      cell.className = 'tp-smart-day-cell';
      cell.setAttribute('data-ymd', ymd);

      if (isOutside) cell.classList.add('is-outside');
      if (ymd === todayYMD) cell.classList.add('is-today');

      var isStart = ymd === startYMD;
      var isEnd = ymd === endYMD;
      var isSingle = isStart && isEnd;

      if (isSingle) {
        cell.classList.add('is-single');
      } else if (isStart) {
        cell.classList.add('is-start');
      } else if (isEnd) {
        cell.classList.add('is-end');
      } else if (startYMD && endYMD && ymd > startYMD && ymd < endYMD) {
        cell.classList.add('is-in-range');
      }

      var numSpan = document.createElement('span');
      numSpan.className = 'tp-day-num';
      numSpan.textContent = dayNum;
      cell.appendChild(numSpan);

      // Click to select
      cell.addEventListener('click', function (e) {
        e.stopPropagation();
        var clickedDate = parseYMD(ymd);

        if (!pendingStart || (pendingStart && pendingEnd)) {
          // First click: reset and pick start
          pendingStart = clickedDate;
          pendingEnd = null;
          activePresetId = 'custom';
        } else if (pendingStart && !pendingEnd) {
          // Second click: pick end
          if (clickedDate < pendingStart) {
            pendingEnd = pendingStart;
            pendingStart = clickedDate;
          } else {
            pendingEnd = clickedDate;
          }
          activePresetId = 'custom';
        }

        renderPresets();
        renderCalendarMonth();
        updateSelectionDisplays();
      });

      // Surgical hover preview (Zero DOM thrashing)
      cell.addEventListener('mouseenter', function () {
        if (pendingStart && !pendingEnd) {
          var sYMD = formatYMD(pendingStart);
          var hYMD = ymd;
          var rangeStart = sYMD <= hYMD ? sYMD : hYMD;
          var rangeEnd = sYMD <= hYMD ? hYMD : sYMD;

          var allCells = popover.querySelectorAll('.tp-smart-day-cell');
          allCells.forEach(function (c) {
            var cYmd = c.getAttribute('data-ymd');
            if (cYmd === sYMD) {
              c.classList.add('is-start');
              c.classList.remove('is-in-range', 'is-end', 'is-single');
            } else if (cYmd === hYMD) {
              c.classList.add('is-end');
              c.classList.remove('is-in-range', 'is-single');
            } else if (cYmd > rangeStart && cYmd < rangeEnd) {
              c.classList.add('is-in-range');
              c.classList.remove('is-end', 'is-start');
            } else {
              c.classList.remove('is-in-range', 'is-end');
            }
          });
        }
      });

      return cell;
    }

    // 9. Render single calendar month
    function renderCalendarMonth() {
      var y = currentViewDate.getFullYear();
      var m = currentViewDate.getMonth();
      renderMonth(monthEl, y, m);
    }

    // 10. Positioning & 2D Collision Auto-Flip
    function positionPopover() {
      popover.style.display = 'block';
      popover.classList.remove('popover-up', 'popover-right');

      var rect = trigger.getBoundingClientRect();
      var popoverRect = popover.getBoundingClientRect();
      var viewportHeight = window.innerHeight || document.documentElement.clientHeight;
      var viewportWidth = window.innerWidth || document.documentElement.clientWidth;

      // Vertical flip
      var spaceBelow = viewportHeight - rect.bottom;
      var spaceAbove = rect.top;

      if (spaceBelow < popoverRect.height + 15 && spaceAbove > popoverRect.height + 15) {
        popover.classList.add('popover-up');
      }

      // Horizontal flip
      if (rect.left + popoverRect.width > viewportWidth - 20) {
        popover.classList.add('popover-right');
      }
    }

    // 11. Open / Close controllers
    function openPopover() {
      pendingStart = committedStart ? new Date(committedStart) : null;
      pendingEnd = committedEnd ? new Date(committedEnd) : null;

      currentViewDate = pendingStart ? new Date(pendingStart) : new Date();
      currentViewDate.setDate(1);

      renderPresets();
      renderCalendarMonth();
      updateSelectionDisplays();

      positionPopover();
      trigger.classList.add('is-open');
      trigger.setAttribute('aria-expanded', 'true');
    }

    function closePopover() {
      popover.style.display = 'none';
      popover.classList.remove('popover-up', 'popover-right');
      trigger.classList.remove('is-open');
      trigger.setAttribute('aria-expanded', 'false');
    }

    function togglePopover() {
      if (popover.style.display === 'none') {
        openPopover();
      } else {
        closePopover();
      }
    }

    // 12. Commit and Form Execution
    function applySelection() {
      // Single day fallback: if only start is selected, treat as 1-day range (start = end)
      if (pendingStart && !pendingEnd) {
        pendingEnd = new Date(pendingStart);
      }

      if (!pendingStart || !pendingEnd) {
        closePopover();
        return;
      }

      // Ensure start <= end
      var finalStart = pendingStart <= pendingEnd ? pendingStart : pendingEnd;
      var finalEnd = pendingStart <= pendingEnd ? pendingEnd : pendingStart;

      committedStart = finalStart;
      committedEnd = finalEnd;

      var startStr = formatYMD(committedStart);
      var endStr = formatYMD(committedEnd);

      // Write to underlying input elements
      startInput.value = startStr;
      endInput.value = endStr;

      if (periodInput) {
        periodInput.value = 'custom';
      }

      updateTriggerState();
      closePopover();

      // Dispatch change events
      startInput.dispatchEvent(new Event('change', { bubbles: true }));
      endInput.dispatchEvent(new Event('change', { bubbles: true }));

      // Unconditionally execute form submit / dashboard fetch
      if (form) {
        form._isSubmitting = false; // reset lock
        form.submit();
      } else if (window.CRMReportDashboard && typeof window.CRMReportDashboard.fetch === 'function') {
        window.CRMReportDashboard.fetch();
      }
    }

    function clearSelection() {
      committedStart = null;
      committedEnd = null;
      pendingStart = null;
      pendingEnd = null;
      activePresetId = 'custom';

      startInput.value = '';
      endInput.value = '';

      if (periodInput) {
        periodInput.value = 'all';
      }

      updateTriggerState();
      closePopover();

      startInput.dispatchEvent(new Event('change', { bubbles: true }));
      endInput.dispatchEvent(new Event('change', { bubbles: true }));

      if (form) {
        form._isSubmitting = false;
        form.submit();
      } else if (window.CRMReportDashboard && typeof window.CRMReportDashboard.fetch === 'function') {
        window.CRMReportDashboard.fetch();
      }
    }

    // Event Bindings
    trigger.addEventListener('click', function (e) {
      e.stopPropagation();
      togglePopover();
    });

    resetBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      clearSelection();
    });

    applyBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      applySelection();
    });

    cancelBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      closePopover();
    });

    clearBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      clearSelection();
    });

    // Close on outside click
    document.addEventListener('click', function (e) {
      if (!container.contains(e.target)) {
        closePopover();
      }
    });

    // Close on Escape key
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && popover.style.display !== 'none') {
        closePopover();
        trigger.focus();
      }
    });

    // Window resize reposition
    window.addEventListener('resize', function () {
      if (popover.style.display !== 'none') {
        positionPopover();
      }
    });

    // Initialize display state
    updateTriggerState();
  }

  // Global Auto-initialization
  function initAllSmartCalendars() {
    // 1. Explicit containers
    var containers = document.querySelectorAll('.tp-smart-date-container');
    containers.forEach(function (c) {
      createSmartCalendar(c);
    });

    // 2. Progressive enhancement for dashboard custom date wrappers
    var customWrappers = document.querySelectorAll('[data-smart-calendar="true"]');
    customWrappers.forEach(function (w) {
      w.classList.add('tp-smart-date-container');
      createSmartCalendar(w);
    });
  }

  window.initSmartCalendar = initAllSmartCalendars;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAllSmartCalendars);
  } else {
    initAllSmartCalendars();
  }
})();
