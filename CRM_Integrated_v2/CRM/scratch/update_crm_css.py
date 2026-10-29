import os

BASE_DIR = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM"
css_path = os.path.join(BASE_DIR, "static", "css", "crm.css")

with open(css_path, "r", encoding="utf-8") as f:
    css = f.read()

# 1. Update .app-sidebar width
css = css.replace(
"""/* Sidebar */
.app-sidebar {
  width: 225px;
  height: 100vh;
  background-color: var(--bg-sidebar, #0f172a);
  color: var(--text-sidebar);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width 0.25s ease, transform 0.25s ease;
  z-index: 100;
  border-right: 1px solid rgba(255, 255, 255, 0.05);
}""",
"""/* Sidebar */
.app-sidebar {
  width: 240px;
  height: 100vh;
  background-color: var(--bg-sidebar, #0f172a);
  color: var(--text-sidebar);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width 0.25s ease, transform 0.25s ease;
  z-index: 100;
  border-right: 1px solid rgba(255, 255, 255, 0.05);
}"""
)

# 2. Update .app-sidebar.collapsed
css = css.replace(
""".app-sidebar.collapsed {
  width: 60px;
}""",
""".app-sidebar.collapsed {
  width: 64px;
}"""
)

# 3. Update .sidebar-nav scrollbar
css = css.replace(
""".sidebar-nav {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 10px 8px;
}""",
""".sidebar-nav {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 10px 8px;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.16) transparent;
}
.sidebar-nav::-webkit-scrollbar {
  width: 5px;
}
.sidebar-nav::-webkit-scrollbar-track {
  background: transparent;
}
.sidebar-nav::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.16);
  border-radius: 4px;
}
.sidebar-nav::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}"""
)

# 4. Update .app-main
css = css.replace(
"""/* Main Content Area */
.app-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
}""",
"""/* Main Content Area */
.app-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.3) transparent;
}
.app-main::-webkit-scrollbar {
  width: 6px;
}
.app-main::-webkit-scrollbar-track {
  background: transparent;
}
.app-main::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.3);
  border-radius: 4px;
}"""
)

# 5. Header updates
old_header_css = """/* Header */
.app-header {
  height: 52px;
  background-color: var(--tp-glass-bg, rgba(255, 255, 255, 0.88));
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  position: sticky;
  top: 0;
  z-index: 2000 !important;
  box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.05);
  backdrop-filter: var(--tp-glass-blur, blur(16px));
  -webkit-backdrop-filter: var(--tp-glass-blur, blur(16px));
}

.app-header.has-open-dropdown,
.app-header:has(.is-open) {
  z-index: 10000 !important;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: nowrap !important;
  min-width: 0;
  position: relative;
  z-index: 50;
}

.header-left.has-open-dropdown,
.header-left:has(.is-open) {
  z-index: 10005 !important;
}

.tp-nav-branch-picker {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  position: relative;
}

.tp-nav-branch-picker.has-open-dropdown,
.tp-nav-branch-picker:has(.is-open) {
  z-index: 10005 !important;
}

.tp-nav-branch-picker .tp-cselect-wrapper {
  position: relative !important;
}

.tp-nav-branch-picker .tp-cselect-wrapper.is-open {
  z-index: 10006 !important;
}

.tp-nav-branch-picker .tp-cselect-menu {
  z-index: 10010 !important;
  min-width: 180px;
  max-width: 260px;
}
[data-theme="dark"] .app-header {
  background-color: var(--tp-glass-bg, rgba(19, 27, 46, 0.88));
  box-shadow: 0 4px 24px -2px rgba(0, 0, 0, 0.45);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.btn-sidebar-toggle {
  background: none;
  border: 1px solid var(--border-color);
  color: var(--text-muted);
  border-radius: var(--radius-sm);
  padding: 4px 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.btn-sidebar-toggle:hover {
  background-color: var(--primary-light);
  color: var(--primary);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}"""

