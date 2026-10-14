/**
 * Dashboard configuration. Centralized configuration for all 8 branches.
 * Edit these values without any build step needed.
 */
window.DASHBOARD_CONFIG = {
  // Authentication configuration
  AUTH: {
    TITLE: 'CRM Dashboard',
    USERNAME: 'Techpanda',
    PASSWORD: 'Tech@2026',
  },

  // Common Google Spreadsheet ID
  SPREADSHEET_ID: '1PiCtFM-k_dCz87XR0Vso2d9NImnw0P8hsNuAq2D_-zE',

  // All 8 branches mapped to their exact name and GID
  BRANCHES: [
    { name: 'Tnagar', gid: '0' },
    { name: 'Velachery', gid: '875342187' },
    { name: 'CBE', gid: '1844546948' },
    { name: 'OMR', gid: '694041727' },
    { name: 'Porur', gid: '592575622' },
    { name: 'Tambaram', gid: '813463373' },
    { name: 'Anna Nagar', gid: '1607111616' },
    { name: 'Kochi', gid: '2113729191' },
  ],

  // Backward-compatible SHEET_URL list generated from BRANCHES
  get SHEET_URL() {
    return this.BRANCHES.map(b =>
      `https://docs.google.com/spreadsheets/d/${this.SPREADSHEET_ID}/edit?gid=${b.gid}#gid=${b.gid}`
    );
  },

  // The 7 canonical channels in required display order (Problem 4)
  CHANNELS: [
    'Meta WhatsApp',
    'Meta Lead Form',
    'Website (Google Ad)',
    'Website (Google SEO)',
    'Instagram',
    'Google Calls',
    'Influencer',
  ],

  // Live refresh interval in seconds (5 minutes = 300s to avoid aggressive polling, Problem 11)
  REFRESH_INTERVAL: 300,

  // The 3 coloured KPI cards (green, yellow, red)
  KPI_METRICS: ['Connected', 'Prospected', 'Call not connected'],

  // The last 3 table columns with normal styling (Problem 6)
  STATUS_COLUMNS: ['New Leads', 'Existing Leads', 'Missed Leads'],

  // Display order for branches in tables and charts
  BRANCH_ORDER: ['Tnagar', 'Velachery', 'CBE', 'OMR', 'Porur', 'Tambaram', 'Anna Nagar', 'Kochi'],

  // Date parsing preference: India standard day-first (DMY)
  DATE_ORDER: 'DMY',

  // Reference date: null = most recent date with leads in the sheet
  REFERENCE_DATE: null,
};
