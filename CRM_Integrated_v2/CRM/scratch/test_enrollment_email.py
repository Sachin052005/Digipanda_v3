import sys
import os

sys.path.insert(0, r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.test import Client
from accounts.models import User
from branches.models import Branch
from products.models import Product
from leads.models import Lead, LeadCategory
from leads.models_enrollment import Enrollment

admin_user = User.objects.filter(role='ADMIN').first()
if not admin_user:
    admin_user = User.objects.filter(is_superuser=True).first()

client = Client()
client.force_login(admin_user)

branch, _ = Branch.objects.get_or_create(name="T. Nagar", defaults={'code': 'TN', 'status': 'Active'})
product, _ = Product.objects.get_or_create(name="Python Full Stack", defaults={'status': 'Active', 'price': 35000})

# Create a test lead
test_lead = Lead.objects.create(
    name="Enrollment Test Candidate",
    phone="9876500001",
    email="",
    category=LeadCategory.TRAINING,
    branch=branch,
    product=product,
    status="New"
)
print("Created test lead for enrollment:", test_lead.id)

# Try enrolling with an email
enroll_post = {
    'student_name': 'Enrollment Test Candidate',
    'student_phone': '9876500001',
    'student_email': 'candidate.new@digipanda.test',
    'product_id': product.id,
    'branch_id': branch.id,
    'base_course_fee': '30000.00',
    'gst_treatment': 'EXCLUSIVE',
    'tax_rate': '18.00',
    'payment_plan': 'FULL_PAYMENT',
    'installment_method': 'AUTOMATIC',
    'notes': 'Test enrollment'
}

response = client.post(f'/leads/{test_lead.id}/enroll/', enroll_post, follow=False)
print("Enrollment POST status code:", response.status_code)
if response.status_code == 302:
    print("Redirected to:", response.url)
    enr = Enrollment.objects.filter(lead=test_lead).first()
    print("Enrollment created:", enr)
    if enr:
        print("Enrollment number:", enr.enrollment_number, "email:", enr.student_email)
        print("Lead email before refresh:", repr(test_lead.email))
        test_lead.refresh_from_db()
        print("Refreshed lead email in DB:", repr(test_lead.email))
        print("Lead status:", test_lead.status)
else:
    print("Failed to redirect! Checking messages or content...")
    print("Content preview:", response.content.decode('utf-8')[:600])

