/**
 * API Module (client-side)
 * Computes every dashboard number from LeadStore.
 * Serves unified KPIs, channel splits, branch summaries, and outcome metrics.
 */

const Api = (() => {
  const cfg = () => window.DASHBOARD_CONFIG || {};
  const pct = (n, total) => (total > 0 ? Math.round((n / total) * 100) : 0);
  const eq = (a, b) => String(a || '').toLowerCase() === String(b || '').toLowerCase();
  const norm = (s) => String(s || '').toLowerCase().replace(/\s+/g, ' ').trim();

  const inRange = (date, p) => (!p.start_date || date >= p.start_date) && (!p.end_date || date <= p.end_date);

  const filterRecs = (p = {}) => LeadStore.records().filter(r =>
    inRange(r.date, p) && (!p.branch || eq(r.branch, p.branch)) && (!p.channel || eq(r.channel, p.channel)));

  // Outcome columns are not split by channel, so they are unavailable when an individual channel is selected
  const filterMetrics = (p = {}) => (p.channel ? null : LeadStore.metrics().filter(m =>
    inRange(m.date, p) && (!p.branch || eq(m.branch, p.branch) || m.branch === 'All Branches')));

  const sum = (arr, f = 'count') => arr.reduce((s, x) => s + (x[f] || 0), 0);

  /** Map wanted metric names onto the sheet's actual column names */
  const resolveMetric = (wanted) => {
    const names = LeadStore.metricNames();
    const target = norm(wanted);
    return names.find(n => norm(n) === target) ||
           names.find(n => norm(n).includes(target)) ||
           null;
  };

  const kpiNames = () => (cfg().KPI_METRICS || ['Connected', 'Prospected', 'Call not connected'])
    .slice(0, 3).map(w => ({ wanted: w, name: resolveMetric(w) }));

  const statusColumns = () => (cfg().STATUS_COLUMNS || ['New Leads', 'Existing Leads', 'Missed Leads'])
    .slice(0, 3).map(w => ({ wanted: w, name: resolveMetric(w) }));

  const metricTotal = (mets, name) => (mets && name ? sum(mets.filter(m => m.name === name), 'value') : 0);

  const previousPeriodChange = (p, currentTotal) => {
    if (!p.start_date || !p.end_date) return null;
    const parse = (s) => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); };
    const start = parse(p.start_date), end = parse(p.end_date);
    const days = Math.round((end - start) / 86400000) + 1;
    const prevEnd = new Date(start); prevEnd.setDate(prevEnd.getDate() - 1);
    const prevStart = new Date(prevEnd); prevStart.setDate(prevStart.getDate() - (days - 1));
    const prev = sum(filterRecs({ ...p, start_date: LeadStore.toISO(prevStart), end_date: LeadStore.toISO(prevEnd) }));
    if (prev === 0) return null;
    return Math.round(((currentTotal - prev) / prev) * 100);
  };

  const fetchKPIs = (p) => {
    const total = sum(filterRecs(p));
    const mets = filterMetrics(p);
    return {
      total_leads: total,
      total_change_pct: previousPeriodChange(p, total),
      kpis: kpiNames().map(k => {
        const v = mets !== null && k.name ? metricTotal(mets, k.name) : null;
        return { label: k.wanted, value: v, percentage: v === null ? null : pct(v, total), found: !!k.name };
      }),
    };
  };

  const fetchChannels = (p) => {
    const recs = filterRecs(p);
    const total = sum(recs);
    return {
      total,
      channels: LeadStore.CHANNELS.map(c => {
        const n = sum(recs.filter(r => r.channel === c));
        return { channel: c, count: n, percentage: pct(n, total) };
      }),
    };
  };

  const fetchBranches = (p) => {
    const recs = filterRecs(p);
    const mets = filterMetrics(p);
    const statuses = statusColumns();
    const order = (cfg().BRANCH_ORDER || []).map(norm);

    // Collect all branches present in the dataset or configured in BRANCH_ORDER
    const allBranches = Array.from(new Set([...(cfg().BRANCH_ORDER || []), ...LeadStore.records().map(r => r.branch)]));

    const rowFor = (bRecs, bMets, name) => ({
      branch: name,
      total_leads: sum(bRecs),
      channels: LeadStore.CHANNELS.map(c => sum(bRecs.filter(r => r.channel === c))),
      statuses: statuses.map(s => (s.name ? metricTotal(bMets, s.name) : 0)),
    });

    const rows = allBranches.map(b => rowFor(
      recs.filter(r => r.branch === b),
      mets && mets.filter(m => m.branch === b),
      b
    ));

    // Sort by configured branch order
    rows.sort((a, b) => {
      const ia = order.indexOf(norm(a.branch)), ib = order.indexOf(norm(b.branch));
      return (ia < 0 ? 999 : ia) - (ib < 0 ? 999 : ib) || b.total_leads - a.total_leads;
    });

    return {
      data: rows,
      totals: rowFor(recs, mets, 'Total'),
      channels: LeadStore.CHANNELS,
      statusLabels: statuses.map(s => s.wanted),
    };
  };

  /** All outcome / quality columns from the sheet */
  const fetchOutcomes = (p) => {
    const total = sum(filterRecs(p));
    const mets = filterMetrics(p);
    return {
      total,
      available: mets !== null,
      items: LeadStore.metricNames().map(n => {
        const v = metricTotal(mets, n) || 0;
        return { name: n, value: v, percentage: pct(v, total) };
      }),
    };
  };

  const fetchFilters = () => {
    const order = cfg().BRANCH_ORDER || [];
    const presentBranches = Array.from(new Set(LeadStore.records().map(r => r.branch)));
    const branches = order.length
      ? [...order.filter(b => presentBranches.includes(b)), ...presentBranches.filter(b => !order.includes(b))]
      : presentBranches.sort();

    // The 7 canonical channels (Problem 2 & Problem 3)
    const channels = LeadStore.CHANNELS;
    return { branches, channels };
  };

  // Most recent day that actually has leads
  const latestLeadDate = () => LeadStore.records().reduce((max, r) => (r.count > 0 && r.date > max ? r.date : max), '');

  const wrap = (fn) => (...args) => Promise.resolve().then(() => fn(...args));

  return {
    fetchKPIs: wrap(fetchKPIs),
    fetchChannels: wrap(fetchChannels),
    fetchBranches: wrap(fetchBranches),
    fetchOutcomes: wrap(fetchOutcomes),
    fetchFilters: wrap(fetchFilters),
    triggerSync: () => LeadStore.syncFromSheet(),
    latestLeadDate,
  };
})();
