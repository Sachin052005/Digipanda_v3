import sys
import os

sys.path.insert(0, r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from accounts.models import User
from branches.models import Branch
from products.models import Product
from leads.models import Lead, LeadCategory
from leads.services_enrollment import create_or_update_enrollment

admin_user = User.objects.filter(role='ADMIN').first()
if not admin_user:
    admin_user = User.objects.filter(is_superuser=True).first()

branch = Branch.objects.first()
product = Product.objects.first()

test_lead = Lead.objects.filter(name="Enrollment Test Candidate").first()

data = {
    'student_name': 'Enrollment Test Candidate',
    'student_phone': '9876500001',
    'student_email': 'candidate.new@digipanda.test',
    'product': product,
    'branch': branch,
    'base_course_fee': '30000.00',
    'gst_treatment': 'EXCLUSIVE',
    'tax_rate': '18.00',
    'payment_plan': 'FULL_PAYMENT',
    'installment_method': 'AUTOMATIC',
    'notes': 'Test enrollment'
}

try:
    saved = create_or_update_enrollment(test_lead, admin_user, data)
    print("SUCCESS! Enrollment:", saved)
except Exception as e:
    import traceback
    print("ENROLLMENT FAILED WITH EXCEPTION:")
    traceback.print_exc()

