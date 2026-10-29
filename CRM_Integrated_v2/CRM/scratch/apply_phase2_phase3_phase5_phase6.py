import os

CRM_DIR = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM'

# 1. Update static/css/design-system.css
ds_path = os.path.join(CRM_DIR, 'static', 'css', 'design-system.css')
with open(ds_path, 'r', encoding='utf-8') as f:
    ds_css = f.read()

# Add token bridges to :root before line 94
bridge_tokens = """
  /* ==========================================================================
     UNIFIED AUTHORITATIVE DESIGN TOKEN BRIDGES (PLAN-UI-2026-001)
     Bridges --saas-* and legacy variable namespaces to authoritative --tp-* tokens
     ========================================================================== */
  --saas-primary: var(--tp-primary-600);
  --saas-primary-hover: var(--tp-primary-700);
  --saas-canvas: var(--tp-surface-bg);
  --saas-canvas-subtle: var(--tp-surface-card-hover);
  --saas-surface: var(--tp-surface-card);
  --saas-border: var(--tp-surface-border);
  --saas-border-subtle: var(--tp-surface-border-subtle);
  --saas-text-main: var(--tp-text-primary);
  --saas-text-muted: var(--tp-text-muted);
  --saas-text-subtle: var(--tp-text-subtle);

  /* Legacy un-prefixed variable bridges */
  --primary-color: var(--tp-primary-600);
  --primary-hover: var(--tp-primary-700);
  --bg-main: var(--tp-surface-bg);
  --bg-card: var(--tp-surface-card);
  --bg-card-hover: var(--tp-surface-card-hover);
  --border-color: var(--tp-surface-border);
  --text-main: var(--tp-text-primary);
  --text-muted: var(--tp-text-muted);
  --text-subtle: var(--tp-text-subtle);
  --primary: var(--tp-primary-600);
  --success: #10b981;
  --warning: #f59e0b;
  --danger: #ef4444;
  --info: #3b82f6;
  --radius-sm: var(--tp-radius-sm);
  --radius-md: var(--tp-radius-md);
  --radius-lg: var(--tp-radius-lg);
  --shadow-sm: var(--tp-shadow-sm);
  --shadow-md: var(--tp-shadow-md);
  --shadow-lg: var(--tp-shadow-lg);
"""

target_root_end = "  --tp-gloss-highlight: linear-gradient(180deg, rgba(255, 255, 255, 0.25) 0%, rgba(255, 255, 255, 0) 100%);\n}"
if target_root_end in ds_css:
    ds_css = ds_css.replace(target_root_end, "  --tp-gloss-highlight: linear-gradient(180deg, rgba(255, 255, 255, 0.25) 0%, rgba(255, 255, 255, 0) 100%);" + bridge_tokens + "\n}", 1)
    print("design-system.css :root bridges added")
else:
    target_root_end_crlf = target_root_end.replace('\n', '\r\n')
    if target_root_end_crlf in ds_css:
        ds_css = ds_css.replace(target_root_end_crlf, "  --tp-gloss-highlight: linear-gradient(180deg, rgba(255, 255, 255, 0.25) 0%, rgba(255, 255, 255, 0) 100%);" + bridge_tokens.replace('\n', '\r\n') + "\r\n}", 1)
        print("design-system.css :root bridges added (CRLF)")
    else:
        print("Could not find target_root_end in design-system.css")

# Update responsive KPI grid rules at lines 3753-3767
old_kpi_mq = """@media (max-width: 1279px) and (min-width: 900px) {
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
}"""

new_kpi_mq = """@media (max-width: 1279px) and (min-width: 1025px) {
  .tp-kpi-grid-7 {
    grid-template-columns: repeat(4, 1fr) !important;
  }
}
@media (max-width: 1024px) and (min-width: 641px) {
  .tp-kpi-grid-7, .tp-kpi-grid-5, .tp-kpi-grid-6 {
    grid-template-columns: repeat(3, 1fr) !important;
  }
}
@media (max-width: 640px) {
  .tp-kpi-grid-7, .tp-kpi-grid-5, .tp-kpi-grid-6 {
    grid-template-columns: repeat(2, 1fr) !important;
    gap: 8px !important;
  }
}
@media (max-width: 360px) {
  .tp-kpi-grid-7, .tp-kpi-grid-5, .tp-kpi-grid-6 {
    grid-template-columns: 1fr !important;
  }
}"""

if old_kpi_mq in ds_css:
    ds_css = ds_css.replace(old_kpi_mq, new_kpi_mq, 1)
    print("design-system.css responsive KPI grid updated")
