import os
import sys

extra_site = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\.venv\Lib\site-packages"
if os.path.exists(extra_site) and extra_site not in sys.path:
    sys.path.insert(0, extra_site)

sys.path.insert(0, r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
os.environ['DB_ENGINE'] = 'django.db.backends.sqlite3'
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

if "check" not in sys.argv and "test" not in sys.argv:
    sys.argv.append("check")

import django
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from reports.views import admin_dashboard

User = get_user_model()

admin_user, _ = User.objects.get_or_create(
    username="admin_test_user_ui",
    defaults={"role": "ADMIN", "is_staff": True, "is_superuser": True}
)

rf = RequestFactory()
request = rf.get("/admin/dashboard/")
request.user = admin_user
request.session = {}
setattr(request, '_messages', FallbackStorage(request))

print("Rendering admin_dashboard view...")
response = admin_dashboard(request)
assert response.status_code == 200, f"Expected 200, got {response.status_code}"
content = response.content.decode('utf-8')

checks = [
    ("app-header", "app-header class present"),
    ("header-left", "header-left zone present"),
    ("header-center", "header-center zone present"),
    ("header-right", "header-right zone present"),
    ("tp-search-trigger-btn", "Quick search trigger present"),
    ("tp-filter-bar", "Compact filter bar present"),
    ("tp-compact-filter-grid", "Compact filter grid present"),
    ("tp-kpi-grid-7", "Executive 7-KPI grid present"),
    ("tp-kpi-grid-5", "Revenue 5-KPI grid present"),
    ("Organization Overview", "Dashboard title present"),
    ("DigipandaCRM", "DigipandaCRM branding present"),
    ("adminStatusChart", "Status chart canvas present"),
    ("adminTelecallerChart", "Telecaller chart canvas present"),
]

all_passed = True
for needle, desc in checks:
    if needle in content:
        print(f"PASS: {desc}")
    else:
        print(f"FAIL: {desc}")
        all_passed = False

if all_passed:
    print("\nALL DASHBOARD RENDER CHECKS PASSED SUCCESSFULLY!")
else:
    print("\nSOME CHECKS FAILED!")
    sys.exit(1)