new_header_css = """/* Header (Modern 3-Zone Architecture) */
.app-header {
  height: 58px;
  background-color: var(--tp-glass-bg, rgba(255, 255, 255, 0.92));
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 24px;
  position: sticky;
  top: 0;
  z-index: 2000 !important;
  box-shadow: 0 2px 12px -2px rgba(15, 23, 42, 0.04);
  backdrop-filter: var(--tp-glass-blur, blur(16px));
  -webkit-backdrop-filter: var(--tp-glass-blur, blur(16px));
}

.app-header.has-open-dropdown,
.app-header:has(.is-open) {
  z-index: 10000 !important;
}

[data-theme="dark"] .app-header {
  background-color: var(--tp-glass-bg, rgba(15, 23, 42, 0.92));
  border-bottom-color: rgba(255, 255, 255, 0.08);
  box-shadow: 0 2px 16px -2px rgba(0, 0, 0, 0.5);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
  min-width: 0;
}

.header-left .header-brand-link {
  display: none;
  align-items: center;
}

.app-sidebar.collapsed ~ .app-main .header-left .header-brand-link {
  display: inline-flex;
}

@media (max-width: 900px) {
  .header-left .header-brand-link {
    display: inline-flex;
  }
}

.btn-sidebar-toggle {
  background: none;
  border: 1px solid var(--border-color);
  color: var(--text-muted);
  border-radius: var(--radius-sm);
  padding: 5px 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}
.btn-sidebar-toggle:hover {
  background-color: var(--primary-light);
  color: var(--primary);
  border-color: var(--primary);
}

.header-center {
  flex: 1 1 auto;
  display: flex;
  justify-content: flex-start;
  max-width: 380px;
  min-width: 0;
}

.tp-search-trigger-btn {
  width: 100%;
  max-width: 360px;
  height: 35px;
  background: var(--bg-body);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm, 8px);
  padding: 0 12px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
  font-size: 0.8125rem;
  cursor: pointer;
  transition: all 0.2s ease;
}
.tp-search-trigger-btn:hover {
  background: var(--bg-card-hover);
  border-color: var(--primary);
  color: var(--text-main);
}
.tp-search-trigger-text {
  flex: 1;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.tp-kbd-shortcut {
  font-size: 0.7rem;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  padding: 1px 5px;
  border-radius: 4px;
  font-weight: 600;
  color: var(--text-muted);
  flex-shrink: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  min-width: 0;
}

.tp-header-branch-form {
  display: inline-flex;
  align-items: center;
  margin: 0;
  flex-shrink: 0;
}

.tp-nav-branch-picker {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  position: relative;
}
.tp-nav-branch-picker.has-open-dropdown,
.tp-nav-branch-picker:has(.is-open) {
  z-index: 10005 !important;
}
.tp-nav-branch-picker .tp-cselect-wrapper {
  position: relative !important;
}
.tp-nav-branch-picker .tp-cselect-wrapper.is-open {
  z-index: 10006 !important;
}
.tp-nav-branch-picker .tp-cselect-menu {
  z-index: 10010 !important;
  min-width: 180px;
  max-width: 260px;
}"""

if old_header_css in css:
    css = css.replace(old_header_css, new_header_css)
else:
    print("Warning: old_header_css not found directly, will check line by line")

# 6. Update .content-wrapper
css = css.replace(
"""/* Page Content */
.content-wrapper {
  padding: 20px 24px;
  flex: 1;
  animation: none;
}""",
"""/* Page Content */
.content-wrapper {
  padding: 20px 28px;
  flex: 1;
  width: 100%;
  max-width: 1680px;
  margin: 0 auto;
  box-sizing: border-box;
  min-width: 0;
  animation: none;
}
@media (max-width: 768px) {
  .content-wrapper {
    padding: 14px 16px;
  }
}"""
)

