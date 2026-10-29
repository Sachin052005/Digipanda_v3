import sys
import os

sys.path.insert(0, r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.test import Client
from accounts.models import User
from branches.models import Branch
from lead_channels.models import Channel
from products.models import Product
from leads.models import Lead

admin_user = User.objects.filter(role='ADMIN').first()
if not admin_user:
    admin_user = User.objects.filter(is_superuser=True).first()

client = Client()
client.force_login(admin_user)

branch = Branch.objects.first()
channel = Channel.objects.first()
product = Product.objects.first()

# Delete existing test lead if exists
Lead.objects.filter(phone='9998887771').delete()

print("1. Testing Add New Lead (/admin/leads/create/)...")
# Note that in admin/lead_create.html:
# name, phone, email, alternate_phone, channel, product, status, notes
# BUT NO branch, NO category, NO assigned_manager, NO assigned_telecaller in the template!
post_data = {
    'name': 'Test New Lead Audit',
    'phone': '9998887771',
    'email': 'audit_test_lead_1@example.com',
    'status': 'New',
    'channel': channel.id if channel else '',
    'product': product.id if product else '',
    'notes': 'Test lead created via audit script'
}

response = client.post('/admin/leads/create/', post_data, follow=False)
print("Add Lead Status Code:", response.status_code)
if response.status_code == 302:
    print("Redirected to:", response.url)
    created = Lead.objects.filter(phone='9998887771').first()
    print("Created lead in DB:", created)
    if created:
        print("Created lead details - ID:", created.id, "Branch:", created.branch, "Status:", created.status, "Sales Head:", created.assigned_sales_head, "Telecaller:", created.assigned_telecaller)
else:
    print("Failed to redirect! Checking form errors...")
    if hasattr(response, 'context') and response.context and 'form' in response.context:
        print("Form errors:", response.context['form'].errors)
    else:
        print("Response content:", response.content.decode('utf-8')[:500])
