# Motion Design & Choreography Specification

## 1. Principles of Motion
Animation in TECHPANDA CRM must feel responsive, purposeful, and technologically advanced:
1. **Speed & Efficiency**: Routine workflows must never be delayed by decorative animation. Micro-interactions take $\le 220\text{ms}$.
2. **Physical Continuity**: Cards, dialogs, drawers, and tabs move with spring damping rather than mechanical linear steps.
3. **Spatial Awareness**: Modals emerge from the user's viewport center; drawers glide along their active axis; tooltips and dropdown menus pop with subtle spring scaling.

---

## 2. Core Keyframe Library

### 2.1 `headerLaser` (Continuous Topbar Ambient Energy)
```css
@keyframes headerLaser {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
```
*Application*: Walk-in desks, studio command headers, and card top-accent bars.

### 2.2 `btnLaserBeam` (Interactive Tactile Button Sweep)
```css
@keyframes btnLaserBeam {
  0% { left: -100%; }
  100% { left: 160%; }
}
```
*Application*: `.btn-primary`, `.btn-save`, `.btn-submit` upon user hover.

### 2.3 `beaconPulse` (Live System Status & Telephony Radar)
```css
@keyframes beaconPulse {
  0% {
    transform: scale(0.95);
    box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
  }
  70% {
    transform: scale(1.08);
    box-shadow: 0 0 0 8px rgba(16, 185, 129, 0);
  }
  100% {
    transform: scale(0.95);
    box-shadow: 0 0 0 0 rgba(16, 185, 129, 0);
  }
}
```
*Application*: Live engine status, active reception desk radar, ringing call dock, and waiting queue badges.

### 2.4 `toastPop` (Notification Arrival)
```css
@keyframes toastPop {
  0% {
    transform: translateY(20px) scale(0.94);
    opacity: 0;
  }
  100% {
    transform: translateY(0) scale(1);
    opacity: 1;
  }
}
```
*Application*: Instant toast notifications, save feedback, and webhook confirmation alerts.

### 2.5 `cardHoverLift`
```css
.tp-card-interactive, .sim-section-box, .builder-section-card, .desk-kpi-card {
  transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.22s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.22s ease;
}
.tp-card-interactive:hover {
  transform: translateY(-2px);
  box-shadow: 0 16px 36px -6px rgba(15, 23, 42, 0.16), 0 0 20px -4px rgba(99, 102, 241, 0.12);
}
```

---

## 3. Reduced Motion Graceful Degradation
Under the media query `@media (prefers-reduced-motion: reduce)`:
- Animations with infinite loops (`headerLaser`, `btnLaserBeam`, `beaconPulse`) are paused.
- Dynamic `translateY(-2px)` and `scale(0.97)` are converted to simple color and opacity adjustments.
- Transitions default to `0.05s ease` to protect users with vestibular conditions while preserving functional state clarity.
