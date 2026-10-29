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
from managers.views import manager_dashboard

User = get_user_model()

mgr_user, _ = User.objects.get_or_create(
    username="manager_test_user_ui",
    defaults={"role": "SALES_HEAD", "is_staff": True}
)

rf = RequestFactory()
request = rf.get("/manager/dashboard/")
request.user = mgr_user
request.session = {}
setattr(request, '_messages', FallbackStorage(request))

print("Rendering manager_dashboard view...")
response = manager_dashboard(request)
assert response.status_code == 200, f"Expected 200, got {response.status_code}"
content = response.content.decode('utf-8')

checks = [
    ("app-header", "app-header class present"),
    ("header-left", "header-left zone present"),
    ("header-center", "header-center zone present"),
    ("header-right", "header-right zone present"),
    ("tp-kpi-grid-6", "Executive 6-KPI grid present"),
    ("Sales Head Workspace", "Sales Head title present"),
    ("DigipandaCRM", "DigipandaCRM branding present"),
]

all_passed = True
for needle, desc in checks:
    if needle in content:
        print(f"PASS: {desc}")
    else:
        print(f"FAIL: {desc}")
        all_passed = False

if all_passed:
    print("\nALL MANAGER DASHBOARD CHECKS PASSED!")
else:
    print("\nSOME CHECKS FAILED!")
    sys.exit(1)
