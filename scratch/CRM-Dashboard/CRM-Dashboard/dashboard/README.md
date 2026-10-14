# Marketing Performance Dashboard (Static HTML / CSS / JS)

A high-performance, zero-build client-side marketing analytics dashboard connecting live to Google Sheets across 8 branches.

No Python, database, or build step required: open `index.html` directly in any modern browser, or deploy to any static host (GitHub Pages, Netlify, Vercel, Cloudflare Pages, S3).

---

## 1. Configured Branches & Data Source

All branches are ingested from Google Spreadsheet ID:
`1PiCtFM-k_dCz87XR0Vso2d9NImnw0P8hsNuAq2D_-zE`

Configured in `js/config.js`:
1. **Tnagar** — GID: `0`
2. **Velachery** — GID: `875342187`
3. **CBE** — GID: `1844546948`
4. **OMR** — GID: `694041727`
5. **Porur** — GID: `592575622`
6. **Tambaram** — GID: `813463373`
7. **Anna Nagar** — GID: `1607111616`
8. **Kochi** — GID: `2113729191`

---

## 2. Seven Canonical Channels

The dashboard standardizes all incoming leads across 7 canonical channels:
1. `Meta WhatsApp`
2. `Meta Lead Form`
3. `Website (Google Ad)`
4. `Website (Google SEO)`
5. `Instagram`
6. `Google Calls`
7. `Influencer`

*Website Google Ads and Google SEO are treated as distinct categories across KPI cards, tables, and both charts.*
*The `Influencer` channel is backward-compatible: when absent in a branch sheet, it safely defaults to 0 without errors or column shifts.*

---

## 3. Branch Summary Table Styling

The main Branch Wise Lead Summary table renders:
- **9 Highlighted Columns:** `Branch`, `Total Leads`, `Meta WhatsApp`, `Meta Lead Form`, `Website (Google Ad)`, `Website (Google SEO)`, `Instagram`, `Google Calls`, `Influencer`
- **3 Normal Status Columns:** `New Leads`, `Existing Leads`, `Missed Leads`

---

## 4. Project Files

- `index.html` – Main dashboard view
- `css/dashboard.css` – Visual styles and pastel highlight column formatting
- `css/responsive.css` – Mobile and tablet responsive grid rules
- `js/config.js` – Centralized branch configuration, spreadsheet ID, channel list, and polling interval
- `js/store.js` – Robust Google Sheets CSV fetcher, date parser, and multi-tab aggregator with partial-failure resilience
- `js/api.js` – In-browser KPI, branch distribution, channel aggregation, and filter engine
- `js/charts.js` – Chart.js renderers (Leads by Channel Donut, Branch Wise Stacked Bars, and Call Outcomes)
- `js/filters.js` – Date, branch, and channel filter state management
- `js/dropdown.js` – Accessible, centered custom dropdown pills
- `js/dashboard.js` – Main orchestrator, DOM bindings, and live sync management
- `tests/test-suite.js` – Automated test suite verifying all 14 problem statements

---

## 5. Running & Testing Locally

### Direct Browser Usage
Double-click `index.html` or open it in Google Chrome, Microsoft Edge, Mozilla Firefox, or Safari.

### Running Automated Verification Tests
Run the deterministic test suite via Node.js:
```bash
node tests/test-suite.js
```
