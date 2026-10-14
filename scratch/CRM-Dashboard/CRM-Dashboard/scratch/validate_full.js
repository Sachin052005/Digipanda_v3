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
  // Match DD/MM/YYYY or DD-MM-YYYY
  let m = s.match(/^(\d{1,2})[\/\.-](\d{1,2})[\/\.-](\d{2,4})/);
  if (m) {
    let day = parseInt(m[1], 10);
    let month = parseInt(m[2], 10);
    let year = parseInt(m[3], 10);
    if (year < 100) year += 2000;
    // Check if month and day are valid
    if (month >= 1 && month <= 12 && day >= 1 && day <= 31) {
      const dt = new Date(year, month - 1, day);
      if (dt.getFullYear() === year && dt.getMonth() === month - 1 && dt.getDate() === day) {
        return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      }
    }
  }
  // Match YYYY-MM-DD
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

function classifyChannel(h) {
  const l = h.toLowerCase().replace(/\s+/g, ' ').trim();
  if (l.includes('influencer')) return 'Influencer';
  if (l.includes('instagram') || /\binsta\b/.test(l)) return 'Instagram';
  if (l.includes('google call') || (l.includes('google') && l.includes('call'))) return 'Google Calls';
  // SEO check: must check before ad if it has 'seo' without 'google ad/'
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

async function runValidation() {
  const summary = [];
  for (const b of BRANCHES) {
    const url = `https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/gviz/tq?tqx=out:csv&headers=1&gid=${b.gid}`;
    const text = await fetch(url).then(r => r.text());
    const rows = parseCSV(text);
    const headers = rows[0] || [];
    
    // detect date col
    let dateCol = headers.findIndex(h => /date|day/i.test(h));
    if (dateCol < 0) {
      // sample rows
      const sample = rows.slice(1, 10);
      for (let c = 0; c < headers.length; c++) {
        if (sample.filter(r => parseDate(r[c])).length >= 2) {
          dateCol = c;
          break;
        }
      }
    }
    if (dateCol < 0 && rows.slice(1).some(r => parseDate(r[0]))) dateCol = 0;

    // channel cols
    const channelMap = {};
    const unmappedCols = [];
    headers.forEach((h, idx) => {
      if (idx === dateCol || !h) return;
      const ch = classifyChannel(h);
      if (ch) {
        channelMap[ch] = { col: idx, header: h };
      } else {
        unmappedCols.push({ col: idx, header: h });
      }
    });

    let validDates = 0, invalidDates = 0, totalLeadsSum = 0;
    const channelTotals = {};
    CANONICAL_CHANNELS.forEach(c => channelTotals[c] = 0);

    const datesList = [];
    rows.slice(1).forEach((r, rIdx) => {
      const d = parseDate(r[dateCol]);
      if (d) {
        validDates++;
        datesList.push(d);
        let rowSum = 0;
        CANONICAL_CHANNELS.forEach(c => {
          if (channelMap[c]) {
            const val = parseNum(r[channelMap[c].col]) || 0;
            channelTotals[c] += val;
            rowSum += val;
          }
        });
        totalLeadsSum += rowSum;
      } else {
        if (r.some(cell => cell.trim())) {
          invalidDates++;
        }
      }
    });

    summary.push({
      branch: b.name,
      gid: b.gid,
      totalRows: rows.length,
      dataRows: rows.length - 1,
      validDates,
      invalidDates,
      dateRange: datesList.length ? `${datesList[0]} to ${datesList[datesList.length - 1]}` : 'N/A',
      channelsFound: Object.keys(channelMap),
      missingChannels: CANONICAL_CHANNELS.filter(c => !channelMap[c]),
      channelTotals,
      totalLeads: totalLeadsSum,
      unmappedHeaders: unmappedCols.map(u => u.header)
    });
  }

  console.log(JSON.stringify(summary, null, 2));
  fs.writeFileSync('scratch/full_validation_report.json', JSON.stringify(summary, null, 2));
}

runValidation();
