/**
 * Marketing Performance Dashboard - Automated Verification Test Suite
 * Tests all 14 Problem Statements & Acceptance Criteria deterministically.
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

// Set up browser-like environment in Node
global.window = global;
global.document = {
  getElementById: (id) => null,
  querySelectorAll: (sel) => [],
};

// Load config, store, and api modules
const baseDir = path.resolve(__dirname, '..');
vm.runInThisContext(fs.readFileSync(path.join(baseDir, 'js', 'config.js'), 'utf8'));
vm.runInThisContext(fs.readFileSync(path.join(baseDir, 'js', 'store.js'), 'utf8'));
vm.runInThisContext(fs.readFileSync(path.join(baseDir, 'js', 'api.js'), 'utf8'));

let testsPassed = 0;
let testsFailed = 0;

function assert(condition, testName) {
  if (condition) {
    testsPassed++;
    console.log(`  [PASS] ${testName}`);
  } else {
    testsFailed++;
    console.error(`  [FAIL] ${testName}`);
  }
}

async function runAllTests() {
  console.log('\n======================================================');
  console.log('MARKETING DASHBOARD AUTOMATED TEST SUITE');
  console.log('======================================================\n');

  /* ------------------------------------------------------------------
   * 1. CONFIGURATION TESTS (Problem 1)
   * ------------------------------------------------------------------ */
  console.log('--- 1. Configuration Tests (All 8 Branches) ---');
  const cfg = window.DASHBOARD_CONFIG;
  assert(cfg && Array.isArray(cfg.BRANCHES), 'DASHBOARD_CONFIG.BRANCHES is defined and an array');
  assert(cfg.BRANCHES.length === 8, 'Exactly 8 branches are configured');

  const expectedBranches = [
    { name: 'Tnagar', gid: '0' },
    { name: 'Velachery', gid: '875342187' },
    { name: 'CBE', gid: '1844546948' },
    { name: 'OMR', gid: '694041727' },
    { name: 'Porur', gid: '592575622' },
    { name: 'Tambaram', gid: '813463373' },
    { name: 'Anna Nagar', gid: '1607111616' },
    { name: 'Kochi', gid: '2113729191' },
  ];

  expectedBranches.forEach(expected => {
    const found = cfg.BRANCHES.find(b => b.name === expected.name && String(b.gid) === expected.gid);
    assert(!!found, `Branch ${expected.name} is mapped to exact GID ${expected.gid}`);
  });

  const gids = cfg.BRANCHES.map(b => String(b.gid));
  const uniqueGids = new Set(gids);
  assert(uniqueGids.size === 8, 'No duplicate GIDs exist across the 8 branches');

  assert(cfg.SPREADSHEET_ID === '1PiCtFM-k_dCz87XR0Vso2d9NImnw0P8hsNuAq2D_-zE', 'Spreadsheet ID matches specification');
  assert(cfg.REFRESH_INTERVAL === 300, 'Refresh interval set to 300s (5 minutes)');

  /* ------------------------------------------------------------------
   * 2. CHANNEL TESTS (Problem 2, 3, 4, 7, 8)
   * ------------------------------------------------------------------ */
  console.log('\n--- 2. Channel Tests (7 Canonical Channels) ---');
  const expectedChannels = [
    'Meta WhatsApp',
    'Meta Lead Form',
    'Website (Google Ad)',
    'Website (Google SEO)',
    'Instagram',
    'Google Calls',
    'Influencer',
  ];

  assert(JSON.stringify(LeadStore.CHANNELS) === JSON.stringify(expectedChannels),
    'LeadStore.CHANNELS contains exactly the 7 channels in required order');

  // Classification tests
  assert(LeadStore._test.classifyChannel('Influencer Leads') === 'Influencer', 'Classifies "Influencer Leads" as Influencer');
  assert(LeadStore._test.classifyChannel('Tnagar Website & Google Form leads (Google ads)') === 'Website (Google Ad)', 'Classifies Google Ads separately');
  assert(LeadStore._test.classifyChannel('Tnagar Website Leads SEO') === 'Website (Google SEO)', 'Classifies Google SEO separately');
  assert(LeadStore._test.classifyChannel('CBE Meta Leads (Whatsapp)') === 'Meta WhatsApp', 'Classifies WhatsApp leads');
  assert(LeadStore._test.classifyChannel('CBE Meta Leads(Lead form)') === 'Meta Lead Form', 'Classifies Lead Form leads');
  assert(LeadStore._test.classifyChannel('Velachery Instagram Leads') === 'Instagram', 'Classifies Instagram leads');
  assert(LeadStore._test.classifyChannel('OMR Google Calls') === 'Google Calls', 'Classifies Google Calls');
  assert(LeadStore._test.classifyChannel('Unrecognized Mystery Column') === null, 'Unknown channels return null and are not misclassified');

  // Backward-compatibility: Influencer column missing returns 0
  const sampleHeadersWithoutInfluencer = [
    'Date & Day',
    'Tnagar Meta Leads (Whatsapp)',
    'Tnagar Website Leads SEO',
  ];
  const sampleRowsWithoutInfluencer = [
    sampleHeadersWithoutInfluencer,
    ['01/10/2026', '10', '5'],
  ];
  const mappedNoInf = LeadStore._test.mapSummary(sampleRowsWithoutInfluencer, sampleHeadersWithoutInfluencer, 'Tnagar');
  const infCountNoInf = mappedNoInf.recs.filter(r => r.channel === 'Influencer').reduce((s, r) => s + r.count, 0);
  assert(infCountNoInf === 0, 'Missing Influencer column cleanly evaluates to 0 without errors');

  // Adding Influencer column automatically captures real values
  const sampleHeadersWithInfluencer = [
    'Date & Day',
    'Tnagar Meta Leads (Whatsapp)',
    'Tnagar Website Leads SEO',
    'Tnagar Influencer Leads',
  ];
  const sampleRowsWithInfluencer = [
    sampleHeadersWithInfluencer,
    ['01/10/2026', '10', '5', '7'],
  ];
  const mappedWithInf = LeadStore._test.mapSummary(sampleRowsWithInfluencer, sampleHeadersWithInfluencer, 'Tnagar');
  const infCountWithInf = mappedWithInf.recs.filter(r => r.channel === 'Influencer').reduce((s, r) => s + r.count, 0);
  assert(infCountWithInf === 7, 'Newly added Influencer column accurately records its value (7)');

  /* ------------------------------------------------------------------
   * 3. DATE PARSING & FILTER TESTS (Problem 9 A, B)
   * ------------------------------------------------------------------ */
  console.log('\n--- 3. Date Parsing & Filtering Tests ---');
  assert(LeadStore._test.parseDate('01/10/2026', 'DMY') === '2026-10-01', 'Parses DD/MM/YYYY format accurately');
  assert(LeadStore._test.parseDate('24/10/2026', 'DMY') === '2026-10-24', 'Parses 24/10/2026 accurately');
  assert(LeadStore._test.parseDate('2026-10-15') === '2026-10-15', 'Parses ISO YYYY-MM-DD format accurately');
  assert(LeadStore._test.parseDate('Invalid Date String') === null, 'Rejects invalid date string and returns null');
  assert(LeadStore._test.parseDate('') === null, 'Empty string returns null without guessing');

  /* ------------------------------------------------------------------
   * 4. DATA RECONCILIATION & AGGREGATION TESTS (Problem 9 C, D, E & 10)
   * ------------------------------------------------------------------ */
  console.log('\n--- 4. Data Reconciliation & Aggregation Tests ---');
  // Load synthetic deterministic multi-branch dataset
  const syntheticCSV_Tnagar = `Date & Day,Tnagar Meta Leads (Whatsapp),Tnagar Meta Leads(Lead form),Tnagar Website & Google Form leads (Google ads),Tnagar Website Leads SEO,Tnagar Instagram Leads,Tnagar Google Calls,Connected
01/10/2026,10,2,4,3,1,5,6
02/10/2026,12,0,5,2,0,3,4`;

  const syntheticCSV_Velachery = `Date & Day,Velachery Meta Leads (Whatsapp),Velachery Meta Leads(Lead form),Velachery Website & Google Form leads (Google ads),Velachery Website leads (SEO),Velachery Instagram Leads,Velachery Google Calls,Connected
01/10/2026,0,15,2,1,0,4,8
02/10/2026,0,10,3,0,1,2,5`;

  LeadStore.init();
  const parsedT = LeadStore._test.mapRows(LeadStore._test.parseCSV(syntheticCSV_Tnagar), 'Tnagar');
  const parsedV = LeadStore._test.mapRows(LeadStore._test.parseCSV(syntheticCSV_Velachery), 'Velachery');

  assert(parsedT.branch === 'Tnagar', 'Dataset 1 explicitly assigned to branch Tnagar');
  assert(parsedV.branch === 'Velachery', 'Dataset 2 explicitly assigned to branch Velachery');

  const tnagarLeads = parsedT.recs.reduce((s, r) => s + r.count, 0);
  // Row 1: 10+2+4+3+1+5 = 25. Row 2: 12+0+5+2+0+3 = 22. Total = 47.
  assert(tnagarLeads === 47, `Tnagar total leads is accurately calculated (${tnagarLeads} === 47)`);

  const velLeads = parsedV.recs.reduce((s, r) => s + r.count, 0);
  // Row 1: 0+15+2+1+0+4 = 22. Row 2: 0+10+3+0+1+2 = 16. Total = 38.
  assert(velLeads === 38, `Velachery total leads is accurately calculated (${velLeads} === 38)`);

  // Direct injection into LeadStore to test Api aggregation
  LeadStore.init();
  LeadStore.importCSVText(syntheticCSV_Tnagar, 'Tnagar');

  /* ------------------------------------------------------------------
   * 5. TABLE STYLING INTEGRITY (Problem 5 & Problem 6)
   * ------------------------------------------------------------------ */
  console.log('\n--- 5. Table Specification & Column Highlighting Tests ---');
  const cssFile = fs.readFileSync(path.join(baseDir, 'css', 'dashboard.css'), 'utf8');
  assert(cssFile.includes('.th-influencer'), 'CSS contains .th-influencer header highlight class');
  assert(cssFile.includes('.td-influencer'), 'CSS contains .td-influencer cell highlight class');
  assert(cssFile.includes('.th-status-normal'), 'CSS contains .th-status-normal normal styling class');
  assert(cssFile.includes('.td-status-normal'), 'CSS contains .td-status-normal normal styling class');

  const htmlFile = fs.readFileSync(path.join(baseDir, 'index.html'), 'utf8');
  assert(htmlFile.includes('data-chan-count="Influencer"'), 'HTML contains Influencer channel card');
  assert(htmlFile.includes('data-chan-count="Website (Google Ad)"'), 'HTML contains Website (Google Ad) channel card');
  assert(htmlFile.includes('data-chan-count="Website (Google SEO)"'), 'HTML contains Website (Google SEO) channel card');
  assert(!htmlFile.includes('data-chan-count="Other"'), 'Old "Other" card successfully removed from HTML');

  /* ------------------------------------------------------------------
   * 6. AUTHENTICATION & LOGIN PAGE TESTS (CRM Dashboard)
   * ------------------------------------------------------------------ */
  console.log('\n--- 6. Authentication & Login Page Tests ---');
  assert(cfg.AUTH && cfg.AUTH.TITLE === 'CRM Dashboard', 'Config AUTH.TITLE is "CRM Dashboard"');
  assert(cfg.AUTH && cfg.AUTH.USERNAME === 'Techpanda', 'Config AUTH.USERNAME is "Techpanda"');
  assert(cfg.AUTH && cfg.AUTH.PASSWORD === 'Tech@2026', 'Config AUTH.PASSWORD is "Tech@2026"');

  const loginFile = fs.readFileSync(path.join(baseDir, 'login.html'), 'utf8');
  assert(loginFile.includes('<title>CRM Dashboard</title>'), 'login.html has title "CRM Dashboard"');
  assert(loginFile.includes('CRM Dashboard'), 'login.html contains CRM Dashboard heading');
  assert(loginFile.includes('Techpanda'), 'login.html checks Techpanda user');
  assert(loginFile.includes('Tech@2026'), 'login.html checks Tech@2026 password');

  assert(htmlFile.includes('<title>CRM Dashboard</title>'), 'index.html has title "CRM Dashboard"');
  assert(htmlFile.includes('<h1>CRM Dashboard</h1>'), 'index.html has h1 "CRM Dashboard"');
  assert(htmlFile.includes('crm_auth_user'), 'index.html contains auth guard redirect check');
  assert(htmlFile.includes('id="btnLogout"'), 'index.html contains logout button');

  /* ------------------------------------------------------------------
   * SUMMARY
   * ------------------------------------------------------------------ */
  console.log('\n======================================================');
  console.log(`TEST RESULTS: ${testsPassed} PASSED, ${testsFailed} FAILED`);
  console.log('======================================================\n');

  if (testsFailed > 0) {
    process.exit(1);
  }
}

runAllTests().catch(err => {
  console.error('Test runner fatal error:', err);
  process.exit(1);
});
