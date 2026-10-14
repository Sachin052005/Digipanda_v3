const fs = require('fs');

const SPREADSHEET_ID = '1PiCtFM-k_dCz87XR0Vso2d9NImnw0P8hsNuAq2D_-zE';
const BRANCHES = [
  { name: 'Tnagar', gid: '0' },
  { name: 'Velachery', gid: '875342187' },
  { name: 'CBE', gid: '1844546948' },
  { name: 'OMR', gid: '694041727' },
  { name: 'Porur', gid: '592575622' },
  { name: 'Tambaram', gid: '813463373' },
  { name: 'Anna Nagar', gid: '1607111616' },
  { name: 'Kochi', gid: '2113729191' },
];

const CANONICAL_CHANNELS = [
  'Meta WhatsApp',
  'Meta Lead Form',
  'Website (Google Ad)',
  'Website (Google SEO)',
  'Instagram',
  'Google Calls',
  'Influencer'
];

function classifyChannel(h) {
  const l = h.toLowerCase().replace(/\s+/g, ' ').trim();
  if (l.includes('influencer')) return 'Influencer';
  if (l.includes('instagram') || /\binsta\b/.test(l)) return 'Instagram';
  if (l.includes('google call') || (l.includes('google') && l.includes('call'))) return 'Google Calls';
  if (l.includes('(seo)') || l.includes('leads seo') || l.includes('leads(seo)') || (l.includes('seo') && !l.includes('google ad/'))) {
    return 'Website (Google SEO)';
  }
  if (l.includes('google ad') || l.includes('google ads') || l.includes('adwords') || l.includes('google form') || l.includes('website') || l.includes('webiste')) {
    return 'Website (Google Ad)';
  }
  if (l.includes('lead form') || l.includes('leadform') || (l.includes('meta') && l.includes('form')) || l.includes('facebook')) {
    return 'Meta Lead Form';
  }
  if (l.includes('whatsapp') || l.includes('whats app') || l.includes('meta')) {
    return 'Meta WhatsApp';
  }
  return null;
}

function parseCSV(text) {
  const rows = [];
  let row = [], cell = '', inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') { cell += '"'; i++; }
        else { inQuotes = false; }
      } else { cell += c; }
    } else {
      if (c === '"') { inQuotes = true; }
      else if (c === ',') { row.push(cell.trim()); cell = ''; }
      else if (c === '\n' || c === '\r') {
        if (c === '\r' && text[i + 1] === '\n') i++;
        row.push(cell.trim()); rows.push(row); row = []; cell = '';
      } else { cell += c; }
    }
  }
  if (cell !== '' || row.length) { row.push(cell.trim()); rows.push(row); }
  return rows.filter(r => r.some(c => c !== ''));
}

function parseNum(v) {
  const s = String(v == null ? '' : v).replace(/[,\s₹]/g, '').trim();
  if (s === '' || s === '-') return 0;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

function parseDate(v) {
  const s = String(v || '').trim();
  if (!s) return null;
  let m = s.match(/^(\d{1,2})[\/\.-](\d{1,2})[\/\.-](\d{2,4})/);
  if (m) {
    let day = parseInt(m[1], 10);
    let month = parseInt(m[2], 10);
    let year = parseInt(m[3], 10);
    if (year < 100) year += 2000;
    if (month >= 1 && month <= 12 && day >= 1 && day <= 31) {
      const dt = new Date(year, month - 1, day);
      if (dt.getFullYear() === year && dt.getMonth() === month - 1 && dt.getDate() === day) {
        return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      }
    }
  }
  m = s.match(/^(\d{4})[\/\.-](\d{1,2})[\/\.-](\d{1,2})/);
  if (m) {
    let year = parseInt(m[1], 10);
    let month = parseInt(m[2], 10);
    let day = parseInt(m[3], 10);
    const dt = new Date(year, month - 1, day);
    if (dt.getFullYear() === year && dt.getMonth() === month - 1 && dt.getDate() === day) {
      return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    }
  }
  return null;
}

async function testFetchAndProcess() {
  const records = [];
  const metrics = [];
  const branchStatuses = [];

  for (const b of BRANCHES) {
    const url = `https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/gviz/tq?tqx=out:csv&headers=1&gid=${b.gid}`;
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const text = await res.text();
      const rows = parseCSV(text);
      const headers = rows[0] || [];

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
        if (dateIdx < 0 && sampleRows.some(r => parseDate(r[0]))) dateIdx = 0;
      }
      if (dateIdx < 0) throw new Error('No Date column');

      // Map channel columns
      const channelCols = [];
      const metricCols = [];
      headers.forEach((h, idx) => {
        if (idx === dateIdx || !h) return;
        const ch = classifyChannel(h);
        if (ch) {
          channelCols.push({ idx, channel: ch });
        } else {
          metricCols.push({ idx, header: h });
        }
      });

      // Map rows
      let bLeadCount = 0;
      rows.slice(1).forEach(r => {
        const date = parseDate(r[dateIdx]);
        if (!date) return;

        // Channel counts
        channelCols.forEach(c => {
          const count = parseNum(r[c.idx]) || 0;
          records.push({ date, branch: b.name, channel: c.channel, count });
          bLeadCount += count;
        });

        // Other numeric metrics
        metricCols.forEach(c => {
          const val = parseNum(r[c.idx]);
          if (val !== null && val > 0) {
            metrics.push({ date, branch: b.name, name: c.header, value: val });
          }
        });
      });

      branchStatuses.push({ branch: b.name, status: 'OK', leads: bLeadCount });
    } catch (e) {
      branchStatuses.push({ branch: b.name, status: 'FAIL', error: e.message });
    }
  }

  console.log('Branch statuses:', branchStatuses);
  console.log('Total records:', records.length);
  const totalLeads = records.reduce((s, r) => s + r.count, 0);
  console.log('Total Leads:', totalLeads);

  // Group by channel
  const byChan = {};
  CANONICAL_CHANNELS.forEach(c => byChan[c] = 0);
  records.forEach(r => { byChan[r.channel] += r.count; });
  console.log('Channels breakdown:', byChan);
}

testFetchAndProcess();
