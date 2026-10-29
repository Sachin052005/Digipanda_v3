# TECHPANDA CRM: COMPREHENSIVE DESIGN SYSTEM & DESIGN DIRECTION SPECIFICATION

**Application:** TechPanda CRM  
**Target Audience:** Education Sales Leaders, Branch Managers, Admissions Counselors, Telecalling Agents, Front Desk Staff  
**Design System Name:** **AURA Enterprise Design System** (Adaptive Unified Responsive Architecture)

---

## 1. Evaluation of Visual Directions

Before finalizing the visual identity, three distinct design directions were evaluated against TechPanda's product requirements: high-density tabular data, telephony workflows, real-time messaging, multi-role access, and high-frequency daily use.

### Direction 1: "Executive Horizon" (Selected & Implemented)
- **Visual Personality:** Authoritative, sophisticated, structured, calm, high-efficiency enterprise SaaS. Evokes precision and trust reminiscent of Stripe Dashboard, Linear, and modern Datadog.
- **Color Palette:** Deep Obsidian & Slate neutrals (`#090d16`, `#0f172a`, `#1e293b`), Royal Indigo primary brand (`#4f46e5`, `#6366f1`), crisp emerald successes (`#10b981`), amber warnings (`#f59e0b`), and crimson alerts (`#ef4444`).
- **Typography:** Inter with tabular figures (`tnum`) for numeric alignment, strict font-weight hierarchy (400, 500, 600, 700, 800), and balanced line heights.
- **Layout Principles:** Structured 8px spatial grid, high-density content cards with subtle 1px border delineation, fixed-header data tables with horizontal scroll indicators, and distinct status ribbons.
- **Navigation Style:** Refined collapsible sidebar with icon badges, category headers, active pill indicators, and a floating global search trigger (Ctrl + K).
- **Component Appearance:** 8px–10px border radius, subtle micro-shadows, zero decorative gradients, high-contrast hover lifts, and distinct `:focus-visible` rings.
- **Data Visualization:** Clean Chart.js palette with translucent fills, smooth curved line strokes, and high-contrast tooltip callouts.
- **Accessibility:** WCAG 2.2 AA compliant. High contrast ratios (5.0+:1 for normal text, 7.0+:1 for headings), clear focus rings, and multi-modal status indicators (color + icon + text).
- **Why Selected:** It provides the perfect balance between high-density operational utility (needed by telecallers and counselors handling hundreds of leads) and polished executive elegance (needed by sales heads and branch managers reviewing revenue and conversion metrics).

---

### Direction 2: "Neo-Fintech Minimalist" (Evaluated)
- **Visual Personality:** Stark, monochrome-heavy, ultra-clean, minimal surface elevation.
- **Color Palette:** Pure white, pure black (`#000000`), cool grays, single electric cyan accent (`#06b6d4`).
- **Typography:** Geist / JetBrains Mono accents, oversized numeric displays.
- **Layout Principles:** Cardless lists separated purely by 1px hairline dividers; generous white space.
- **Trade-offs:** While visually striking for simple consumer finance apps, generous white space severely reduces information density, forcing CRM users to scroll excessively to review student inquiries and call logs. Lacks warm, reassuring tones needed in education counseling.

---

### Direction 3: "Vibrant Velocity" (Evaluated)
- **Visual Personality:** Playful, rounded, consumer-tech inspired, vibrant gradient fills.
- **Color Palette:** Bright blue (`#2563eb`), purple gradients (`#8b5cf6` to `#ec4899`), pastel pill badges.
- **Layout Principles:** Large 16px–20px rounded cards, floating pills, prominent glassmorphism backdrops.
- **Trade-offs:** Heavy glassmorphism and large border radiuses degrade data table readability and introduce GPU rendering penalties on low-end telecaller laptops. Feels too casual for institutional admissions and financial installment tracking.

---

## 2. AURA Design Tokens Architecture

