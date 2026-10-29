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
from leads.forms import AdminLeadForm

channel = Channel.objects.first()
product = Product.objects.first()

post_data = {
    'name': 'Test New Lead Audit',
    'phone': '9998887771',
    'email': 'audit_test_lead_1@example.com',
    'status': 'New',
    'channel': channel.id if channel else '',
    'product': product.id if product else '',
    'notes': 'Test lead created via audit script'
}

form = AdminLeadForm(data=post_data)
print("Is form valid?", form.is_valid())
if not form.is_valid():
    print("FORM ERRORS:", form.errors.as_json())