# 7. Add Dashboard Responsive Grid, Compact Filter Bar, and KPI Classes to end of crm.css
responsive_additions = """
/* ==========================================================================
   DIGIPANDA CRM DASHBOARD RESPONSIVE SUITE (100% ZOOM STABILITY)
   ========================================================================== */

/* 1. High-Density Compact Filter Command Bar */
.tp-filter-bar {
  background: var(--tp-surface-card, var(--bg-card));
  border: 1px solid var(--tp-surface-border, var(--border-color));
  border-radius: var(--tp-radius-lg, 12px);
  padding: 14px 18px;
  box-shadow: var(--shadow-sm);
  margin-bottom: 20px;
}

.tp-compact-filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)) auto;
  gap: 10px;
  align-items: flex-end;
}

.tp-filter-field {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.tp-field-label {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--tp-text-muted, var(--text-muted));
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tp-input-compact,
.tp-select-compact {
  height: 33px;
  padding: 4px 8px;
  font-size: 0.8125rem;
  border-radius: var(--radius-sm, 6px);
  border: 1px solid var(--border-color);
  background: var(--bg-body);
  color: var(--text-main);
  width: 100%;
  box-sizing: border-box;
}

.tp-input-compact:focus,
.tp-select-compact:focus {
  border-color: var(--primary);
  outline: none;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.15);
}

@media (max-width: 900px) {
  .tp-compact-filter-grid {
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  }
}

/* 2. Structured Executive KPI Grids (Prevents Lone Card Stretches) */
.tp-kpi-grid-7 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(138px, 1fr));
  gap: 12px;
}
@media (min-width: 1360px) {
  .tp-kpi-grid-7 {
    grid-template-columns: repeat(7, 1fr);
  }
}
@media (max-width: 1359px) and (min-width: 992px) {
  .tp-kpi-grid-7 {
    grid-template-columns: repeat(4, 1fr);
  }
}
@media (max-width: 991px) and (min-width: 580px) {
  .tp-kpi-grid-7 {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 579px) {
  .tp-kpi-grid-7 {
    grid-template-columns: 1fr;
  }
}

.tp-kpi-grid-5 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}
@media (min-width: 1200px) {
  .tp-kpi-grid-5 {
    grid-template-columns: repeat(5, 1fr);
  }
}
@media (max-width: 1199px) and (min-width: 768px) {
  .tp-kpi-grid-5 {
    grid-template-columns: repeat(3, 1fr);
  }
}
@media (max-width: 767px) {
  .tp-kpi-grid-5 {
    grid-template-columns: repeat(2, 1fr);
  }
}

.tp-kpi-grid-6 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}
@media (min-width: 1200px) {
  .tp-kpi-grid-6 {
    grid-template-columns: repeat(6, 1fr);
  }
}
@media (max-width: 1199px) and (min-width: 768px) {
  .tp-kpi-grid-6 {
    grid-template-columns: repeat(3, 1fr);
  }
}

/* 3. Balanced KPI Card Inner Layout */
.kpi-card, .tp-kpi-card {
  padding: 12px 16px !important;
  min-height: 74px;
}
.kpi-card .kpi-info h4, .tp-kpi-card .kpi-info h4 {
  font-size: 0.725rem !important;
  margin-bottom: 4px !important;
  line-height: 1.2 !important;
}
.kpi-card .kpi-value, .tp-kpi-card .kpi-value {
  font-size: 1.45rem !important;
  line-height: 1.15 !important;
}
.kpi-icon-wrap {
  width: 36px !important;
  height: 36px !important;
  border-radius: 8px !important;
}
.kpi-icon-wrap svg {
  width: 18px !important;
  height: 18px !important;
}

/* 4. Chart Cards & Performance Tables Container Bounds */
.tp-chart-card,
.crm-card,
.tp-card {
  min-width: 0 !important;
}
.table-responsive {
  width: 100% !important;
  min-width: 0 !important;
  overflow-x: auto !important;
  -webkit-overflow-scrolling: touch;
}
"""

if "DIGIPANDA CRM DASHBOARD RESPONSIVE SUITE" not in css:
    css = css + "\n" + responsive_additions

with open(css_path, "w", encoding="utf-8") as f:
    f.write(css)

print("SUCCESS: Updated crm.css")
