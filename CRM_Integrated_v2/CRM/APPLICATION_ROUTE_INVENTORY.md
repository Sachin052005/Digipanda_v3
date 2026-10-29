# TECHPANDA CRM: APPLICATION ROUTE INVENTORY & DESIGN SPECIFICATION

**Application:** TechPanda CRM (Django)  
**Total Routes Cataloged:** 440+ endpoints (Core Web UI Screens, Modals, APIs, Webhooks, and Django Admin)  
**Architecture:** Django Model-View-Template (MVT) with Django Channels (WebSockets) and REST APIs

---

## SECTION 1: AUTHENTICATION & ACCOUNT ACCESS

### 1.1 General Login (`login`)
- **Route:** `/login/` (name: `login`)
- **Purpose:** Central authentication portal for all CRM staff roles with role-based dashboard redirection.
- **Roles:** Anonymous / Unauthenticated visitors.
- **Existing Page Structure:** `templates/registration/login.html` — Card container with TechPanda logo, username input, password input, remember me checkbox, submit button, and password reset link.
- **Available Actions:** Enter credentials, toggle password visibility, submit login, navigate to password recovery.
- **Data & Dependencies:** Django `django.contrib.auth.views.LoginView` / `accounts.views.general_login`, `User` model, CSRF token.
- **Usability Problems:** Missing branded hero illustration or modern product showcase on desktop split screen; mobile view has unnecessary vertical margins.
- **Proposed New Layout:** Modern asymmetric split layout: Left brand showcase with subtle gradient mesh and security badges; right high-focus card with floating labels, keyboard Enter submission, and inline validation.
- **Responsive Requirements:** Mobile (360px–640px): Stack into a single high-focus centered card, hiding promotional side panel.
- **Testing Requirements:** Verify valid credentials redirect to role-specific dashboard; verify invalid credentials display accessible error banner; verify CSRF protection.

### 1.2 Dedicated Role Login Portals (`admin_login`, `manager_login`, `telecaller_login`, `receptionist_login`)
- **Routes:** `/admin/login/`, `/manager/login/`, `/telecaller/login/`, `/receptionist/login/`
- **Purpose:** Dedicated role login endpoints with pre-filtered role validation and dedicated entry contexts.
- **Roles:** Anonymous visitors of specific departments.
- **Existing Structure:** `templates/registration/*_login.html`.
- **Usability Problems:** Styling is duplicated across 4 distinct template files with slight class mismatches.
- **Proposed Layout:** Unified brand authentication layout sharing reusable form components and consistent design tokens.
- **Testing Requirements:** Verify role mismatch shows friendly error ("This account belongs to another department, redirecting...").

### 1.3 Password Recovery & Reset Flow (`password_reset`, `password_reset_confirm`, `account_setup`)
- **Routes:** `/password-reset/`, `/password-reset/done/`, `/password-reset-confirm/<uidb64>/<token>/`, `/accounts/setup/<uidb64>/<token>/`
- **Purpose:** Self-service password recovery and newly invited staff account activation with password setup.
- **Roles:** All staff members with valid email addresses.
- **Existing Structure:** `templates/registration/password_reset_*.html`, `account_setup.html`.
- **Usability Problems:** Password complexity requirements are not clearly visualized in real-time as the user types; error messages appear only after submission.
- **Proposed Layout:** Real-time password strength meter and interactive checklist (8+ chars, uppercase, lowercase, number, symbol), inline match indicator, and clean step-by-step progress.
- **Testing Requirements:** Verify token validation, expired token handling, password change confirmation, and automated login redirect.

---

## SECTION 2: EXECUTIVE & OPERATIONAL DASHBOARDS

