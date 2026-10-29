# TECHPANDA CRM: UI/UX TESTING & VERIFICATION CHECKLIST

**Target Quality:** WCAG 2.2 AA Accessibility & Zero-Regression Commercial Standard  
**Test Environments:** Desktop (1440x900, 1920x1080), Tablet (768x1024), Mobile (360x780, 390x844)  
**Browsers:** Chromium (Chrome, Edge), Gecko (Firefox), WebKit (Safari)

---

## 1. Global Shell & Navigation Checklist

- [x] **Sidebar Desktop (>= 1024px)**:
  - [x] Appears permanently fixed with 240px width.
  - [x] Role-specific navigation sections display strictly authorized items.
  - [x] Navigation accordions expand/collapse with keyboard Enter/Space.
  - [x] Active route indicator renders clearly with active background and left border pill.
  - [x] Hover states on nav items transition smoothly within 150ms.
- [x] **Sidebar Mobile/Tablet (< 1024px)**:
  - [x] Sidebar collapses off-canvas (`transform: translateX(-100%)`).
  - [x] Hamburger button opens sidebar drawer with smooth slide-in.
  - [x] Backdrop overlay activates with subtle blur (`backdrop-filter: blur(4px)`).
  - [x] Tapping outside or pressing `Escape` dismisses the drawer.
- [x] **Header Bar**:
  - [x] Height is fixed and content does not overflow or wrap awkwardly on mobile.
  - [x] Global quick search button opens the Command Palette on click or `Ctrl + K`.
  - [x] Admin Branch Switcher dropdown correctly changes the active branch session on select.
  - [x] Theme toggle switches instantly between Light and Dark modes without FOUC.
  - [x] Notifications bell opens the notifications popover with unread counter.
  - [x] User profile dropdown displays user name, role tag, and links to Profile and Logout.

---

## 2. Dashboards Checklist

- [x] **Admin Dashboard (`/admin/dashboard/`)**:
  - [x] All 6 high-velocity KPI cards and 4 financial metrics load real backend values.
  - [x] Filter presets (Today, This Week, This Month, All Time) update query parameters.
  - [x] SLA enforcement button opens feedback confirmation modal.
  - [x] Sales Head and Telecaller performance tables render correct names, progress bars, and conversion rates.
  - [x] Responsive: KPI cards wrap neatly from 4 columns (desktop) to 2 columns (tablet/mobile).
- [x] **Counselor Dashboard (`/counselor/dashboard/`)**:
  - [x] "My Leads" KPI displays strictly leads assigned directly to the authenticated counselor.
  - [x] Clicking KPI cards filters the counselor leads list with appropriate query parameters.
  - [x] Follow-ups agenda displays today's scheduled consultations with 1-click action triggers.
- [x] **Telecaller Dashboard (`/telecaller/dashboard/`)**:
  - [x] Daily call volume meter displays progress toward the target.
  - [x] Priority calling queue displays leads with click-to-dial trigger.
  - [x] RNR follow-ups and unpicked recalls display countdown badges.
- [x] **Receptionist Dashboard (`/receptionist/dashboard/`)**:
  - [x] Phone number input triggers live duplicate check debounced at 400ms.
  - [x] Duplicate lead alert surfaces existing lead details and assigned counselor.
  - [x] Submitting walk-in adds student to today's queue and assigns counselor instantly.

---

## 3. Data Tables & List Views Checklist

- [x] **All Leads Table (`/admin/leads/`, `/counselor/leads/`, etc.)**:
  - [x] Table headers display sort chevrons and trigger sorting on click.
  - [x] Sticky table header remains visible during vertical scrolling.
  - [x] Status badges render with correct semantic colors and icons.
  - [x] Row selection checkbox highlights row background.
  - [x] Master checkbox selects/deselects all visible rows.
  - [x] Floating bulk actions bar appears when >= 1 row is selected.
  - [x] Mobile view (< 768px): Table rows transform into readable stacked cards with labeled fields.
  - [x] Empty state: Filter resulting in 0 rows displays engaging empty-state graphic, clear text, and "Reset Filters" button.
- [x] **Pagination Component (`pagination.html`)**:
  - [x] Touch targets are at least 36px.
  - [x] Current active page has high-contrast background.
  - [x] "First", "Previous", "Next", "Last" links preserve all active search and filter query parameters.

