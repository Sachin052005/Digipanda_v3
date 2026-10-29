import os
import re

CRM_DIR = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM'

dashboard_views = [
    ('admin_dashboard', os.path.join(CRM_DIR, 'reports', 'views.py')),
    ('telecaller_dashboard', os.path.join(CRM_DIR, 'telecallers', 'views.py')),
    ('counselor_dashboard', os.path.join(CRM_DIR, 'counselors', 'views.py')),
    ('manager_dashboard', os.path.join(CRM_DIR, 'managers', 'views.py')),
    ('accountant_dashboard', os.path.join(CRM_DIR, 'leads', 'views_accountant.py')),
    ('branch_head_dashboard', os.path.join(CRM_DIR, 'branch_heads', 'views.py')),
    ('admin_leads_list', os.path.join(CRM_DIR, 'leads', 'views.py')),
]

print("=== DEEP ROLE DASHBOARD & VIEW PARAMETERS AUDIT ===")
for name, fpath in dashboard_views:
    if not os.path.exists(fpath):
        print(f"File missing: {fpath}")
        continue
    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
        code = f.read()
    pattern = r'def\s+' + name + r'\s*\([^)]*\):.*?(?=\ndef\s+[a-zA-Z0-9_]+\s*\([^)]*\):|\Z)'
    m = re.search(pattern, code, re.DOTALL)
    if m:
        body = m.group(0)
        get_params = set(re.findall(r"request\.GET\.get\(\s*['\"]([^'\"]+)['\"]", body))
        date_params = {p for p in get_params if any(k in p.lower() for k in ['date', 'from', 'to', 'range', 'period', 'day', 'month', 'year'])}
        template_m = re.findall(r"render\(\s*request\s*,\s*['\"]([^'\"]+)['\"]", body)
        print(f"\n[View: {name}] ({os.path.relpath(fpath, CRM_DIR)})")
        print(f"  Templates rendered: {template_m}")
        print(f"  Date Parameters: {sorted(list(date_params))}")
        print(f"  All GET parameters: {sorted(list(get_params))}")
    else:
        print(f"View {name} not found in {fpath}")
