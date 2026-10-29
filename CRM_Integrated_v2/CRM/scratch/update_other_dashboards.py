import os

BASE_DIR = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM"

# 1. Update manager_dashboard/dashboard.html
mgr_path = os.path.join(BASE_DIR, "templates", "manager_dashboard", "dashboard.html")
with open(mgr_path, "r", encoding="utf-8") as f:
    mgr_html = f.read()

mgr_html = mgr_html.replace(
    """<div class="kpi-grid tp-stagger-container" style="grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 16px; margin-bottom: 24px;">""",
    """<div class="kpi-grid tp-kpi-grid-6 tp-stagger-container" style="gap: 12px; margin-bottom: 20px;">"""
)

with open(mgr_path, "w", encoding="utf-8") as f:
    f.write(mgr_html)
print("SUCCESS: Updated manager_dashboard/dashboard.html")

# 2. Update branch_head_dashboard/dashboard.html
bh_path = os.path.join(BASE_DIR, "templates", "branch_head_dashboard", "dashboard.html")
with open(bh_path, "r", encoding="utf-8") as f:
    bh_html = f.read()

bh_html = bh_html.replace(
    """<div class="kpi-grid tp-stagger-container" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px;">""",
    """<div class="kpi-grid tp-kpi-grid-6 tp-stagger-container" style="gap: 12px; margin-bottom: 20px;">"""
)

with open(bh_path, "w", encoding="utf-8") as f:
    f.write(bh_html)
print("SUCCESS: Updated branch_head_dashboard/dashboard.html")
