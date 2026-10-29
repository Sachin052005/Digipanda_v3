import sys
import os

sys.path.insert(0, r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.test import Client
from accounts.models import User
from leads.models import Lead

admin_user = User.objects.filter(role='ADMIN').first()
if not admin_user:
    admin_user = User.objects.filter(is_superuser=True).first()

client = Client()
client.force_login(admin_user)

lead = Lead.objects.filter(phone='9998887771').first()
assert lead is not None, "Lead 9998887771 not found!"

print("Testing Edit Lead for lead ID:", lead.id)
edit_post_data = {
    'name': 'Test New Lead - EDITED NAME',
    'phone': '9998887771',
    'email': 'audit_test_lead_EDITED@example.com',
    'status': 'Contacted',
    'notes': 'Notes have been updated during audit edit test'
}

response = client.post(f'/admin/leads/{lead.id}/edit/', edit_post_data, follow=False)
print("Edit Lead Status Code:", response.status_code)
if response.status_code == 302:
    print("Redirected to:", response.url)
    lead.refresh_from_db()
    print("Updated Lead in DB:")
    print("  Name:", lead.name)
    print("  Email:", lead.email)
    print("  Status:", lead.status)
    print("  Notes:", lead.notes)
    assert lead.name == 'Test New Lead - EDITED NAME'
    assert lead.email == 'audit_test_lead_EDITED@example.com'
    assert lead.status == 'Contacted'
    print("EDIT LEAD VERIFIED SUCCESSFULLY!")
else:
    print("Failed to redirect! Checking response...")
    print(response.content.decode('utf-8')[:600])

