/**
 * Data Store
 * Reads Google Sheets tabs (CSV) and normalizes records across all 8 branches:
 *   records: { date, branch, channel, count }   -> lead counts per canonical channel
 *   metrics: { date, branch, name, value }      -> outcome/status metrics (Connected, Prospected, etc.)
 */

const LeadStore = (() => {
  let records = [];
  let metrics = [];
  let metricNames = [];
  let lastSync = null;
  let lastText = null;
  const branchCache = new Map(); // branchName -> { recs, mets, rawCount, days, text }

  const CANONICAL_CHANNELS = [
    'Meta WhatsApp',
    'Meta Lead Form',
    'Website (Google Ad)',
    'Website (Google SEO)',
    'Instagram',
    'Google Calls',
    'Influencer',
  ];

  /* ---------- helpers ---------- */
  const pad = (n) => String(n).padStart(2, '0');
  const toISO = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const clean = (s) => String(s == null ? '' : s).replace(/\s+/g, ' ').trim();
  const MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];

  const parseNum = (v) => {
    const s = clean(v).replace(/[,₹\s]/g, '');
    if (s === '' || s === '-') return 0;
    const n = Number(s);
    return Number.isFinite(n) ? n : null;
  };

  /* ---------- CSV Parser ---------- */
  const parseCSV = (text) => {
    const rows = [];
    let row = [], cell = '', inQuotes = false;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (inQuotes) {
        if (ch === '"') {
          if (text[i + 1] === '"') { cell += '"'; i++; }
          else { inQuotes = false; }
        } else {
          cell += ch;
        }
      } else {
        if (ch === '"') {
          inQuotes = true;
        } else if (ch === ',') {
          row.push(cell);
          cell = '';
        } else if (ch === '\n' || ch === '\r') {
          if (ch === '\r' && text[i + 1] === '\n') i++;
          row.push(cell);
          rows.push(row);
          row = [];
          cell = '';
        } else {
          cell += ch;
        }
      }
    }
    if (cell !== '' || row.length) { row.push(cell); rows.push(row); }
    return rows.filter(r => r.some(c => clean(c)));
  };

  /* ---------- Date Parser (Deterministic, avoids JS new Date ambiguities) ---------- */
  const parseDate = (val, order = 'DMY') => {
    const v = clean(val);
    if (!v) return null;

    // Check Google Sheets serial date number (e.g. 46300)
    if (/^\d{5}$/.test(v)) {
      const serial = Number(v);
      if (serial > 30000 && serial < 60000) {
        const utcDays = serial - 25569;
        const utcVal = utcDays * 86400;
        const dateInfo = new Date(utcVal * 1000);
        return toISO(dateInfo);
      }
    }

    let m;
    const mk = (y, mo, d) => {
      y = +y; if (y < 100) y += 2000;
      const dt = new Date(y, +mo - 1, +d);
      return dt.getFullYear() === y && dt.getMonth() === +mo - 1 && dt.getDate() === +d ? toISO(dt) : null;
    };
    const mon = (s) => MONTHS.indexOf(String(s).slice(0, 3).toLowerCase()) + 1;
    const thisYear = new Date().getFullYear();

    // Standard YYYY-MM-DD
    if ((m = v.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})/))) return mk(m[1], m[2], m[3]);

    // DD/MM/YYYY or MM/DD/YYYY
    if ((m = v.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})/))) {
      return order === 'MDY' ? mk(m[3], m[1], m[2]) : mk(m[3], m[2], m[1]);
    }

    // "01-Oct-2026", "1 Oct 2026", "1st October 2026"
    if ((m = v.match(/^(\d{1,2})(?:st|nd|rd|th)?[\s\-/.]*([A-Za-z]{3,})\.?,?[\s\-/.]*(\d{2,4})?/)) && mon(m[2])) {
      return mk(m[3] || thisYear, mon(m[2]), m[1]);
    }

    // "Oct 1, 2026" or "Wed, Oct 1 2026"
    const noDay = v.replace(/^(mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?,?\s*/i, '');
    if (noDay !== v) return parseDate(noDay, order);
    if ((m = v.match(/^([A-Za-z]{3,})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})?/)) && mon(m[1])) {
      return mk(m[3] || thisYear, mon(m[1]), m[2]);
    }

    return null;
  };

  /* ---------- Canonical Channel Classification (Centralized, Problem 9 D) ---------- */
  const classifyChannel = (header) => {
    const l = clean(header).toLowerCase();
    if (!l) return null;

    // 1. Influencer
    if (l.includes('influencer')) return 'Influencer';

    // 2. Instagram
    if (l.includes('instagram') || /\binsta\b/.test(l)) return 'Instagram';

    // 3. Google Calls
    if (l.includes('google call') || (l.includes('google') && l.includes('call'))) return 'Google Calls';

    // 4. Website (Google SEO) - check before Google Ad when 'seo' is present
    if (l.includes('(seo)') || l.includes('leads seo') || l.includes('leads(seo)') || (l.includes('seo') && !l.includes('google ad/'))) {
      return 'Website (Google SEO)';
    }

    // 5. Website (Google Ad)
    if (l.includes('google ad') || l.includes('google ads') || l.includes('adwords') || l.includes('google form') || l.includes('website') || l.includes('webiste')) {
      return 'Website (Google Ad)';
    }

    // 6. Meta Lead Form
    if (l.includes('lead form') || l.includes('leadform') || (l.includes('meta') && l.includes('form')) || l.includes('facebook')) {
      return 'Meta Lead Form';
    }

    // 7. Meta WhatsApp
    if (l.includes('whatsapp') || l.includes('whats app') || l.includes('meta')) {
      return 'Meta WhatsApp';
    }

    return null;
  };

  const isTotalHeader = (h) => /^total\s*leads?$/i.test(clean(h));

  /* ---------- Layout 1: Daily summary with explicit configured branch ---------- */
  const mapSummary = (rows, headers, configuredBranch) => {
    const branchName = configuredBranch || (window.DASHBOARD_CONFIG?.DEFAULT_BRANCH) || 'Main Branch';

    // Date column detection: header search with sample data fallback
    let dateIdx = headers.findIndex(h => /date|day/i.test(h));
    if (dateIdx < 0) {
      const sampleRows = rows.slice(1, Math.min(rows.length, 15));
      for (let col = 0; col < headers.length; col++) {
        const matches = sampleRows.filter(r => parseDate(r[col])).length;
        if (matches >= Math.min(2, sampleRows.length)) {
          dateIdx = col;
          break;
        }
      }
      if (dateIdx < 0 && sampleRows.some(r => parseDate(r[0]))) {
        dateIdx = 0;
      }
    }
    if (dateIdx < 0) throw new Error(`No "Date" column found in tab for branch ${branchName}.`);

    const channelCols = [];
    const metricCols = [];

    headers.forEach((h, i) => {
      if (i === dateIdx || !h) return;
      const ch = classifyChannel(h);
      if (ch) {
        channelCols.push({ i, channel: ch });
      } else {
        const cleanedH = clean(h);
        metricCols.push({ i, header: cleanedH, isTotal: isTotalHeader(cleanedH) });
      }
    });

    if (!channelCols.length) {
      throw new Error(`No lead channel columns identified in tab for branch ${branchName}.`);
    }

    const order = (window.DASHBOARD_CONFIG?.DATE_ORDER) || 'DMY';
    const recs = [];
    const mets = [];
    const numericSeen = new Set();
    let days = 0;

    rows.slice(1).forEach(r => {
      const date = parseDate(r[dateIdx], order);
      if (!date) return; // skip totals, empty rows, notes

      let any = false;

      // Map verified channel counts
      channelCols.forEach(c => {
        const n = parseNum(r[c.i]) || 0;
        if (n > 0) any = true;
        recs.push({ date, branch: branchName, channel: c.channel, count: n });
      });

      // Map outcome & quality metrics
      metricCols.forEach(c => {
        if (c.isTotal) return;
        const n = parseNum(r[c.i]);
        if (n === null) return;
        numericSeen.add(c.header);
        if (n > 0) {
          any = true;
          mets.push({ date, branch: branchName, name: c.header, value: n });
        }
      });

      if (any) days++;
    });

    const names = [];
    metricCols.forEach(c => {
      if (!c.isTotal && numericSeen.has(c.header) && !names.includes(c.header)) {
        names.push(c.header);
      }
    });

    return {
      recs,
      mets,
      names,
      rawCount: rows.length - 1,
      days,
      branch: branchName,
      layout: 'summary',
    };
  };

  /* ---------- Layout 2: One row per lead (CRM format) ---------- */
  const PHONE_HEADERS = ['phone', 'phone number', 'contact', 'mobile', 'phone_number', 'mobile number', 'contact number'];
  const mapPerLead = (rows, headers, configuredBranch) => {
    const branchName = configuredBranch || (window.DASHBOARD_CONFIG?.DEFAULT_BRANCH) || 'Main Branch';
    const find = (syns) => headers.findIndex(h => syns.includes(clean(h).toLowerCase()));
    const iPhone = find(PHONE_HEADERS);
    let iDate = headers.findIndex(h => /date/i.test(clean(h)));
    if (iDate < 0) {
      const sampleRows = rows.slice(1, Math.min(rows.length, 15));
      for (let col = 0; col < headers.length; col++) {
        if (sampleRows.filter(r => parseDate(r[col])).length >= Math.min(2, sampleRows.length)) {
          iDate = col;
          break;
        }
      }
    }
    const iBranch = find(['branch', 'branch name', 'location', 'city', 'centre', 'center']);
    const iChannel = find(['channel', 'source', 'lead channel', 'lead source', 'marketing channel']);
    const iStatus = find(['crm status', 'crm_status', 'status', 'lead status', 'stage']);
    const order = (window.DASHBOARD_CONFIG?.DATE_ORDER) || 'DMY';
    const today = toISO(new Date());

    const recs = [], mets = [], names = [];
    const seenRecords = new Set();

    rows.slice(1).forEach((r, idx) => {
      const phone = clean(r[iPhone]).replace(/[^\d+]/g, '');
      const rawDate = iDate >= 0 ? parseDate(r[iDate], order) : today;
      const date = rawDate || today;
      const branch = clean(r[iBranch]) || branchName;
      const ch = classifyChannel(clean(r[iChannel])) || 'Website (Google Ad)';
      const status = iStatus >= 0 ? clean(r[iStatus]) : '';

      // De-duplicate only exact identical submissions (phone + date + channel)
      const recordKey = `${phone}_${date}_${branch}_${ch}`;
      if (phone && seenRecords.has(recordKey)) return;
      if (phone) seenRecords.add(recordKey);

      recs.push({ date, branch, channel: ch, count: 1 });

      if (status) {
        const name = status.replace(/\b\w/g, c => c.toUpperCase());
        if (!names.includes(name)) names.push(name);
        mets.push({ date, branch, name, value: 1 });
      }
    });

    return {
      recs,
      mets,
      names,
      rawCount: rows.length - 1,
      days: new Set(recs.map(r => r.date)).size,
      branch: branchName,
      layout: 'per-lead',
    };
  };

  const mapRows = (rows, configuredBranch) => {
    if (!rows || rows.length < 2) throw new Error(`Sheet for ${configuredBranch || 'branch'} has no data rows below the header.`);
    const headers = rows[0].map(clean);
    const hasPhone = headers.some(h => PHONE_HEADERS.includes(h.toLowerCase()));
    return hasPhone ? mapPerLead(rows, headers, configuredBranch) : mapSummary(rows, headers, configuredBranch);
  };

  /* ---------- Google Sheet URLs ---------- */
  const sheetCsvUrl = (url) => {
    const idMatch = String(url).match(/\/spreadsheets\/d\/([a-zA-Z0-9-_]+)/);
    if (!idMatch) throw new Error('Could not read spreadsheet ID from Google Sheet link.');
    const gidMatch = String(url).match(/[#&?]gid=([0-9]+)/);
    return `https://docs.google.com/spreadsheets/d/${idMatch[1]}/gviz/tq?tqx=out:csv&headers=1&gid=${gidMatch ? gidMatch[1] : '0'}`;
  };

  const getBranchConfigs = () => {
    const cfg = window.DASHBOARD_CONFIG || {};
    if (Array.isArray(cfg.BRANCHES) && cfg.BRANCHES.length > 0) {
      const spId = cfg.SPREADSHEET_ID || '1PiCtFM-k_dCz87XR0Vso2d9NImnw0P8hsNuAq2D_-zE';
      return cfg.BRANCHES.map(b => ({
        name: b.name,
        gid: String(b.gid),
        url: `https://docs.google.com/spreadsheets/d/${spId}/gviz/tq?tqx=out:csv&headers=1&gid=${b.gid}`,
      }));
    }
    const urls = (Array.isArray(cfg.SHEET_URL) ? cfg.SHEET_URL : [cfg.SHEET_URL]).filter(Boolean);
    return urls.map((u, i) => {
      const gidMatch = String(u).match(/[#&?]gid=([0-9]+)/);
      return {
        name: (cfg.BRANCH_ORDER && cfg.BRANCH_ORDER[i]) || `Branch ${i + 1}`,
        gid: gidMatch ? gidMatch[1] : String(i),
        url: sheetCsvUrl(u),
      };
    });
  };

  /* ---------- State Management ---------- */
  const init = () => {
    records = [];
    metrics = [];
    metricNames = [];
    lastSync = null;
    lastText = null;
    branchCache.clear();
  };

  const applyResults = (results, source, warnings = []) => {
    records = [];
    metrics = [];
    metricNames = [];
    let raw = 0, days = 0;

    results.forEach(r => {
      records.push(...r.recs);
      metrics.push(...r.mets);
      raw += r.rawCount;
      days += r.days;
      r.names.forEach(n => {
        if (!metricNames.includes(n)) metricNames.push(n);
      });
    });

    lastSync = {
      source,
      completed_at: new Date().toISOString(),
      rows_processed: raw,
      days,
      total_leads: records.reduce((s, r) => s + r.count, 0),
      layout: results[0]?.layout || 'summary',
      status: warnings.length ? 'PARTIAL' : 'SUCCESS',
      warning: warnings.length ? warnings.join('; ') : null,
    };
    return lastSync;
  };

  const fetchText = async (url) => {
    const res = await fetch(`${url}&_=${Date.now()}`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`Google Sheet returned HTTP ${res.status}. Verify sharing permissions.`);
    const text = await res.text();
    if (/^\s*<(!doctype|html)/i.test(text)) throw new Error('Google returned a login page instead of CSV data.');
    return text;
  };

  /* ---------- Synchronization with Partial Failure Handling (Problem 11) ---------- */
  const syncFromSheet = async () => {
    const branches = getBranchConfigs();
    if (!branches.length) throw new Error('No branches or sheet URLs configured in js/config.js');

    const responses = await Promise.allSettled(branches.map(async (b) => {
      const text = await fetchText(b.url);
      return { branch: b.name, gid: b.gid, text };
    }));

    const results = [];
    const warnings = [];
    const validTexts = [];
    const branchStatuses = [];

    responses.forEach((res, i) => {
      const bConfig = branches[i];
      if (res.status === 'fulfilled') {
        const { branch, gid, text } = res.value;
        try {
          const parsed = mapRows(parseCSV(text), branch);
          branchCache.set(branch, { ...parsed, text });
          results.push(parsed);
          validTexts.push(text);
          branchStatuses.push({ branch, gid, status: 'OK', leads: parsed.recs.reduce((s, r) => s + r.count, 0) });
        } catch (err) {
          warnings.push(`${branch} (GID ${gid}): ${err.message}`);
          branchStatuses.push({ branch, gid, status: 'PARSE_ERROR', error: err.message });
          // Preserve cached data if available
          if (branchCache.has(branch)) {
            results.push(branchCache.get(branch));
          }
        }
      } else {
        const errText = res.reason?.message || 'Network fetch failed';
        warnings.push(`${bConfig.name} (GID ${bConfig.gid}): ${errText}`);
        branchStatuses.push({ branch: bConfig.name, gid: bConfig.gid, status: 'FETCH_ERROR', error: errText });
        // Preserve cached data if available
        if (branchCache.has(bConfig.name)) {
          results.push(branchCache.get(bConfig.name));
        }
      }
    });

    if (!results.length) {
      throw new Error(warnings.length ? warnings.join('; ') : 'No data could be loaded from any branch.');
    }

    const joined = validTexts.join('\u0000');
    if (joined === lastText && lastSync && !warnings.length) {
      lastSync.completed_at = new Date().toISOString();
      lastSync.branchStatuses = branchStatuses;
      return { ...lastSync, changed: false };
    }

    const log = applyResults(results, 'Google Sheet', warnings);
    log.branchStatuses = branchStatuses;
    lastText = joined;
    return { ...log, changed: true };
  };

  const importCSVText = (text, fileName) => {
    lastText = null;
    const branchName = (window.DASHBOARD_CONFIG?.DEFAULT_BRANCH) || 'Imported';
    return applyResults([mapRows(parseCSV(text), branchName)], fileName || 'CSV file');
  };

  return {
    CHANNELS: CANONICAL_CHANNELS,
    init,
    records: () => records,
    metrics: () => metrics,
    metricNames: () => metricNames,
    lastSync: () => lastSync,
    sheetUrls: () => getBranchConfigs().map(b => b.url),
    syncFromSheet,
    importCSVText,
    toISO,
    _test: { parseDate, parseCSV, classifyChannel, mapRows, mapSummary },
  };
})();
