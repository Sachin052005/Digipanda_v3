import os
import sys

# Setup Django environment
sys.path.insert(0, r"d:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

import inspect
from accounts.models import UserRole
from leads.qualification import generate_smart_precall_pitch
from leads import views_walkin

print("=" * 70)
print("PART 2: RBAC, XSS & FILE UPLOAD AUDIT")
print("=" * 70)

# TEST 1: Inspect Decorators on Walkin Admin Views
print("\n--- TEST 1: Decorator Audit on Walkin Admin Views ---")
walkin_admin_funcs = [
    ('admin_walkin_forms_list', views_walkin.admin_walkin_forms_list),
    ('admin_walkin_form_create', views_walkin.admin_walkin_form_create),
    ('admin_walkin_form_edit', views_walkin.admin_walkin_form_edit),
    ('admin_walkin_form_duplicate', views_walkin.admin_walkin_form_duplicate),
    ('admin_walkin_form_toggle_status', views_walkin.admin_walkin_form_toggle_status),
    ('admin_walkin_form_delete', views_walkin.admin_walkin_form_delete),
]

for name, func in walkin_admin_funcs:
    src = inspect.getsource(func)
    first_lines = src.split("def ")[0]
    has_admin_check = "admin_required" in first_lines or "role_required" in first_lines or "is_admin_user" in src[:300]
    has_login_required = "login_required" in first_lines
    print(f"Function {name}:")
    print(f"  - @login_required: {has_login_required}")
    print(f"  - @admin_required / RBAC check: {has_admin_check}")
    if not has_admin_check:
        print(f"  -> [VULNERABILITY] {name} only checks login; any authenticated role (Telecaller, Counselor, Receptionist) can execute it!")

# TEST 2: Stored XSS Inspection in Smart Pre-Call Pitch
print("\n--- TEST 2: Stored XSS in Smart Pre-Call Pitch ---")
class MockLead:
    name = '<script>alert("XSS_IN_LEAD_NAME")</script>'
    custom_fields = {'working_status': '<img src=x onerror=alert("XSS_STATUS")>'}
    product = None
    branch = None

pitch = generate_smart_precall_pitch(MockLead())
print(f"Generated Pitch Output:\n  {pitch}")
if "<script>" in pitch or "<img" in pitch:
    print("  -> [VULNERABILITY] Confirmed Stored XSS: unescaped payload in pitch, rendered with |safe in lead_detail_view.html:231!")

# TEST 3: Logo Upload Validation in admin_walkin_form_edit
print("\n--- TEST 3: File Upload Validation in admin_walkin_form_edit ---")
src_edit = inspect.getsource(views_walkin.admin_walkin_form_edit)
has_ext_check = any(k in src_edit for k in ['ALLOWED_EXTENSIONS', '.endswith', 'split(\'.\')', 'magic', 'imghdr', 'PIL'])
print(f"Extension or MIME type validation present in admin_walkin_form_edit: {has_ext_check}")
if not has_ext_check:
    print("  -> [VULNERABILITY] Direct assignment form_obj.logo = request.FILES['logo'] without file extension or image magic-byte verification!")

print("\n" + "=" * 70)
print("EVALUATION FINISHED")
print("=" * 70)