else:
    old_kpi_mq_crlf = old_kpi_mq.replace('\n', '\r\n')
    new_kpi_mq_crlf = new_kpi_mq.replace('\n', '\r\n')
    if old_kpi_mq_crlf in ds_css:
        ds_css = ds_css.replace(old_kpi_mq_crlf, new_kpi_mq_crlf, 1)
        print("design-system.css responsive KPI grid updated (CRLF)")
    else:
        print("Could not find old_kpi_mq in design-system.css")

# Append .table-responsive wrapper helper if not present
if '.table-responsive' not in ds_css:
    ds_css += """\n
/* Responsive Table Container Helper */
.table-responsive {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  margin-bottom: 1rem;
}
"""

with open(ds_path, 'w', encoding='utf-8') as f:
    f.write(ds_css)


# 2. Update templates/base.html (ARIA for call notes modal)
base_path = os.path.join(CRM_DIR, 'templates', 'base.html')
with open(base_path, 'r', encoding='utf-8') as f:
    base_html = f.read()

old_call_modal = '<div id="call-notes-required-modal" class="modal-backdrop" style="display: none; position: fixed; inset: 0; background: rgba(15, 23, 42, 0.7); z-index: 9999; align-items: center; justify-content: center; backdrop-filter: blur(4px);">'
new_call_modal = '<div id="call-notes-required-modal" class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="call-notes-modal-title" style="display: none; position: fixed; inset: 0; background: rgba(15, 23, 42, 0.7); z-index: 9999; align-items: center; justify-content: center; backdrop-filter: blur(4px);">'

old_call_title = '<h3 style="margin: 0; font-size: 1.1rem; font-weight: 700; color: #991b1b; letter-spacing: 0.02em;">CALL NOTES REQUIRED</h3>'
new_call_title = '<h3 id="call-notes-modal-title" style="margin: 0; font-size: 1.1rem; font-weight: 700; color: #991b1b; letter-spacing: 0.02em;">CALL NOTES REQUIRED</h3>'

if old_call_modal in base_html:
    base_html = base_html.replace(old_call_modal, new_call_modal, 1)
    base_html = base_html.replace(old_call_title, new_call_title, 1)
    print("base.html call-notes-required-modal ARIA added")
else:
    print("Could not find call notes modal in base.html")

with open(base_path, 'w', encoding='utf-8') as f:
    f.write(base_html)


# 3. Update templates/admin/leads_list.html (ARIA for drawer and modal)
leads_list_path = os.path.join(CRM_DIR, 'templates', 'admin', 'leads_list.html')
with open(leads_list_path, 'r', encoding='utf-8') as f:
    ll_html = f.read()

old_drawer = '<aside class="filter-drawer" id="filterDrawer">'
new_drawer = '<aside class="filter-drawer" id="filterDrawer" role="region" aria-label="Filter Leads">'

old_close_btn = '<button type="button" class="filter-drawer-close" onclick="closeFilterDrawer()">&times;</button>'
new_close_btn = '<button type="button" class="filter-drawer-close" onclick="closeFilterDrawer()" aria-label="Close Filter Drawer">&times;</button>'

old_precheck_modal = '<div id="bulkWhatsAppPreCheckModal" style="display: none; position: fixed; inset: 0; background: rgba(15, 23, 42, 0.65); z-index: 1060; align-items: center; justify-content: center; padding: 20px;">'
new_precheck_modal = '<div id="bulkWhatsAppPreCheckModal" role="dialog" aria-modal="true" aria-labelledby="bulk-whatsapp-modal-title" style="display: none; position: fixed; inset: 0; background: rgba(15, 23, 42, 0.65); z-index: 1060; align-items: center; justify-content: center; padding: 20px;">'

old_precheck_title = 'Bulk WhatsApp Recipient Pre-Check'
new_precheck_title = '<span id="bulk-whatsapp-modal-title">Bulk WhatsApp Recipient Pre-Check</span>'

if old_drawer in ll_html:
    ll_html = ll_html.replace(old_drawer, new_drawer, 1)
if old_close_btn in ll_html:
    ll_html = ll_html.replace(old_close_btn, new_close_btn, 1)
if old_precheck_modal in ll_html:
    ll_html = ll_html.replace(old_precheck_modal, new_precheck_modal, 1)
if old_precheck_title in ll_html and new_precheck_title not in ll_html:
    ll_html = ll_html.replace(old_precheck_title, new_precheck_title, 1)

with open(leads_list_path, 'w', encoding='utf-8') as f:
    f.write(ll_html)
print("leads_list.html ARIA attributes updated")

print("Phase 2, 3, 5, 6 updates applied successfully!")
