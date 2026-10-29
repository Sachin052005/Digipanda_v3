import os

BASE_DIR = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM"

# 1. Update base.html: bump CSS cache busting versions and shorten search placeholder
base_path = os.path.join(BASE_DIR, "templates", "base.html")
with open(base_path, "r", encoding="utf-8") as f:
    base_html = f.read()

base_html = base_html.replace(
    '<link rel="stylesheet" href="{% static \'css/crm.css\' %}?v=20261024_pwd_ui_cure">',
    '<link rel="stylesheet" href="{% static \'css/crm.css\' %}?v=20261024_zoom100_v3">'
)
base_html = base_html.replace(
    '<link rel="stylesheet" href="{% static \'css/design-system.css\' %}?v=20261024_pwd_ui_cure">',
    '<link rel="stylesheet" href="{% static \'css/design-system.css\' %}?v=20261024_zoom100_v3">'
)
base_html = base_html.replace(
    '<span class="tp-search-trigger-text">Search leads, actions...</span>',
    '<span class="tp-search-trigger-text">Search leads...</span>'
)

with open(base_path, "w", encoding="utf-8") as f:
    f.write(base_html)
print("SUCCESS: Updated base.html cache versions & search label")

# 2. Update admin_dashboard/dashboard.html: add tp-filter-action class to action buttons
dash_path = os.path.join(BASE_DIR, "templates", "admin_dashboard", "dashboard.html")
with open(dash_path, "r", encoding="utf-8") as f:
    dash_html = f.read()

dash_html = dash_html.replace(
    '<div style="display: flex; gap: 6px; align-items: flex-end;">\n      <button type="submit"',
    '<div class="tp-filter-action">\n      <button type="submit"'
)

with open(dash_path, "w", encoding="utf-8") as f:
    f.write(dash_html)
print("SUCCESS: Updated admin_dashboard.html filter action wrapper")

# 3. Patch CSS rules in crm.css
crm_css_path = os.path.join(BASE_DIR, "static", "css", "crm.css")
with open(crm_css_path, "r", encoding="utf-8") as f:
    crm_css = f.read()

# Replace the invalid CSS Grid syntax in crm.css
old_grid_rule = """.tp-compact-filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)) auto;
  gap: 10px;
  align-items: flex-end;
}"""

new_flex_rule = """.tp-compact-filter-grid {
  display: flex !important;
  flex-direction: row !important;
  flex-wrap: wrap !important;
  gap: 10px !important;
  align-items: flex-end !important;
  width: 100% !important;
}

.tp-filter-field {
  flex: 1 1 125px !important;
  min-width: 120px !important;
  display: flex !important;
  flex-direction: column !important;
  gap: 3px !important;
}

.tp-filter-action {
  flex: 0 0 auto !important;
  display: flex !important;
  gap: 6px !important;
  align-items: flex-end !important;
}"""

if old_grid_rule in crm_css:
    crm_css = crm_css.replace(old_grid_rule, new_flex_rule)
    print("SUCCESS: Replaced invalid CSS Grid in crm.css with robust Flexbox")
else:
    print("Note: old_grid_rule not exact match in crm.css, appending targeted override")

crm_css = crm_css.replace(
"""@media (min-width: 1360px) {
  .tp-kpi-grid-7 {
    grid-template-columns: repeat(7, 1fr);
  }
}
@media (max-width: 1359px) and (min-width: 992px) {
  .tp-kpi-grid-7 {
    grid-template-columns: repeat(4, 1fr);
  }
}""",
"""@media (min-width: 1280px) {
  .tp-kpi-grid-7 {
    grid-template-columns: repeat(7, 1fr) !important;
  }
}
@media (max-width: 1279px) and (min-width: 900px) {
  .tp-kpi-grid-7 {
    grid-template-columns: repeat(4, 1fr) !important;
  }
}"""
)

with open(crm_css_path, "w", encoding="utf-8") as f:
    f.write(crm_css)

