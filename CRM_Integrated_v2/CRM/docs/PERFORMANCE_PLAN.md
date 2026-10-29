# Performance Plan & Asset Optimization

## 1. Zero-FOUC & Render Speed
- **Early Theme Attribution**: The lightweight theme script (`theme-manager.js`) executes in the document `<head>` to prevent Flash of Unstyled Content (FOUC) when loading dark mode.
- **Hardware-Accelerated Transitions**: All button and card animations exclusively manipulate `transform` and `opacity`, avoiding expensive browser layout recalculations (`reflow`).
- **GPU Compositing**: Key interactive elements utilize `will-change: transform` cautiously to ensure smooth 60fps / 120fps animations on mobile and low-power devices.

---

## 2. CSS Architecture & Clean Cascading
- Global futuristic styling is packaged directly into `CRM/static/css/design-system.css` and `CRM/static/css/crm.css`.
- Zero external CSS frameworks or Node.js runtime dependencies are introduced, maintaining 100% compatibility with the Django monolith stack.

---

## 3. Font & Asset Optimization
- Inter & Plus Jakarta Sans loaded from Google Fonts with `preconnect` and `display=swap`.
- SVG icons used inline for zero network roundtrips and sharp scalability on high-DPI retina displays.