The design tokens are unified across both `:root` (Light Theme) and `[data-theme="dark"]` (Dark Theme) into a single, cohesive namespace. All legacy token collisions (e.g. `--primary` vs `--tp-primary-600`) are harmonized.

```css
/* =====================================================================
   AURA DESIGN SYSTEM - GLOBAL TOKENS
   ===================================================================== */
:root {
  /* Brand Primary Palette (Royal Indigo & Enterprise Blue) */
  --tp-primary-50: #eef2ff;
  --tp-primary-100: #e0e7ff;
  --tp-primary-200: #c7d2fe;
  --tp-primary-300: #a5b4fc;
  --tp-primary-400: #818cf8;
  --tp-primary-500: #6366f1;
  --tp-primary-600: #4f46e5; /* Authoritative Brand Primary */
  --tp-primary-700: #4338ca;
  --tp-primary-800: #3730a3;
  --tp-primary-900: #312e81;

  /* Backward Compatibility Aliases */
  --primary: var(--tp-primary-600);
  --primary-hover: var(--tp-primary-700);
  --primary-light: var(--tp-primary-50);

  /* Surface & Canvas (Light Theme) */
  --tp-canvas-bg: #f8fafc;        /* Body canvas */
  --tp-surface-card: #ffffff;      /* High-level cards */
  --tp-surface-card-hover: #f1f5f9;/* Table hover & card hover */
  --tp-surface-subtle: #f1f5f9;    /* Filter bars & search input */
  --tp-surface-border: #e2e8f0;    /* Card & input borders */
  --tp-surface-border-subtle: #edf2f7;

  /* Backward Compatibility Aliases */
  --bg-body: var(--tp-canvas-bg);
  --bg-card: var(--tp-surface-card);
  --border-color: var(--tp-surface-border);

  /* Typography Colors (High Contrast Light Mode) */
  --tp-text-primary: #0f172a;      /* 15.8:1 contrast on white */
  --tp-text-secondary: #334155;    /* 9.6:1 contrast on white */
  --tp-text-muted: #64748b;        /* 4.6:1 contrast on white (WCAG AA pass) */
  --tp-text-subtle: #94a3b8;       /* Placeholders and minor icons */
  --tp-text-inverse: #ffffff;

  /* Backward Compatibility Aliases */
  --text-main: var(--tp-text-primary);
  --text-muted: var(--tp-text-muted);
  --text-subtle: var(--tp-text-subtle);

  /* Navigation Sidebar Tokens (Deep Obsidian Navy) */
  --tp-sidebar-bg: #0b1120;
  --tp-sidebar-border: #1e293b;
  --tp-sidebar-text: #94a3b8;
  --tp-sidebar-text-hover: #e2e8f0;
  --tp-sidebar-active-bg: rgba(99, 102, 241, 0.12);
  --tp-sidebar-active-text: #ffffff;
  --tp-sidebar-active-bar: #6366f1;

  /* Backward Compatibility Aliases */
  --bg-sidebar: var(--tp-sidebar-bg);
  --text-sidebar: var(--tp-sidebar-text);
  --text-sidebar-active: var(--tp-sidebar-active-text);

  /* Functional Semantic Statuses */
  --tp-success-bg: #ecfdf5;
  --tp-success-border: #a7f3d0;
  --tp-success-text: #065f46;
  --tp-success-main: #10b981;

  --tp-warning-bg: #fffbeb;
  --tp-warning-border: #fde68a;
  --tp-warning-text: #92400e;
  --tp-warning-main: #f59e0b;

  --tp-danger-bg: #fef2f2;
  --tp-danger-border: #fecaca;
  --tp-danger-text: #991b1b;
  --tp-danger-main: #ef4444;

  --tp-info-bg: #eff6ff;
  --tp-info-border: #bfdbfe;
  --tp-info-text: #1e40af;
  --tp-info-main: #3b82f6;

  /* Shadows & Elevation */
  --tp-shadow-xs: 0 1px 2px 0 rgba(15, 23, 42, 0.04);
  --tp-shadow-sm: 0 1px 3px 0 rgba(15, 23, 42, 0.06), 0 1px 2px -1px rgba(15, 23, 42, 0.04);
  --tp-shadow-md: 0 4px 6px -1px rgba(15, 23, 42, 0.08), 0 2px 4px -2px rgba(15, 23, 42, 0.04);
  --tp-shadow-lg: 0 10px 15px -3px rgba(15, 23, 42, 0.08), 0 4px 6px -4px rgba(15, 23, 42, 0.04);
  --tp-shadow-xl: 0 20px 25px -5px rgba(15, 23, 42, 0.1), 0 8px 10px -6px rgba(15, 23, 42, 0.05);
  --tp-shadow-dropdown: 0 12px 28px -4px rgba(15, 23, 42, 0.15), 0 4px 8px -2px rgba(15, 23, 42, 0.06);

  /* Geometry & Spacing Grid (4px / 8px Base Scale) */
  --tp-space-1: 4px;
  --tp-space-2: 8px;
  --tp-space-3: 12px;
  --tp-space-4: 16px;
  --tp-space-5: 20px;
  --tp-space-6: 24px;
  --tp-space-8: 32px;
  --tp-space-10: 40px;
  --tp-space-12: 48px;

  /* Border Radii */
  --tp-radius-xs: 4px;
  --tp-radius-sm: 6px;
  --tp-radius-md: 8px;
  --tp-radius-lg: 12px;
  --tp-radius-xl: 16px;
  --tp-radius-full: 9999px;

  /* Accessibility Focus Rings */
  --tp-focus-ring: 0 0 0 3px rgba(99, 102, 241, 0.35);
  --tp-focus-ring-error: 0 0 0 3px rgba(239, 68, 68, 0.35);

  /* Motion & Transitions */
  --tp-ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --tp-ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
  --tp-duration-fast: 150ms;
  --tp-duration-normal: 220ms;
  --tp-duration-slow: 320ms;
}

/* =====================================================================
   DARK THEME TOKENS
   ===================================================================== */
[data-theme="dark"] {
  --tp-canvas-bg: #090d16;
  --tp-surface-card: #131b2e;
  --tp-surface-card-hover: #1b263e;
  --tp-surface-subtle: #162035;
  --tp-surface-border: #1e2c47;
  --tp-surface-border-subtle: #192338;

  --tp-text-primary: #f8fafc;
  --tp-text-secondary: #cbd5e1;
  --tp-text-muted: #94a3b8;
  --tp-text-subtle: #64748b;

  --tp-sidebar-bg: #070a12;
  --tp-sidebar-border: #151d2f;

  --tp-shadow-sm: 0 1px 3px 0 rgba(0, 0, 0, 0.4);
  --tp-shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.5);
  --tp-shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.6);
  --tp-shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.7);
  --tp-shadow-dropdown: 0 14px 32px -4px rgba(0, 0, 0, 0.75);

  --tp-success-bg: rgba(16, 185, 129, 0.12);
  --tp-success-border: rgba(16, 185, 129, 0.25);
  --tp-success-text: #34d399;

  --tp-warning-bg: rgba(245, 158, 11, 0.12);
  --tp-warning-border: rgba(245, 158, 11, 0.25);
  --tp-warning-text: #fbbf24;

  --tp-danger-bg: rgba(239, 68, 68, 0.12);
  --tp-danger-border: rgba(239, 68, 68, 0.25);
  --tp-danger-text: #f87171;

  --tp-info-bg: rgba(59, 130, 246, 0.12);
  --tp-info-border: rgba(59, 130, 246, 0.25);
  --tp-info-text: #60a5fa;

  --tp-focus-ring: 0 0 0 3px rgba(129, 140, 248, 0.45);
}
```

