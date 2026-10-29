# UI/UX Acceptance & Verification Test Plan

## 1. Test Objectives
Verify that the modern, animated, futuristic redesign is active, aesthetically cohesive, fully responsive, and functionally stable across all application screens.

---

## 2. Test Checklist

### 2.1 Button-to-Button Inspection
- [ ] **`.btn-primary`**:
  - Displays rich electric indigo gradient with specular top highlight.
  - Hover triggers smooth `-2px` translateY and animated laser beam sweep.
  - Active press compresses button smoothly by `scale(0.97)`.
  - Focus ring appears as 2px electric cyan ring with 2px offset.
- [ ] **`.btn-secondary`**:
  - Displays frosted glass surface with crisp typography.
  - Hover illuminates border to vibrant indigo with subtle shadow bloom.
  - Active press gives tactile tactile depression.
- [ ] **`.btn-success`**:
  - Neon emerald gradient with laser sweep and glowing halo.
- [ ] **`.btn-danger`**:
  - Crimson nova gradient with laser sweep and danger halo.
- [ ] **`.btn-warning`**:
  - Amber gold gradient with warm warning halo.

### 2.2 Shell & Navigation
- [ ] Sidebar active link shows glowing cyan left-rail indicator.
- [ ] Top command bar search button opens command palette smoothly.
- [ ] Dark/Light mode toggle smoothly transitions surface luminance without layout shift.
- [ ] Telephony dock shows live status beacon pulsing with `beaconPulse`.

### 2.3 Cards & Data Tables
- [ ] KPI cards display top accent laser bars.
- [ ] Table rows illuminate with velvet glow on hover.
- [ ] Lead tokens and IDs render in crisp monospace font.

### 2.4 Accessibility & Performance
- [ ] Keyboard navigation (`Tab`) displays prominent focus ring on every control.
- [ ] Activating `prefers-reduced-motion` in browser disables laser sweeps and motion scaling.
- [ ] Zero layout shifts or console errors during page navigation.
