# Developer Implementation Handoff & Architecture Blueprint

## 1. Overview & Scope Boundary
This document defines the exact frontend specifications for the Developer Agent to implement the modern, animated, futuristic redesign across the entire TECHPANDA CRM application:
- **Scope**: Frontend UI/UX, styling, animation, layout, and component polish.
- **Strict Boundary**: Zero changes to database models, backend logic, authentication, permissions, API endpoints, or existing form submission keys.

---

## 2. File Modification Inventory

1. **`CRM/static/css/design-system.css`**:
   - Inject the Futuristic Tactile Button Engine (`.btn`, `.btn-primary`, `.btn-secondary`, `.btn-success`, `.btn-danger`, `.btn-warning`, `.btn-glass`).
   - Add global keyframes (`btnLaserBeam`, `headerLaser`, `beaconPulse`, `toastPop`).
   - Add modern glassmorphism tokens, specular top borders, and hover lift shadows.
   - Add universal `:focus-visible` cyber cyan indicators.

2. **`CRM/static/css/crm.css`**:
   - Update legacy button styles to inherit the new tactile button tokens.
   - Refine `.page-header`, `.page-actions`, and search inputs with frosted glass surfaces.
   - Refine data table row hover effects with smooth velvet lighting.

3. **`CRM/templates/base.html`**:
   - Upgrade the sidebar brand logo with a glowing cyber badge.
   - Enhance the active navigation rail indicator with neon laser accents.
   - Add smooth transition easing on sidebar expansion and accordion groups.

---

## 3. Preserved Functional Contracts
- All button IDs (e.g. `#save_button`, `#btn_export`, `#btn_filter`) and form action URLs must remain unchanged.
- All template variables (`{{ form }}`, `{{ leads }}`, `{{ user }}`, etc.) must remain intact.
- Django CSRF tokens (`{% csrf_token %}`) must remain in all forms.
