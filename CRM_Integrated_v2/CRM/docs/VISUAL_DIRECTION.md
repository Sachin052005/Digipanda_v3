# Visual Direction: Futuristic Cyber-Minimalism & Neo-Glassmorphism

## 1. Aesthetic Thesis & Mood
TECHPANDA CRM is designed as a mission-control cockpit for enterprise education sales, admissions, and omnichannel automation. The aesthetic is **Futuristic Cyber-Minimalism & Neo-Glassmorphism**:
- **Precise & High-Tech**: Monospace tokens, illuminated status beacons, laser top-bars, and crisp typography.
- **Dimensional & Layered**: Translucent frosted surfaces (`backdrop-filter: blur(16px)`), subtle specular highlights on top edges, and deep ambient drop shadows.
- **Dynamic & Tactile**: Smooth spring physics (`cubic-bezier(0.16, 1, 0.3, 1)`), animated laser sweeps across active/primary buttons, and responsive micro-scaling upon click.

---

## 2. Color Palette & Emissive Accents

### 2.1 Core Chromatic System
- **Deep Space Obsidian (Dark Canvas)**: `#080c15` (Viewport Background), `#0e1422` (Card Surface), `#162035` (Hover Surface).
- **Polar Glass (Light Canvas)**: `#f8fafc` (Viewport Background), `#ffffff` (Card Surface), `#f1f5f9` (Hover Surface).
- **Electric Indigo (Primary Brand)**:
  - Base: `#4f46e5`
  - Neon Core: `#6366f1`
  - Deep Glow: `rgba(99, 102, 241, 0.35)`
- **Cyber Cyan (Secondary / Telephony / Focus)**:
  - Base: `#06b6d4`
  - Neon Core: `#38bdf8`
  - Focus Ring: `#0ea5e9`
- **Neon Emerald (Success / Live Engine / Active Leads)**:
  - Base: `#10b981`
  - Neon Core: `#34d399`
  - Beacon Glow: `rgba(16, 185, 129, 0.4)`
- **Radiant Amber (Waiting / Follow-up / Warning)**:
  - Base: `#f59e0b`
  - Neon Core: `#fbbf24`
  - Warning Halo: `rgba(245, 158, 11, 0.35)`
- **Crimson Nova (Critical / Missed / Lost / Danger)**:
  - Base: `#ef4444`
  - Neon Core: `#f87171`
  - Danger Halo: `rgba(239, 68, 68, 0.4)`

---

## 3. Surface & Depth Architecture

### Tier 1 — Viewport Void (`z-index: 0`)
- The base application background featuring subtle ambient aurora gradients in dark mode and ultra-clean neutral slate in light mode.

### Tier 2 — Frosted Glass Shell (`z-index: 10`)
- Sidebar and Topbar Navigation panels with `backdrop-filter: blur(16px)`, `rgba(14, 20, 34, 0.85)` in dark and `rgba(255, 255, 255, 0.88)` in light, bounded by 1px subtle glass borders.

### Tier 3 — Elevated HUD Cards & Modules (`z-index: 20`)
- KPI metrics, table containers, and studio panels with top specular highlights (`inset 0 1px 0 rgba(255, 255, 255, 0.15)`), rounded corners (`16px`), and smooth `-2px` hover lift with soft shadow bloom.

### Tier 4 — Interactive Controls & Overlays (`z-index: 50+`)
- Tactile holographic buttons, filter drawers, command palettes, and telephony floating docks with high-contrast elevation and laser accent borders.

---

## 4. Typography Scale
- **Display & Section Titles**: `Plus Jakarta Sans` or `Inter`, font weight 800, tight letter-spacing (`-0.03em`).
- **Body & Data Labels**: `Inter`, font weight 500-600, optimal line-height (`1.5`).
- **Telemetry, Tokens & IDs**: Monospace (`ui-monospace`, `JetBrains Mono`, `Consolas`), font weight 700, letter spacing (`0.05em`).
