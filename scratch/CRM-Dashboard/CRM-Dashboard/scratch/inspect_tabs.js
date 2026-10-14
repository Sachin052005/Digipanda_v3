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

async function inspectAllTabs() {
  const report = [];
  for (const b of BRANCHES) {
    const url = `https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/gviz/tq?tqx=out:csv&headers=1&gid=${b.gid}`;
    try {
      const res = await fetch(url);
      if (!res.ok) {
        console.log(`[FAIL] ${b.name} (GID: ${b.gid}): HTTP ${res.status}`);
        report.push({ branch: b.name, gid: b.gid, status: `HTTP ${res.status}` });
        continue;
      }
      const text = await res.text();
      const rows = parseCSV(text);
      console.log(`\n======================================================`);
      console.log(`BRANCH: ${b.name} | GID: ${b.gid} | Status: OK | Rows: ${rows.length}`);
      console.log(`Headers (${rows[0]?.length || 0} cols):`, JSON.stringify(rows[0]));
      if (rows.length > 1) console.log(`Row 1:`, JSON.stringify(rows[1]));
      if (rows.length > 2) console.log(`Row 2:`, JSON.stringify(rows[2]));
      if (rows.length > 3) console.log(`Row 3:`, JSON.stringify(rows[3]));

      // analyze dates, empty rows, etc
      let validDates = 0, invalidDates = 0;
      const headerRow = rows[0] || [];
      const dataRows = rows.slice(1);
      dataRows.forEach(r => {
        const val = r[0] || '';
        if (/\d/.test(val)) validDates++;
        else invalidDates++;
      });
      console.log(`Dates in col 0: ~${validDates} date-like, ${invalidDates} other`);
      report.push({
        branch: b.name,
        gid: b.gid,
        status: 'OK',
        rowCount: rows.length,
        headers: headerRow
      });
    } catch (e) {
      console.log(`[ERROR] ${b.name} (GID: ${b.gid}): ${e.message}`);
      report.push({ branch: b.name, gid: b.gid, status: `ERROR: ${e.message}` });
    }
  }
  fs.writeFileSync('scratch/report_tabs.json', JSON.stringify(report, null, 2));
}

inspectAllTabs();
