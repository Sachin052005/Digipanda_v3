/**
 * Dashboard Main Orchestrator
 * Renders KPIs, channel cards, branch table with 9 highlighted and 3 normal columns,
 * and live-syncs Google Sheets tabs with partial-failure resilience.
 */

const App = (() => {
  let isSyncing = false;
  let syncError = null;
  let lastBranchData = null;

  const setText = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  const esc = (s) => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmt = (v) => (v === null || v === undefined ? '—' : Number(v).toLocaleString());

  // Visual classes for the 9 highlighted columns and 3 normal status columns
  const CHANNEL_CLASS = {
    'Meta WhatsApp': ['th-whatsapp', 'td-whatsapp', 'fa-brands fa-whatsapp'],
    'Meta Lead Form': ['th-meta-form', 'td-meta-form', 'fa-brands fa-meta'],
    'Website (Google Ad)': ['th-google-ad', 'td-ad', 'fa-brands fa-google'],
    'Website (Google SEO)': ['th-google-seo', 'td-seo', 'fa-solid fa-magnifying-glass'],
    'Instagram': ['th-instagram', 'td-ig', 'fa-brands fa-instagram'],
    'Google Calls': ['th-google-call', 'td-call', 'fa-solid fa-phone-volume'],
    'Influencer': ['th-influencer', 'td-influencer', 'fa-solid fa-bullhorn'],
  };

  const updateKPIs = async (filters) => {
    const d = await Api.fetchKPIs(filters);
    setText('kpiTotalLeads', fmt(d.total_leads));
    const ch = d.total_change_pct;
    const badge = document.getElementById('kpiTotalPct');
    if (badge) {
      badge.textContent = ch === null ? '—' : `${ch >= 0 ? '↑ +' : '↓ '}${ch}%`;
      badge.classList.toggle('is-negative', ch !== null && ch < 0);
    }
    const days = filters.start_date && filters.end_date
      ? Math.round((new Date(filters.end_date) - new Date(filters.start_date)) / 86400000) + 1 : 0;
    setText('kpiTotalPctLabel', !days ? 'all time' : days === 1 ? 'vs previous day' : `vs previous ${days} days`);

    d.kpis.forEach((k, i) => {
      setText(`kpiTitle${i + 1}`, k.label);
      setText(`kpiVal${i + 1}`, fmt(k.value));
      setText(`kpiPct${i + 1}`, k.percentage === null ? '—' : `${k.percentage}%`);
    });
  };

  const updateChannels = async (filters) => {
    const res = await Api.fetchChannels(filters);
    DashboardCharts.renderChannelDonut(res.channels, res.total);
    res.channels.forEach(c => {
      document.querySelectorAll(`[data-chan-count="${c.channel}"]`).forEach(el => { el.textContent = fmt(c.count); });
      document.querySelectorAll(`[data-chan-pct="${c.channel}"]`).forEach(el => { el.textContent = `${c.percentage}%`; });
    });
  };

  const rowCells = (r, channels, statusLabels) => `
    <td class="td-branch">${esc(r.branch)}</td>
    <td class="td-total">${fmt(r.total_leads)}</td>
    ${channels.map((c, i) => `<td class="${CHANNEL_CLASS[c]?.[1] || 'td-other'}">${fmt(r.channels[i] || 0)}</td>`).join('')}
    ${(r.statuses || []).map(v => `<td class="td-status-normal">${fmt(v)}</td>`).join('')}`;

  const updateBranches = async (filters) => {
    const res = await Api.fetchBranches(filters);
    lastBranchData = res;
    DashboardCharts.renderBranchStacked(res.data, res.channels);

    const head = document.getElementById('branchTableHead');
    if (head) {
      head.innerHTML = `<tr>
        <th class="th-branch">Branch</th>
        <th class="th-total">Total Leads</th>
        ${res.channels.map(c => {
          const [th, , icon] = CHANNEL_CLASS[c] || ['th-other', '', 'fa-solid fa-ellipsis'];
          return `<th class="${th}"><div class="th-header-inner"><i class="${icon}"></i><span>${esc(c)}</span></div></th>`;
        }).join('')}
        ${res.statusLabels.map(l => `<th class="th-status-normal">${esc(l)}</th>`).join('')}
      </tr>`;
    }

    const cols = 2 + res.channels.length + res.statusLabels.length;
    const body = document.getElementById('branchTableBody');
    if (body) {
      body.innerHTML = res.data.length
        ? res.data.map(r => `<tr>${rowCells(r, res.channels, res.statusLabels)}</tr>`).join('')
        : `<tr><td class="td-empty" colspan="${cols}">No leads for the selected filters</td></tr>`;
    }

    const tfoot = document.getElementById('branchTableFooter');
    if (tfoot) tfoot.innerHTML = rowCells(res.totals, res.channels, res.statusLabels);
  };

  const updateOutcomes = async (filters) => {
    DashboardCharts.renderOutcomes(await Api.fetchOutcomes(filters));
  };

  const updateTitles = () => {
    const p = DashboardFilters.getPeriodLabel();
    document.querySelectorAll('[data-period]').forEach(el => { el.textContent = `(${p})`; });
  };

  const sheetConfigured = () => LeadStore.sheetUrls().length > 0;

  const updateSyncStatus = () => {
    const s = LeadStore.lastSync();
    const el = document.getElementById('lastSyncText');
    if (!el) return;
    const line = el.parentElement;
    line.classList.toggle('is-error', !!syncError);
    line.classList.toggle('is-live', !syncError && !!s && s.source === 'Google Sheet');
    if (!sheetConfigured() && !s) { el.textContent = 'No Google Sheet linked in js/config.js'; return; }
    if (syncError) { el.textContent = `Can't read Google Sheets: ${syncError}`; return; }
    if (!s) { el.textContent = 'Loading live data from Google Sheets…'; return; }
    const t = new Date(s.completed_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const what = `${s.total_leads.toLocaleString()} leads over ${s.days} day${s.days === 1 ? '' : 's'}`;
    const warnTxt = s.warning ? ` (⚠️ ${s.warning})` : '';
    el.textContent = s.source === 'Google Sheet' ? `Live · Google Sheet · ${what} · checked ${t}${warnTxt}` : `${s.source} · ${what} · loaded ${t}${warnTxt}`;
  };

  const refreshAll = async () => {
    const filters = DashboardFilters.getFilterValues();
    updateTitles();
    try {
      await Promise.all([updateKPIs(filters), updateChannels(filters), updateBranches(filters), updateOutcomes(filters)]);
    } catch (err) {
      console.error('Error during dashboard refresh:', err);
    }
    updateSyncStatus();
  };

  const afterDataChange = async () => {
    DashboardFilters.refreshDates();
    await DashboardFilters.populateDropdowns();
    await refreshAll();
  };

  const toast = (msg, isError = false) => {
    const el = document.getElementById('toast');
    if (!el) return;
    el.textContent = msg;
    el.className = `toast show${isError ? ' error' : ''}`;
    clearTimeout(el._t);
    el._t = setTimeout(() => { el.className = 'toast'; }, isError ? 7000 : 3500);
  };

  const triggerSync = async (silent = false) => {
    if (isSyncing || !sheetConfigured()) return;
    isSyncing = true;
    const btn = document.getElementById('btnRefreshSync');
    const icon = document.getElementById('syncIcon');
    if (!silent) { icon?.classList.add('spin'); if (btn) btn.disabled = true; }
    try {
      const log = await Api.triggerSync();
      const hadError = !!syncError;
      syncError = null;
      if (log.changed) await afterDataChange();
      else updateSyncStatus();
      if (!silent) {
        if (log.warning) toast(`Loaded ${log.total_leads} leads with warnings: ${log.warning}`, true);
        else toast(log.changed ? `Loaded ${log.total_leads} leads from Google Sheets` : 'Already up to date');
      } else if (hadError) {
        toast('Connection to Google Sheets restored');
      }
    } catch (err) {
      const first = !syncError;
      syncError = err.message || 'network error';
      updateSyncStatus();
      if (!silent || first) toast(`Sync error: ${syncError}`, true);
    } finally {
      icon?.classList.remove('spin');
      if (btn) btn.disabled = false;
      isSyncing = false;
    }
  };

  const importFile = (file) => {
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const log = LeadStore.importCSVText(String(reader.result), file.name);
        await afterDataChange();
        toast(`Imported ${log.total_leads} leads from ${file.name}`);
      } catch (err) {
        toast(`Import error: ${err.message}`, true);
      }
    };
    reader.readAsText(file);
  };

  const exportBranchCSV = () => {
    const d = lastBranchData;
    if (!d) return;
    const head = ['Branch', 'Total Leads', ...d.channels, ...d.statusLabels];
    const row = (r) => [r.branch, r.total_leads, ...r.channels, ...r.statuses.map(v => (v === null ? '' : v))];
    const q = (v) => `"${String(v).replace(/"/g, '""')}"`;
    const lines = [head, ...d.data.map(row), row(d.totals)].map(r => r.map(q).join(','));
    const blob = new Blob([lines.join('\r\n')], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `branch-summary-${DashboardFilters.getPeriodLabel().replace(/\W+/g, '-').toLowerCase()}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };

  const init = async () => {
    LeadStore.init();
    const cfg = window.DASHBOARD_CONFIG || {};

    PillDropdowns.init();
    DashboardFilters.initListeners(() => refreshAll());
    await DashboardFilters.populateDropdowns();

    const syncBtn = document.getElementById('btnRefreshSync');
    syncBtn?.addEventListener('click', () => triggerSync(false));
    if (syncBtn && !sheetConfigured()) syncBtn.hidden = true;

    const fileInput = document.getElementById('csvFileInput');
    document.getElementById('btnImportCsv')?.addEventListener('click', () => fileInput?.click());
    fileInput?.addEventListener('change', () => { if (fileInput.files[0]) importFile(fileInput.files[0]); fileInput.value = ''; });
    document.getElementById('btnExportCsv')?.addEventListener('click', exportBranchCSV);

    // Wire user display & logout
    const currentUser = sessionStorage.getItem('crm_auth_user') || localStorage.getItem('crm_auth_user') || 'Techpanda';
    const userLabel = document.getElementById('headerUserName');
    if (userLabel) userLabel.textContent = currentUser;

    const logoutBtn = document.getElementById('btnLogout');
    logoutBtn?.addEventListener('click', () => {
      sessionStorage.removeItem('crm_auth_user');
      localStorage.removeItem('crm_auth_user');
      window.location.replace('login.html');
    });

    await refreshAll();

    if (sheetConfigured()) {
      await triggerSync(true);
      const every = Math.max(10, Number(cfg.REFRESH_INTERVAL) || 300) * 1000;
      setInterval(() => { if (document.visibilityState === 'visible') triggerSync(true); }, every);
      document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') triggerSync(true); });
    }
  };

  return { init, refreshAll, triggerSync };
})();

document.addEventListener('DOMContentLoaded', () => App.init());
