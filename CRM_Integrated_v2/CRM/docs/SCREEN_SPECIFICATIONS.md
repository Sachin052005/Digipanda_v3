# Screen-by-Screen UI/UX Specifications

## 1. Global Shell & Navigation
- **Template**: `CRM/templates/base.html`
- **Sidebar**:
  - Frosted glass rail (`rgba(14, 20, 34, 0.95)` in dark, `rgba(255, 255, 255, 0.96)` in light).
  - Brand logo with glowing hexagonal emblem (`TECHPANDA`).
  - Active navigation pill: Electric indigo gradient with left laser beacon indicator (`border-left: 3px solid #38bdf8`) and illuminated text.
  - Collapsible groups: Smooth accordion chevron rotation with spring easing.
- **Top Command Bar**:
  - Quick Search Palette trigger (`Ctrl+K` cyber-pill).
  - Live Center / Branch selector dropdown with glassmorphism popper.
  - Dark / Light mode toggle with smooth rotation animation.
  - Telephony status beacon (green dot pulsing with `beaconPulse`).

---

## 2. All Leads CRM & Pipeline
- **Templates**: `CRM/templates/admin/leads_list.html`, `CRM/templates/leads/kanban.html`
- **Header**:
  - Holographic title group with live lead count badges.
  - Action row: Button group with `.btn-primary` ("+ Add Lead"), `.btn-secondary` ("Duplicates", "Enrolled Students"), and Table/Kanban view switcher pill.
- **Filter Drawer**:
  - Cyber drawer gliding in from left with glass overlay.
  - Condition rows with quick-remove tags and instant count updates.
- **Table View**:
  - Sticky header with laser divider.
  - Monospace lead tokens (`[LD-10492]`).
  - Pulsing status pills (Interested, Contacted, Followup, Joined, Lost).
  - Quick action pills: Instant WhatsApp chat trigger (emerald pill), Call trigger (cyan pill), and Dossier drawer view.

---

## 3. Walk-in Reception Desk & QR Studio
- **Templates**: `CRM/templates/admin/walkin_desk.html`, `CRM/templates/admin/walkin_forms_list.html`, `CRM/templates/admin/walkin_form_editor.html`, `CRM/templates/public/student_enquiry_form.html`
- **Reception Radar**:
  - Animated top laser bar with `headerLaser`.
  - Date range segmented switchers with tactile pills.
  - Real-time visitor queue cards with pulsing avatar status LEDs (Crimson = Waiting, Amber = In Consultation, Emerald = Completed).
- **Visual Studio Editor**:
  - Two-column cyber studio: Visual field builder on left, interactive 3D phone mockup on right.
  - Live simulator instantly updating brand logo image, brand name, form title, and subtitle as the admin types.
  - Top bar with theme color picker dot and Ctrl+S hotkey save listener.
- **Public Kiosk Form**:
  - Cosmic aurora background with glassmorphism form card.
  - Dynamic brand header rendering uploaded logo image or customized brand icon.
  - Animated laser sweep submit button with tactile click feedback.

---

## 4. WhatsApp Automation & Flow Builder
- **Templates**: `CRM/templates/automation/automation_list.html`, `CRM/templates/automation/flow_builder.html`
- **Automation Canvas**:
  - Dark grid canvas with subtle dot matrix.
  - Node cards with glowing header bars matching node type (Trigger = Violet, Message = Emerald, Condition = Cyan, Branch = Amber).
  - Animated connector lines with flowing signal particles.
  - Interactive test simulator modal mimicking WhatsApp chat with instant state replay.

---

## 5. Reports & Analytics
- **Templates**: `CRM/templates/reports/admin_reports.html`, `CRM/templates/reports/dashboard_report.html`
- **KPI Pods**:
  - Top laser beam accent lines.
  - Large monospace metric figures with gradient text fill.
  - Trend comparison pills with directional neon arrows (▲ +14% Emerald, ▼ -3% Crimson).
- **Interactive Charts**:
  - Chart.js initialized with custom glossy neon theme (`chart-theme.js`).
  - Glowing gridlines and transparent area gradients.
