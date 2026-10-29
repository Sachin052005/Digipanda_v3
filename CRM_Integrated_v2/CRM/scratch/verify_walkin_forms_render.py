import os
import sys

extra_site = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\.venv\Lib\site-packages"
if os.path.exists(extra_site) and extra_site not in sys.path:
    sys.path.insert(0, extra_site)

sys.path.insert(0, r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
os.environ['DB_ENGINE'] = 'django.db.backends.sqlite3'
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

if "check" not in sys.argv:
    sys.argv.append("check")

import django
django.setup()

from django.test import Client
from accounts.models import User, UserRole

client = Client()
admin_user, _ = User.objects.get_or_create(
    username="test_admin_walkin_test",
    defaults={'role': UserRole.ADMIN, 'is_staff': True, 'is_active': True}
)
admin_user.role = UserRole.ADMIN
admin_user.is_staff = True
admin_user.save()

client.force_login(admin_user)
resp = client.get('/admin/walkin-forms/')
print(f"Status Code: {resp.status_code}")
if resp.status_code == 200:
    print("SUCCESS: /admin/walkin-forms/ rendered cleanly with 200 OK!")
    if "Open Live Form" in resp.content.decode('utf-8'):
        print("Verified 'Open Live Form' link rendered without syntax errors.")
else:
    print("FAILED with status:", resp.status_code)