# 4. Also inject high-priority rules into design-system.css so nothing overrides them
ds_css_path = os.path.join(BASE_DIR, "static", "css", "design-system.css")
with open(ds_css_path, "r", encoding="utf-8") as f:
    ds_css = f.read()

ds_additions = """
/* ==========================================================================
   DIGIPANDA CRM DASHBOARD ZOOM 100% HIGH-PRIORITY ENFORCEMENT
   ========================================================================== */
.tp-filter-bar {
  background: var(--tp-surface-card, var(--bg-card)) !important;
  border: 1px solid var(--tp-surface-border, var(--border-color)) !important;
  border-radius: var(--tp-radius-lg, 12px) !important;
  padding: 12px 18px !important;
  box-shadow: var(--shadow-sm) !important;
  margin-bottom: 20px !important;
}

.tp-compact-filter-grid {
  display: flex !important;
  flex-direction: row !important;
  flex-wrap: wrap !important;
  gap: 10px !important;
  align-items: flex-end !important;
  width: 100% !important;
}

.tp-filter-field {
  flex: 1 1 125px !important;
  min-width: 120px !important;
  display: flex !important;
  flex-direction: column !important;
  gap: 3px !important;
  box-sizing: border-box !important;
}

.tp-field-label {
  font-size: 0.72rem !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.04em !important;
  color: var(--tp-text-muted, var(--text-muted)) !important;
  margin: 0 0 2px 0 !important;
  white-space: nowrap !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  display: block !important;
}

.tp-input-compact,
.tp-select-compact {
  height: 34px !important;
  padding: 4px 8px !important;
  font-size: 0.8125rem !important;
  border-radius: var(--radius-sm, 6px) !important;
  border: 1px solid var(--border-color) !important;
  background: var(--bg-body) !important;
  color: var(--text-main) !important;
  width: 100% !important;
  box-sizing: border-box !important;
}

.tp-filter-action {
  flex: 0 0 auto !important;
  display: flex !important;
  gap: 6px !important;
  align-items: flex-end !important;
}

.tp-kpi-grid-7 {
  display: grid !important;
  grid-template-columns: repeat(auto-fit, minmax(136px, 1fr)) !important;
  gap: 12px !important;
}
@media (min-width: 1280px) {
  .tp-kpi-grid-7 {
    grid-template-columns: repeat(7, 1fr) !important;
  }
}
@media (max-width: 1279px) and (min-width: 900px) {
  .tp-kpi-grid-7 {
    grid-template-columns: repeat(4, 1fr) !important;
  }
}
@media (max-width: 899px) and (min-width: 550px) {
  .tp-kpi-grid-7 {
    grid-template-columns: repeat(2, 1fr) !important;
  }
}
@media (max-width: 549px) {
  .tp-kpi-grid-7 {
    grid-template-columns: 1fr !important;
  }
}

.tp-kpi-grid-5 {
  display: grid !important;
  grid-template-columns: repeat(auto-fit, minmax(175px, 1fr)) !important;
  gap: 12px !important;
}
@media (min-width: 1100px) {
  .tp-kpi-grid-5 {
    grid-template-columns: repeat(5, 1fr) !important;
  }
}
@media (max-width: 1099px) and (min-width: 700px) {
  .tp-kpi-grid-5 {
    grid-template-columns: repeat(3, 1fr) !important;
  }
}

.tp-kpi-grid-6 {
  display: grid !important;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)) !important;
  gap: 12px !important;
}
@media (min-width: 1200px) {
  .tp-kpi-grid-6 {
    grid-template-columns: repeat(6, 1fr) !important;
  }
}

.kpi-card, .tp-kpi-card {
  padding: 12px 16px !important;
  min-height: 74px !important;
}
"""

if "DIGIPANDA CRM DASHBOARD ZOOM 100% HIGH-PRIORITY ENFORCEMENT" not in ds_css:
    ds_css += "\n" + ds_additions

with open(ds_css_path, "w", encoding="utf-8") as f:
    f.write(ds_css)
print("SUCCESS: Updated design-system.css with high-priority zoom 100% enforcement")