### 2.1 Admin Dashboard (`admin_dashboard`)
- **Route:** `/admin/dashboard/`
- **Purpose:** Comprehensive enterprise intelligence hub for organizational KPI tracking, lead velocity, enrollment revenue, and SLA enforcement.
- **Roles:** `ADMIN`, `SUPERADMIN`.
- **Existing Structure:** `templates/admin_dashboard/dashboard.html` — Page header with SLA button, multi-select filter card (dates, sales head, telecaller, branch, channel, status), 6 high-velocity KPI cards, 4 financial cards, performance tables, recent activity logs.
- **Available Actions:** Filter by date/branch/manager, trigger SLA escalation API, drill into enrolled students, quick lead create, export metrics.
- **Data & Dependencies:** `reports.services.get_dashboard_report_data`, `Lead`, `Enrollment`, `Installment`, `CallHistory`.
- **Usability Problems:** Over 600 lines with heavy inline styles. 12+ KPI cards compete equally for visual attention. Filters form takes excessive vertical space.
- **Proposed New Layout:**
  - Executive Stat Ribbon: 4 Primary North-Star Metrics (Total Leads, Conversion Rate, Period Revenue, Escalation Alerts).
  - Collapsible Filter Toolbar with active filter chips.
  - Interactive Chart Grid (Lead Funnel, Channel Performance, Revenue vs Collections).
  - High-Velocity Operational Grid: Telecaller vs Counselor Performance leaderboard with conversion rates.
- **Responsive Requirements:** Mobile: KPIs stack into a 2x2 grid, tables convert to compact summary cards, charts maintain aspect ratio with horizontal scrolling for dense data.
- **Testing Requirements:** Verify date filters filter all cards and tables consistently; verify SLA button triggers modal feedback; verify zero-data branches render clean empty states.

### 2.2 Sales Head / Manager Dashboard (`manager_dashboard`)
- **Route:** `/manager/dashboard/`
- **Purpose:** Operational management dashboard for Sales Heads supervising multi-branch lead velocity and staff accountability.
- **Roles:** `SALES_HEAD` (`MANAGER`), `ADMIN`.
- **Existing Structure:** `templates/manager_dashboard/dashboard.html`.
- **Proposed Layout:** Team-centric layout highlighting pending follow-ups, overdue leads, counselor assignment ratios, and telecaller call performance.

### 2.3 Branch Head Dashboard (`branch_head_dashboard`)
- **Route:** `/manager/branch-head/dashboard/`
- **Purpose:** Branch floor operational dashboard scoped strictly to the authenticated user's branch.
- **Roles:** `BRANCH_HEAD`, `ADMIN`.
- **Existing Structure:** `templates/branch_head_dashboard/dashboard.html`.
- **Proposed Layout:** Branch-first metrics: Today's walk-ins, branch counselor capacity, telecaller connected call volume, and branch missed calls.

### 2.4 Counselor Workspace Dashboard (`counselor_dashboard`)
- **Route:** `/counselor/dashboard/`
- **Purpose:** Focused workspace for Student Counselors managing counseling sessions, campus visits, student enrollments, and pending follow-ups.
- **Roles:** `COUNSELOR`.
- **Existing Structure:** `templates/counselor_dashboard/dashboard.html` — Quick period bar, 5 clickable KPI cards (My Leads, Visits, Counseling, Pending Follow-ups, Enrolled), upcoming follow-ups list, recent lead activities.
- **Proposed Layout:**
  - "My Leads" authoritative ownership banner with quick search.
  - Today's Agenda: Follow-up schedule with time badges, 1-click call/WhatsApp actions.
  - Pipeline Progress: Visits scheduled vs completed, counseling in progress, enrolled conversion counter.
- **Testing Requirements:** Confirm "My Leads" KPI reflects strictly leads assigned directly to the logged-in counselor; confirm clicking cards filters lead list accurately.

### 2.5 Telecaller Workspace Dashboard (`telecaller_dashboard`)
- **Route:** `/telecaller/dashboard/`
- **Purpose:** High-velocity calling command center for telecallers executing daily outreach, lead qualification, and recall follow-ups.
- **Roles:** `TELECALLER`.
- **Existing Structure:** `templates/telecaller_dashboard/dashboard.html` — Period selector, KPI cards (My Leads, Calls Made, Connected, RNR, Pending Followups), Call queue table with click-to-dial.
- **Proposed Layout:**
  - Focused Calling Queue: Priority leads, overdue recalls, and fresh uncontacted leads.
  - Instant Call Logger: Persistent quick-dock trigger, disposition shortcuts (RNR, Interested, Demo, Lost).
  - Daily Performance Meter: Visual progress bar toward daily call target (e.g. 75/100 calls completed).

