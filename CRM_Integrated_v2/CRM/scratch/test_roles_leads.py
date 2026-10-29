import sys
import os

sys.path.insert(0, r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.test import Client
from accounts.models import User, UserRole
from branches.models import Branch
from lead_channels.models import Channel
from products.models import Product
from leads.models import Lead, LeadCategory

# Setup roles
branch = Branch.objects.first()
manager = User.objects.filter(role=UserRole.SALES_HEAD, is_active=True).first()
telecaller = User.objects.filter(role=UserRole.TELECALLER, is_active=True).first()

print("Testing Manager and Telecaller lead creation and editing...")

# Clean test data
Lead.objects.filter(phone__in=['9888111222', '9888111333']).delete()

if manager:
    client_mgr = Client()
    client_mgr.force_login(manager)
    print("Testing Manager Create Lead (/manager/leads/create/)...")
    res = client_mgr.post('/manager/leads/create/', {
        'name': 'Manager Created Lead',
        'phone': '9888111222',
        'email': 'mgr_lead@example.com',
        'status': 'New',
        'notes': 'Created by sales head'
    }, follow=False)
    print("Manager Create Status:", res.status_code)
    assert res.status_code in [200, 302]
    lead_mgr = Lead.objects.filter(phone='9888111222').first()
    print("Manager Lead in DB:", lead_mgr)
    assert lead_mgr is not None, "Manager lead not persisted"

    print("Testing Manager Edit Lead (/manager/leads/<pk>/edit/)...")
    res_edit = client_mgr.post(f'/manager/leads/{lead_mgr.pk}/edit/', {
        'status': 'Contacted',
        'notes': 'Updated notes by manager'
    }, follow=False)
    print("Manager Edit Status:", res_edit.status_code)
    lead_mgr.refresh_from_db()
    assert lead_mgr.status == 'Contacted'
    print("Manager Edit Lead Success!")

if telecaller:
    client_tc = Client()
    client_tc.force_login(telecaller)
    print("Testing Telecaller Create Lead (/telecaller/leads/create/)...")
    res_tc = client_tc.post('/telecaller/leads/create/', {
        'name': 'Telecaller Created Lead',
        'phone': '9888111333',
        'email': 'tc_lead@example.com',
        'notes': 'Created by telecaller'
    }, follow=False)
    print("Telecaller Create Status:", res_tc.status_code)
    assert res_tc.status_code in [200, 302]
    lead_tc = Lead.objects.filter(phone='9888111333').first()
    print("Telecaller Lead in DB:", lead_tc)
    assert lead_tc is not None, "Telecaller lead not persisted"

    print("Testing Telecaller Edit Lead (/telecaller/leads/<pk>/edit/)...")
    res_tc_edit = client_tc.post(f'/telecaller/leads/{lead_tc.pk}/edit/', {
        'status': 'Follow-up',
        'notes': 'Telecaller called candidate'
    }, follow=False)
    print("Telecaller Edit Status:", res_tc_edit.status_code)
    lead_tc.refresh_from_db()
    assert lead_tc.status == 'Follow-up'
    print("Telecaller Edit Lead Success!")

print("ALL MANAGER & TELECALLER LEAD WORKFLOWS PASSED!")
