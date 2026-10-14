/**
 * Filters Management Module
 * Date / Branch / Channel pills. Dates are now relative to a reference date
 * (see DASHBOARD_CONFIG.REFERENCE_DATE) instead of being hard-coded.
 */

const DashboardFilters = (() => {
  let refDate = new Date();
  let currentDateFilter = { start_date: '', end_date: '' };
  let currentPeriodLabel = 'Today';

  const toISODate = (d) => LeadStore.toISO(d); // local date, avoids the UTC off-by-one
  const fromISO = (s) => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); };
  const formatDateDisplay = (d) => d.toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' });
  const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };

  const resolveReferenceDate = () => {
    const cfg = window.DASHBOARD_CONFIG?.REFERENCE_DATE;
    if (cfg && cfg !== 'system' && /^\d{4}-\d{2}-\d{2}$/.test(cfg)) return fromISO(cfg);
    if (cfg === 'system') return new Date();
    const latest = Api.latestLeadDate();
    return latest ? fromISO(latest) : new Date();
  };

  const isRealToday = () => toISODate(refDate) === toISODate(new Date());

  const getFilterValues = () => ({
    start_date: currentDateFilter.start_date,
    end_date: currentDateFilter.end_date,
    branch: document.getElementById('branchFilter')?.value || '',
    channel: document.getElementById('channelFilter')?.value || '',
  });

  const getPeriodLabel = () => currentPeriodLabel;

  const syncPillsText = () => {
    [['branchFilter', 'branchPillText', 'All Branches'], ['channelFilter', 'channelPillText', 'All Channels']].forEach(([s, t, def]) => {
      const sel = document.getElementById(s), txt = document.getElementById(t);
      if (sel && txt) txt.textContent = sel.options[sel.selectedIndex]?.textContent || def;
    });
  };

  const fillSelect = (select, values, allLabel) => {
    if (!select) return;
    const current = select.value;
    select.innerHTML = `<option value="">${allLabel}</option>`;
    values.forEach(v => {
      const opt = document.createElement('option');
      opt.value = v; opt.textContent = v;
      if (v === current) opt.selected = true;
      select.appendChild(opt);
    });
  };

  const populateDropdowns = async () => {
    const data = await Api.fetchFilters();
    fillSelect(document.getElementById('branchFilter'), data.branches, 'All Branches');
    fillSelect(document.getElementById('channelFilter'), data.channels, 'All Channels');
    syncPillsText();
  };

  /** Rebuild the date <select> labels around the reference date */
  const buildDateOptions = () => {
    refDate = resolveReferenceDate();
    const sel = document.getElementById('dateFilter');
    const picker = document.getElementById('customDatePicker');
    if (!sel) return;
    const current = sel.value || 'today';
    const todayWord = isRealToday() ? 'Today' : 'Latest Day';
    const yWord = isRealToday() ? 'Yesterday' : 'Day Before';
    sel.innerHTML = `
      <option value="today">${todayWord} (${formatDateDisplay(refDate)})</option>
      <option value="yesterday">${yWord} (${formatDateDisplay(addDays(refDate, -1))})</option>
      <option value="last7days">Last 7 Days</option>
      <option value="last30days">Last 30 Days</option>
      <option value="all">All Dates</option>
      <option value="pick_date">Select Custom Date...</option>`;
    sel.value = current.startsWith('date:') || !sel.querySelector(`option[value="${current}"]`) ? 'today' : current;
    if (picker) picker.value = toISODate(refDate);
  };

  let setDateSelection = () => {};

  const initListeners = (onChangeCallback) => {
    const dateSelect = document.getElementById('dateFilter');
    const dateLabel = document.getElementById('datePillLabel');
    const dateVal = document.getElementById('datePillVal');
    const customDatePicker = document.getElementById('customDatePicker');

    const triggerChange = () => {
      syncPillsText();
      if (typeof onChangeCallback === 'function') onChangeCallback(getFilterValues());
    };

    document.getElementById('branchFilter')?.addEventListener('change', triggerChange);
    document.getElementById('channelFilter')?.addEventListener('change', triggerChange);

    setDateSelection = (val, trigger = true) => {
      const refISO = toISODate(refDate);
      const set = (start, end, label, display, period) => {
        currentDateFilter = { start_date: start, end_date: end };
        currentPeriodLabel = period;
        if (dateLabel) dateLabel.textContent = label;
        if (dateVal) dateVal.textContent = display;
      };
      const todayWord = isRealToday() ? 'Today' : 'Latest Day';
      if (val === 'today') {
        set(refISO, refISO, todayWord, formatDateDisplay(refDate), todayWord);
      } else if (val === 'yesterday') {
        const y = addDays(refDate, -1);
        const w = isRealToday() ? 'Yesterday' : 'Day Before';
        set(toISODate(y), toISODate(y), w, formatDateDisplay(y), w);
      } else if (val === 'last7days' || val === 'last30days') {
        const n = val === 'last7days' ? 7 : 30;
        const s = addDays(refDate, -(n - 1));
        set(toISODate(s), refISO, `Last ${n} Days`, `${formatDateDisplay(s)} - ${formatDateDisplay(refDate)}`, `Last ${n} Days`);
      } else if (val === 'all') {
        set('', '', 'All Dates', 'All Available Leads', 'All Dates');
      } else if (val.startsWith('date:')) {
        const dStr = val.slice(5);
        set(dStr, dStr, 'Custom', formatDateDisplay(fromISO(dStr)), formatDateDisplay(fromISO(dStr)));
      }
      if (trigger) triggerChange();
    };

    dateSelect?.addEventListener('change', () => {
      const val = dateSelect.value;
      if (val === 'pick_date') {
        try { customDatePicker.showPicker(); } catch (err) { customDatePicker?.focus(); }
        return;
      }
      setDateSelection(val, true);
    });

    customDatePicker?.addEventListener('change', () => {
      const picked = customDatePicker.value;
      if (!picked) return;
      let opt = dateSelect.querySelector(`option[value="date:${picked}"]`);
      if (!opt) {
        opt = document.createElement('option');
        opt.value = `date:${picked}`;
        opt.textContent = formatDateDisplay(fromISO(picked));
        dateSelect.insertBefore(opt, dateSelect.querySelector('option[value="pick_date"]'));
      }
      dateSelect.value = `date:${picked}`;
      setDateSelection(`date:${picked}`, true);
    });

    buildDateOptions();
    setDateSelection(dateSelect?.value || 'today', false);
    syncPillsText();
  };

  /** Called after new data arrives: reference date may have moved */
  const refreshDates = () => {
    buildDateOptions();
    setDateSelection(document.getElementById('dateFilter')?.value || 'today', false);
  };

  return { getFilterValues, getPeriodLabel, populateDropdowns, initListeners, syncPillsText, refreshDates };
})();