### 2.6 Receptionist Front-Desk Workspace (`receptionist_dashboard`)
- **Route:** `/receptionist/dashboard/`
- **Purpose:** Kiosk-grade student walk-in intake, instant phone duplication check, student registration, and branch counselor handoff.
- **Roles:** `RECEPTIONIST`, `ADMIN`.
- **Existing Structure:** `templates/receptionist/dashboard.html` — Real-time duplicate phone check, walk-in registration form, today's walk-in table with counselor assignment dropdown.
- **Proposed Layout:** Clean, distraction-free front desk interface: Left rapid intake form with real-time phone verification; right live visitor queue with counselor availability badges.

---

## SECTION 3: LEAD MANAGEMENT & PIPELINE

### 3.1 All Leads Master Table (`admin_leads_list`, `manager_leads_list`, `branch_head_leads_list`, `counselor_leads_list`, `telecaller_leads_list`)
- **Routes:** `/admin/leads/`, `/manager/leads/`, `/manager/branch-head/leads/`, `/counselor/leads/`, `/telecaller/leads/`
- **Purpose:** Core tabular lead management interface with multi-field search, advanced filtering, bulk selection, inline status update, and export.
- **Roles:** Role-scoped (Admin sees all; Counselor sees My Leads; Telecaller sees Assigned Leads; Branch Head sees Branch Leads).
- **Existing Structure:** `templates/admin/leads_list.html`, `templates/counselor/leads_list.html`, etc.
- **Available Actions:** Search, filter by status/channel/telecaller/counselor, sort by date/name/activity, bulk select, bulk edit, bulk WhatsApp message, export CSV, pagination.
- **Usability Problems:** Wide tables trigger horizontal overflow on tablets/laptops; action dropdown gets clipped by table container overflow; bulk actions bar lacks sticky positioning.
- **Proposed New Layout:**
  - Sticky Filter & View Control Bar with active filter tags and clear-all button.
  - Floating Bulk Actions Dock appearing dynamically upon row selection with batch count.
  - Responsive Table: High-priority columns (Name, Phone, Status, Assigned To, Activity) prioritized; secondary columns collapsible or hidden on mobile in favor of stacked card rows.
  - Status badges with distinct semantic icons and high-contrast colors.
- **Testing Requirements:** Verify role scoping; verify bulk edit modal executes without reload; verify CSV export filters match active query parameters.

### 3.2 Lead Detail Master Hub (`admin_lead_detail`, `manager_lead_detail`, `counselor_lead_detail`, `telecaller_lead_detail`)
- **Routes:** `/admin/leads/<id>/`, `/counselor/leads/<id>/`, `/telecaller/leads/<id>/`
- **Purpose:** Central 360-degree lead intelligence hub: Personal info, academic profile, course interests, call history with audio player, activity timeline, WhatsApp chat drawer, follow-up scheduling, and enrollment action.
- **Roles:** Authorized staff with access to the specific lead.
- **Existing Structure:** `templates/leads/lead_detail_view.html` (69KB) — 3-column layout: Left profile card & auto-save fields; center call dock & activity timeline; right follow-up scheduler & enrollment details.
- **Usability Problems:** Visual density is heavy; auto-save status indicator is inconspicuous; tab transitions can cause content jumping.
- **Proposed New Layout:**
  - Top Lead Header: Name, masked/full phone with 1-click dial, status pill dropdown, auto-save status badge (`Saved to cloud` / `Saving...`), primary CTA (`🎓 Enroll Student` or `⚡ Reassign`).
  - Organized Tabbed Sections:
    1. **Overview & Profile**: Form fields grouped cleanly into Personal, Academic, and Course Interests with auto-save feedback.
    2. **Call Records & Audio**: Chronological call logs with integrated audio waveforms, duration badges, and notes.
    3. **Activity Timeline**: Full historical audit trail (status changes, reassignments, WhatsApp events).
    4. **WhatsApp Communication**: Embedded chat history drawer with template triggers.
  - Sticky Quick Action Drawer on mobile.
- **Testing Requirements:** Verify inline auto-save field updates; verify audio playback; verify follow-up scheduling creates activity record; verify counselor reassignment permissions.

