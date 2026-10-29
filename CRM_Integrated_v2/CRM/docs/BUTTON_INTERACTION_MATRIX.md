# Button-to-Button Interaction Matrix & Physics Specification

## 1. Overview
The user mandate is to redesign the entire application **"end to end, button to button"** with a modern, animated, futuristic aesthetic. Every interactive trigger across the CRM, automation builder, reception desk, and reports must conform to the **Futuristic Tactile Button Engine**.

---

## 2. Global Button Design Tokens & Physics

### 2.1 Physics & Timing Curves
- **Hover Transition**: `all 0.22s cubic-bezier(0.16, 1, 0.3, 1)`
- **Active Press Transition**: `all 0.08s cubic-bezier(0.4, 0, 0.2, 1)`
- **Hover Lift**: `transform: translateY(-2px)`
- **Active Compression**: `transform: translateY(0px) scale(0.97)`
- **Specular Highlight**: `inset 0 1px 1px 0 rgba(255, 255, 255, 0.35)`
- **Focus Ring**: `outline: 2px solid #38bdf8; outline-offset: 2px;`

### 2.2 Laser Sweep Animation (`btnLaserBeam`)
Primary, high-action, and save buttons feature an internal pseudo-element laser beam that sweeps across the button face on hover:
```css
.btn-primary::after {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 60%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.35), transparent);
  transition: none;
}
.btn-primary:hover::after {
  animation: btnLaserBeam 1.2s cubic-bezier(0.16, 1, 0.3, 1) infinite;
}
@keyframes btnLaserBeam {
  0% { left: -100%; }
  100% { left: 160%; }
}
```

---

## 3. Comprehensive Button Variant Matrix

| Variant Class | Base Appearance | Hover State & Motion | Active / Pressed | Focus State |
| :--- | :--- | :--- | :--- | :--- |
| **`.btn-primary`** | Electric Indigo gradient (`#6366f1` $\rightarrow$ `#4f46e5`), specular top edge, white bold text | `translateY(-2px)`, deep indigo shadow bloom (`0 8px 24px rgba(79, 70, 229, 0.4)`), animated laser sweep | `scale(0.97)`, shadow collapses to `0 2px 6px` | 2px electric cyan ring (`#38bdf8`) with 2px offset |
| **`.btn-secondary`** | Frosted glass (`rgba(255, 255, 255, 0.08)` in dark, `#ffffff` in light), 1.5px subtle border | `translateY(-2px)`, border illuminates to `#6366f1`, subtle glass glow bloom | `scale(0.97)`, background darkens slightly | 2px electric cyan ring with 2px offset |
| **`.btn-success`** | Neon Emerald gradient (`#10b981` $\rightarrow$ `#059669`), specular top edge | `translateY(-2px)`, emerald shadow bloom (`0 8px 22px rgba(16, 185, 129, 0.4)`), laser sweep | `scale(0.97)`, shadow collapses | 2px neon emerald ring (`#34d399`) with 2px offset |
| **`.btn-danger`** | Crimson Nova gradient (`#ef4444` $\rightarrow$ `#dc2626`), specular top edge | `translateY(-2px)`, crimson shadow bloom (`0 8px 22px rgba(239, 68, 68, 0.4)`), laser sweep | `scale(0.97)`, shadow collapses | 2px crimson ring (`#f87171`) with 2px offset |
| **`.btn-warning`** | Amber Gold gradient (`#f59e0b` $\rightarrow$ `#d97706`), specular top edge | `translateY(-2px)`, amber shadow bloom (`0 8px 22px rgba(245, 158, 11, 0.4)`), laser sweep | `scale(0.97)`, shadow collapses | 2px amber ring (`#fbbf24`) with 2px offset |
| **`.btn-outline-primary`** | Transparent background, 1.5px `#6366f1` border, `#6366f1` text | Fills with `#4f46e5`, text turns white, `translateY(-2px)`, soft indigo glow | `scale(0.97)` | 2px electric cyan ring |
| **`.btn-glass` / `.studio-btn-glass`** | Translucent pill (`rgba(255, 255, 255, 0.1)`), 1px border (`rgba(255, 255, 255, 0.15)`) | Background brightens to `rgba(255, 255, 255, 0.22)`, `translateY(-1px)`, text illuminates | `scale(0.96)` | 2px electric cyan ring |
| **`.btn-icon-action`** | Circular / rounded square icon-only button with translucent surface | Rotates or scales icon slightly (`transform: scale(1.08)`), glowing border | `scale(0.92)` | 2px electric cyan ring |

---

## 4. State & Accessibility Rules
1. **Disabled State (`:disabled`, `.disabled`)**:
   - `opacity: 0.45; cursor: not-allowed; pointer-events: none; transform: none; box-shadow: none;`
   - No laser sweep animations execute while disabled.
2. **Loading State (`.btn-loading`)**:
   - Replaces or prefixes button icon with a futuristic rotating neon spinner:
     ```css
     .btn-loading::before {
       content: '';
       width: 14px;
       height: 14px;
       border: 2px solid rgba(255, 255, 255, 0.3);
       border-top-color: #ffffff;
       border-radius: 50%;
       animation: btnSpin 0.7s linear infinite;
     }
     ```
3. **Reduced Motion Compliance**:
   - Under `@media (prefers-reduced-motion: reduce)`, transitions are simplified to instantaneous or 0.05s opacity shifts without `translateY`, `scale`, or infinite laser sweeps.