---

## 3. Typography Scale & Hierarchy

The typography scale uses `Inter` with tabular numerals (`font-feature-settings: "tnum"`) for financial and quantitative metrics.

| Token | Size | Weight | Line Height | Tracking | Intended Usage |
|---|---|---|---|---|---|
| `tp-display` | `1.75rem` (28px) | 800 (Extra Bold) | 1.25 | `-0.025em` | Master Dashboard Titles, Key Totals |
| `tp-h1` | `1.5rem` (24px) | 700 (Bold) | 1.3 | `-0.02em` | Page Header H1s, Major Section Titles |
| `tp-h2` | `1.25rem` (20px) | 700 (Bold) | 1.35 | `-0.015em` | Card Group Headers, Modal Titles |
| `tp-h3` | `1.05rem` (16.8px) | 600 (Semi Bold) | 1.4 | `-0.01em` | Table Headers, Section Subtitles |
| `tp-body` | `0.875rem` (14px) | 400 / 500 | 1.5 | `normal` | Standard Body, Table Cells, Form Inputs |
| `tp-caption` | `0.775rem` (12.4px) | 500 (Medium) | 1.4 | `0.01em` | Helper Text, Table Column Headers, Timestamps |
| `tp-badge-text` | `0.725rem` (11.6px) | 700 (Bold) | 1.2 | `0.02em` | Status Badges, Role Tags, Chip Counters |
| `tp-numeric` | `1.5rem`–`2.0rem` | 800 (Extra Bold) | 1.1 | `-0.02em` | KPI Card Primary Numbers (`tnum`) |