### 3.3 Visual Pipeline Kanban Board (`leads_kanban`)
- **Route:** `/leads/kanban/`
- **Purpose:** Interactive drag-and-drop visual pipeline organized across lead stages (New, Contacted, Interested, Demo Scheduled, Visited, Counseling, Joined, Lost).
- **Roles:** All operational roles (scoped to accessible leads).
- **Existing Structure:** `templates/leads/kanban.html` — Columns with lead cards, drag-and-drop listeners, status update endpoint.
- **Usability Problems:** Horizontal scrollbar is unstyled; drag ghost preview is hard to see in dark mode; column headers lack lead volume totals and conversion ratios.
- **Proposed New Layout:** Polished Trello/Jira-style board with smooth column scrolling, sticky column headers with count badges, rich lead cards (name, phone, course badge, days stagnant counter, assigned avatar), and smooth drag-drop animations with accessible keyboard move fallback.
- **Testing Requirements:** Dragging a card updates status via AJAX; column counters update optimistically; unauthorized moves revert with error toast.

### 3.4 Lead Creation & Import (`admin_lead_create`, `admin_leads_import`)
- **Routes:** `/admin/leads/create/`, `/admin/leads/import/`
- **Purpose:** Manual single lead creation and bulk CSV/Excel lead ingestion with column mapping.
- **Proposed Layout:** Clean card form with field validation; CSV importer with file drag-and-drop zone, live row preview, column mapping selectors, and error summary report.

---

## SECTION 4: TELEPHONY, CALL DOCK, AUDIO RECORDINGS & MISSED CALLS

### 4.1 Missed Calls Center (`missed_calls_list`)
- **Route:** `/calls/missed/`
- **Purpose:** Central queue for incoming calls not answered by telecallers, requiring urgent callback SLA adherence.
- **Roles:** Admin, Manager, Branch Head, Counselor, Telecaller.
- **Existing Structure:** `templates/calls/missed_calls_list.html`.
- **Proposed Layout:** Priority alert table with countdown timer since missed call, 1-click callback trigger, and "Mark Handled" disposition modal.

### 4.2 Call Recordings & Audio Player (`call_recordings_list`, `drive_dashboard`)
- **Routes:** `/drive/recordings/`, `/call-recordings/`
- **Purpose:** Audit and playback repository for all synchronized phone call recordings.
- **Existing Structure:** `templates/calls/recordings_list.html` — Table with audio element or custom waveform player.
- **Proposed Layout:** Media-rich recording browser with inline waveform audio player, playback speed toggle (1x, 1.25x, 1.5x, 2x), volume slider, telecaller/lead filter, and download action.

---

## SECTION 5: STUDENT ADMISSIONS, ENROLLMENTS & BILLING

### 5.1 Student Enrollment Form (`lead_enroll`)
- **Route:** `/leads/<id>/enroll/`
- **Purpose:** Formal conversion workflow transforming a prospective lead into an enrolled student with course selection, fee calculation, discount approval, GST breakdown, and installment schedule.
- **Existing Structure:** `templates/leads/enrollment_form.html`.
- **Proposed Layout:** Multi-step guided checkout flow:
  1. Student & Course Details
  2. Pricing, Discount & GST Calculation (Live summary sidebar)
  3. Installment Plan Scheduler (Downpayment + due dates)
  4. Confirmation & Instant Receipt Generation

### 5.2 Enrolled Students Directory (`admin_enrolled_students`, `counselor_enrolled_students`)
- **Routes:** `/admin/enrolled-students/`, `/counselor/enrolled-students/`
- **Purpose:** Directory of joined students, payment statuses, outstanding balances, and installment collections.
- **Existing Structure:** `templates/leads/enrolled_students.html`.
- **Proposed Layout:** Financial dashboard table with payment health indicators (Fully Paid, Active Installments, Overdue), student search, and 1-click payment recording.

### 5.3 Payment Receipt & Invoicing (`enrollment_receipt_view`, `enrollment_receipt_pdf_view`)
- **Routes:** `/enrollments/receipt/<transaction_id>/`, `/enrollments/receipt/<transaction_id>/pdf/`
- **Purpose:** Professional commercial student invoice/receipt with printable layout and PDF download.
- **Existing Structure:** `templates/leads/receipt.html`, `receipt_pdf.html`.
- **Proposed Layout:** Clean, typography-driven commercial invoice suitable for printing and PDF generation with institution logo, student credentials, transaction ID, GST breakdown, and authorized signature stamp.

