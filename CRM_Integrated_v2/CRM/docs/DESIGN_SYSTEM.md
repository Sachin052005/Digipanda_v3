# Unified Futuristic Design System (Tokens, Surfaces & Components)

## 1. Design Tokens Specification

### 1.1 Color Tokens
```css
:root {
  /* Brand Primary Hologram */
  --tp-primary-50: #eef2ff;
  --tp-primary-100: #e0e7ff;
  --tp-primary-200: #c7d2fe;
  --tp-primary-300: #a5b4fc;
  --tp-primary-400: #818cf8;
  --tp-primary-500: #6366f1;
  --tp-primary-600: #4f46e5;
  --tp-primary-700: #4338ca;
  --tp-primary-800: #3730a3;
  --tp-primary-900: #312e81;

  /* Cyber Accents */
  --tp-cyan-400: #22d3ee;
  --tp-cyan-500: #06b6d4;
  --tp-cyan-glow: rgba(6, 182, 212, 0.35);

  --tp-emerald-500: #10b981;
  --tp-emerald-glow: rgba(16, 185, 129, 0.4);

  --tp-amber-500: #f59e0b;
  --tp-amber-glow: rgba(245, 158, 11, 0.35);

  --tp-rose-500: #ef4444;
  --tp-rose-glow: rgba(239, 68, 68, 0.4);

  /* Light Theme Surfaces */
  --tp-surface-bg: #f8fafc;
  --tp-surface-card: #ffffff;
  --tp-surface-card-hover: #f1f5f9;
  --tp-surface-border: #e2e8f0;
  --tp-surface-border-subtle: #edf2f7;

  /* Frosted Glass */
  --tp-glass-bg: rgba(255, 255, 255, 0.85);
  --tp-glass-border: rgba(255, 255, 255, 0.7);
  --tp-glass-specular: inset 0 1px 1px 0 rgba(255, 255, 255, 0.95);
  --tp-glass-blur: blur(16px) saturate(180%);

  /* Futuristic Radii & Elevation */
  --tp-radius-xs: 6px;
  --tp-radius-sm: 8px;
  --tp-radius-md: 12px;
  --tp-radius-lg: 16px;
  --tp-radius-xl: 24px;
  --tp-radius-full: 9999px;

  --tp-shadow-ambient: 0 4px 20px -2px rgba(15, 23, 42, 0.08);
  --tp-shadow-hover: 0 16px 36px -6px rgba(15, 23, 42, 0.16), 0 0 20px -4px rgba(99, 102, 241, 0.15);
  --tp-shadow-laser: 0 4px 18px rgba(79, 70, 229, 0.4);
}

[data-theme="dark"], html[data-theme="dark"] {
  /* Dark Cosmic Obsidian Surfaces */
  --tp-surface-bg: #080c15;
  --tp-surface-card: #0e1422;
  --tp-surface-card-hover: #162035;
  --tp-surface-border: #1e293b;
  --tp-surface-border-subtle: #151d2f;

  --tp-text-primary: #f8fafc;
  --tp-text-secondary: #cbd5e1;
  --tp-text-muted: #94a3b8;
  --tp-text-subtle: #64748b;

  --tp-glass-bg: rgba(14, 20, 34, 0.85);
  --tp-glass-border: rgba(255, 255, 255, 0.1);
  --tp-glass-specular: inset 0 1px 1px 0 rgba(255, 255, 255, 0.18);
  --tp-glass-blur: blur(20px) saturate(190%);

  --tp-shadow-ambient: 0 4px 25px -2px rgba(0, 0, 0, 0.6);
  --tp-shadow-hover: 0 20px 40px -8px rgba(0, 0, 0, 0.8), 0 0 25px -4px rgba(99, 102, 241, 0.25);
}
```

---

## 2. Reusable Component Systems

### 2.1 The Global Button Engine (`.btn`)
All buttons share the base `.btn` class and variant modifiers:
- Specular top highlight (`inset 0 1px 0 rgba(255, 255, 255, 0.22)`).
- Spring micro-interaction (`transform: translateY(-2px)` on hover, `scale(0.97)` on active).
- Relative positioning with `overflow: hidden` for internal laser beam sweep.
- Clean typography: `font-size: 0.8125rem; font-weight: 700; letter-spacing: -0.01em;`.

### 2.2 Futuristic HUD Cards (`.tp-card-hud`, `.card`)
- Rounded corners (`border-radius: 16px`).
- Ambient backdrop blur and translucent background.
- Top border specular highlight.
- Optional holographic top laser accent bar (`height: 3px`).

### 2.3 Cyber Data Tables (`.table`, `.leads-table`)
- High-contrast header with uppercase tracking (`font-size: 0.72rem; font-weight: 800; letter-spacing: 0.06em;`).
- Zebra hover illumination with velvet glow.
- Monospace tokens for IDs, lead tokens (`[WI-ANN-001]`), timestamps, and phone numbers.

### 2.4 Cyber Inputs & Form Controls
- Focus ring: `box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25), 0 1px 2px rgba(15, 23, 42, 0.05); border-color: var(--tp-primary-500);`.
- Smooth transition: `border-color 0.18s ease, box-shadow 0.18s ease`.
