# Accessibility Plan (WCAG 2.2 AA Compliance)

## 1. Core Accessibility Standards
The futuristic redesign of TECHPANDA CRM adheres to WCAG 2.2 Level AA requirements:
1. **Perceivable**: High contrast ratios ($\ge 4.5:1$ for normal text, $\ge 3:1$ for large text and UI components) across both light and dark themes.
2. **Operable**: All buttons, inputs, drawers, modals, and canvas tools are operable via keyboard.
3. **Understandable**: Clear visual focus indicators, error messages, and predictable interaction models.
4. **Robust**: Semantic HTML5 elements (`<button>`, `<nav>`, `<aside>`, `<main>`, `<header>`) with proper ARIA attributes where needed.

---

## 2. Universal Focus Indicators
Every button and interactive element features a high-visibility, 2px electric cyan focus ring with a 2px offset:
```css
:focus-visible {
  outline: 2px solid #38bdf8 !important;
  outline-offset: 2px !important;
}
```
This guarantees that keyboard navigation (`Tab` / `Shift+Tab`) is instantly recognizable across dark obsidian and light slate backgrounds.

---

## 3. Motion Safety & Vestibular Protection
For users who experience motion sickness or vestibular issues, all animations are wrapped in `@media (prefers-reduced-motion: reduce)`:
- Infinite background lasers (`headerLaser`, `btnLaserBeam`) are disabled.
- Pulsing glow rings (`beaconPulse`) transition to static badges.
- Card hover translation is disabled, relying strictly on clear border color changes.

---

## 4. Screen-Reader & Form Labeling
- All icon-only buttons include descriptive `aria-label` or `title` attributes.
- Dynamic status changes (e.g. "Saving...", "Lead Saved Successfully") announce through live region alerts (`aria-live="polite"`).