---

## SECTION 6: REPORTS, ANALYTICS & EXECUTIVE INTELLIGENCE

### 6.1 Telecaller RNR Report & Drilldown Drawer (`telecaller_rnr_report`, `telecaller_rnr_lead_drilldown`)
- **Routes:** `/reports/telecaller-rnr/`, `/reports/telecaller-rnr/leads/`
- **Purpose:** Telephony performance report tracking Ringing No Response (RNR) calls, unique RNR leads, repeat RNR leads (>=2 attempts), and slide-over lead history drilldown.
- **Existing Structure:** `templates/reports/telecaller_rnr_report.html`.
- **Proposed Layout:**
  - Modern Summary Card Bar (Overall Calls, Connected Calls, Unique RNR, Repeat RNR, Avg Attempts).
  - Telecaller Comparison Table with connection rate progress bars.
  - Interactive Slide-over Drawer with distinct lead search, call timeline, and CSV export.

### 6.2 Executive Dashboard Report (`admin_reports`, `reports_api_data`)
- **Route:** `/admin/reports/`
- **Purpose:** Executive analytics with 10 dynamic charts, marketing channel attribution, conversion funnel, and period comparisons.
- **Existing Structure:** `templates/reports/dashboard_report.html`, `admin_reports.html`.
- **Proposed Layout:** Clean executive dashboard layout with synchronized Chart.js theme colors, channel ROI badges, and exportable data tables.

---

## SECTION 7: STAFF, BRANCHES & CONFIGURATION

### 7.1 Staff Directories (`admin_managers_list`, `admin_branch_heads_list`, `admin_counselors_list`, `admin_telecallers_list`, `admin_receptionists_list`)
- **Routes:** `/admin/managers/`, `/admin/branch-heads/`, `/admin/counselors/`, `/admin/telecallers/`, `/admin/receptionists/`
- **Purpose:** Team directories for managing staff profiles, branch assignments, active/inactive statuses, and password management.
- **Proposed Layout:** Clean team directory with role badges, branch tags, assigned lead counts, status toggles, and user action menus (Edit, Set Password, Reset Link, Toggle Active).

### 7.2 Lead Allocation & Setup Hub (`admin_lead_setup`)
- **Route:** `/admin/settings/lead-setup/`
- **Purpose:** Hierarchical Branch $\rightarrow$ Lead Source $\rightarrow$ Telecaller percentage distribution configuration with strict 100% validation, expected lead calculations, and audit history.
- **Existing Structure:** `templates/admin/lead_setup.html`.
- **Proposed Layout:** Tabbed source navigation bar (`WhatsApp`, `Facebook`, `Website`, `Google Sheets`, `Walk-in`, `Google Call`, `Manual`), live percentage sum meter (Green at 100%), telecaller allocation sliders/inputs, expected leads counter, and expandable audit trail table.

---

## SECTION 8: OMNICHANNEL COMMS (WHATSAPP & FACEBOOK)

### 8.1 WhatsApp CRM Inbox (`inbox`, `whatsapp_inbox`)
- **Route:** `/whatsapp/`
- **Purpose:** Real-time multi-agent WhatsApp conversation hub for incoming and outgoing student chats.
- **Roles:** `ADMIN`, `SUPERADMIN` (Strictly restricted).
- **Existing Structure:** `chat/templates/chat/inbox.html`.
- **Proposed Layout:** Modern 3-pane messaging interface: Conversation list with unread badges $\rightarrow$ Active chat window with message bubbles, media attachments, and template selector $\rightarrow$ Right lead contextual sidebar.

### 8.2 WhatsApp Campaigns & Automations (`whatsapp_campaigns_list`, `automation-list`, `flow-builder`)
- **Routes:** `/campaigns/`, `/automations/`, `/automation/`
- **Purpose:** WhatsApp broadcast campaigns, delivery analytics, and visual trigger automation builder.
- **Roles:** `ADMIN`, `SUPERADMIN`.
- **Proposed Layout:** Campaign manager with delivery rate charts, recipient status badges, and intuitive flow card builders.