---

## 4. Reusable Core Component Patterns

### 4.1 Buttons (`.btn`, `.tp-btn`)
- **Primary Button (`.btn-primary`, `.tp-btn-primary`):** Solid `--tp-primary-600` background, white text, subtle hover brightness, active scale depression (`scale(0.98)`).
- **Secondary Button (`.btn-secondary`, `.tp-btn-secondary`):** Elevated card surface, 1px border (`--tp-surface-border`), subtle hover background tint.
- **Destructive Button (`.btn-danger`, `.tp-btn-danger`):** Red accent for irrevocable actions with confirmation.
- **Icon Buttons (`.btn-icon`):** Square bounding boxes (`36x36px` desktop, `42x42px` mobile touch bounds) with centered SVG icon and tooltip.

### 4.2 Form Inputs & Controls (`.form-control`, `.tp-input`, `.form-select`)
- Consistent `38px` input height across all text inputs, date pickers, and select dropdowns.
- Clear 1px border with smooth transition to `--tp-primary-500` and high-visibility 3px focus ring on `:focus-visible`.
- Integrated error state (`.is-invalid`, `.tp-input-error`) showing red border and inline helper text with exclamation icon.

### 4.3 KPI Cards (`.kpi-card`, `.tp-kpi-card`)
- Elevated white card (`#131b2e` in dark mode) with 1px border.
- Layout: Top subtitle label with trend badge; Large bold numeric value; Right-aligned circular icon container with tint matching metric category.
- Clickable hover state (`.tp-hover-lift`): Translates `translateY(-2px)` with expanded shadow.

### 4.4 Data Tables (`.data-table`, `.tp-table`)
- Sticky table header (`th`) with subtle border bottom and uppercase caption styling.
- Row hover transition with high-contrast indicator bar on the left edge.
- Mobile adaptive card layout (`@media (max-width: 768px)`): Table rows morph into structured stacked cards with data-label prefixes, eliminating horizontal scrolling headaches.

### 4.5 Modals & Drawers (`.modal`, `.tp-modal`, `.tp-drawer`)
- Centered modal dialogs with smooth scale-in animation (`opacity 0 -> 1, scale 0.96 -> 1`).
- Darkened backdrop (`rgba(15, 23, 42, 0.65)` with `backdrop-filter: blur(4px)`).
- Slide-over drawers for detail drilldowns (e.g. Telecaller RNR drilldown, WhatsApp chat) with smooth right-to-left slide transition.