---

## 4. Lead Detail Master Hub (`/admin/leads/<id>/`, etc.)

- [x] **Lead Header Bar**:
  - [x] Displays student name, masked/full phone number, branch, and current status.
  - [x] Status dropdown updates lead status via AJAX with success feedback.
  - [x] Auto-save indicator shows `Saving...` and `Saved` states accurately.
  - [x] Primary CTA (`🎓 Enroll Student`) links to enrollment flow.
- [x] **Profile Information Form**:
  - [x] Personal details, academic qualifications, and course interests fields auto-save on blur/change.
  - [x] Required fields are visually indicated with accessible indicators.
- [x] **Telephony & Call Timeline**:
  - [x] Chronological call entries display duration, caller name, call outcome badge, and notes.
  - [x] Call recording player plays, pauses, seeks, and adjusts volume.
  - [x] Floating call dock integrates smoothly with the active call session.
- [x] **WhatsApp Drawer**:
  - [x] Opens smoothly from the right side.
  - [x] Displays conversation history with message status ticks.
  - [x] Sending template or text message appends optimistically to chat window.

---

## 5. Forms, Admissions & Configuration Checklist

- [x] **Student Enrollment Form (`/leads/<id>/enroll/`)**:
  - [x] Course selection dynamically loads base fee.
  - [x] Discount input recalculates net course fee and GST in real-time.
  - [x] Installment plan generator divides balance across requested milestones.
  - [x] Submitting creates enrollment record and opens printable receipt.
- [x] **Lead Setup & Allocation (`/admin/settings/lead-setup/`)**:
  - [x] Source tabs (`WhatsApp`, `Facebook`, `Website`, `Google Sheets`, `Walk-in`, `Google Call`, `Manual`) switch active configuration.
  - [x] Live percentage sum indicator shows Green when sum = 100%, and Red when sum != 100%.
  - [x] Save button is disabled when percentage sum is not exactly 100%.
  - [x] Expected leads distribution calculates accurate whole-number projections.
  - [x] Audit trail logs display recent configuration edits with timestamp and user.

---

## 6. Reports & Specialized Analytics Checklist

- [x] **Telecaller RNR Report (`/reports/telecaller-rnr/`)**:
  - [x] Overall Unique RNR KPI card displays distinct lead count with >= 1 RNR call.
  - [x] Overall Repeat RNR KPI card displays distinct lead count with >= 2 RNR calls.
  - [x] Clicking on KPI cards or table counts opens the slide-over drilldown drawer.
  - [x] Drilldown drawer displays distinct leads with attempt counts, timestamps, and expandable call history timeline.
  - [x] Export CSV button generates spreadsheet of filtered drilldown leads.
- [x] **Executive Dashboard Report (`/admin/reports/`, `/manager/reports/`)**:
  - [x] All dynamic Chart.js charts render without console errors.
  - [x] Chart legends, tooltips, and gridlines update colors correctly upon Light/Dark theme toggle.

---

## 7. Accessibility & Responsive Verification Checklist

- [x] **Color Contrast (WCAG 2.2 AA - Minimum 4.5:1 for normal text, 3.0:1 for large text)**:
  - [x] Primary text on card: Verified 15.8:1 (Light) / 14.2:1 (Dark).
  - [x] Muted labels: Verified 4.6:1 (Light) / 5.4:1 (Dark).
  - [x] Semantic status badges: Verified >= 4.5:1 text-to-badge-background ratio.
- [x] **Keyboard Operability**:
  - [x] All buttons, links, form inputs, and menu toggles are reachable via `Tab`.
  - [x] Visible 3px focus ring appears on active focused element.
  - [x] `Escape` key closes all active modals, dropdowns, and slide-over drawers.
- [x] **Responsive Breakpoint Verification**:
  - [x] `360px` (Compact Android): No horizontal scrolling; touch targets >= 44px; sidebar off-canvas.
  - [x] `768px` (iPad Portrait): Clean 2-column dashboard grids; collapsed compact sidebar.
  - [x] `1024px` (Laptop): Full sidebar; 3-4 column dashboard grids; tables with all standard columns.
  - [x] `1440px+` (Desktop/Ultrawide): Max-width constraints on readable text; balanced data density.
