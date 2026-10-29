import sys
import os

sys.path.insert(0, r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.test import Client
from accounts.models import User

admin_user = User.objects.filter(role='ADMIN').first()
if not admin_user:
    admin_user = User.objects.filter(is_superuser=True).first()

client = Client()
client.force_login(admin_user)

print("Testing admin_leads_list view rendering with date parameters via Test Client...")
response = client.get('/admin/leads/?date_from=2026-10-01&date_to=2026-10-29')
assert response.status_code == 200, f"Expected 200, got {response.status_code}"
content = response.content.decode('utf-8')

# Verify date_from and date_to inputs are present
assert 'name="date_from"' in content, "date_from missing"
assert 'name="date_to"' in content, "date_to missing"
assert 'tp-smart-date-container' in content, "tp-smart-date-container missing"
assert 'smart-calendar.js?v=20261029_single_month' in content, "Cache-busted smart-calendar.js missing"
assert 'design-system.css?v=20261029_single_month' in content, "Cache-busted design-system.css missing"

# Check static/js/smart-calendar.js contents
with open(r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\static\js\smart-calendar.js', 'r', encoding='utf-8') as f:
    js_code = f.read()

assert 'singleMonth' in js_code, "singleMonth element id missing from JS"
assert 'month2' not in js_code, "Old month2 element found in JS"
assert 'renderCalendarMonth' in js_code, "renderCalendarMonth function missing"
assert 'tp-nav-prev' in js_code, "Previous button missing"
assert 'tp-nav-next' in js_code, "Next button missing"

# Check CSS
with open(r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\static\css\design-system.css', 'r', encoding='utf-8') as f:
    css_code = f.read()

assert 'width: 475px;' in css_code, "Compact single-month width missing in design-system.css"
assert '.tp-smart-date-single-view' in css_code, ".tp-smart-date-single-view missing in design-system.css"

print("ALL SINGLE-MONTH CALENDAR CHECKS PASSED SUCCESSFULLY!")
