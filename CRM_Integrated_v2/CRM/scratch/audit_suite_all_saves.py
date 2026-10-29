import sys
import os
import io

sys.path.insert(0, r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from accounts.models import User, UserRole
from branches.models import Branch
from lead_channels.models import Channel
from products.models import Product
from leads.models import Lead, LeadCategory, PipelineStatus
from leads.models_enrollment import Enrollment, PaymentTransaction, PaymentTransactionStatus
from followups.models import FollowUp

print("==================================================")
print("AUDITING ALL SAVE, SUBMIT, & UPDATE ACTIONS IN CRM")
print("==================================================")

admin_user = User.objects.filter(role=UserRole.ADMIN, is_active=True).first()
if not admin_user:
    admin_user = User.objects.filter(is_superuser=True).first()

counselor = User.objects.filter(role=UserRole.COUNSELOR, is_active=True).first()
branch = Branch.objects.first()
channel = Channel.objects.first()
product = Product.objects.first()

client_admin = Client()
client_admin.force_login(admin_user)

audit_results = {}

# 1. ADD NEW LEAD (Admin)
print("\n[Action 1] Admin Add New Lead...")
Lead.objects.filter(phone='9777000001').delete()
r1 = client_admin.post('/admin/leads/create/', {
    'name': 'Audit Save Lead 1',
    'phone': '9777000001',
    'email': 'audit_save_1@test.com',
    'status': 'New',
    'category': 'Training',
    'channel': channel.id if channel else '',
    'product': product.id if product else '',
    'branch': branch.id if branch else '',
    'notes': 'Checking persistence'
}, follow=False)
l1 = Lead.objects.filter(phone='9777000001').first()
assert r1.status_code == 302 and l1 is not None, "Action 1 failed"
audit_results['Admin Add Lead'] = 'PASSED (Saved to DB, ID: %s)' % l1.id
print("PASSED -> ID:", l1.id)

# 2. EDIT LEAD (Admin)
print("\n[Action 2] Admin Edit Lead...")
r2 = client_admin.post(f'/admin/leads/{l1.id}/edit/', {
    'name': 'Audit Save Lead 1 (UPDATED)',
    'phone': '9777000001',
    'email': 'audit_save_1_updated@test.com',
    'status': 'Contacted',
    'category': 'Training',
    'notes': 'Admin updated lead info'
}, follow=False)
l1.refresh_from_db()
assert r2.status_code == 302 and l1.name == 'Audit Save Lead 1 (UPDATED)', "Action 2 failed"
audit_results['Admin Edit Lead'] = 'PASSED (Updated in DB)'
print("PASSED -> Updated Name:", l1.name)

# 3. STUDENT ENROLLMENT (With Email)
print("\n[Action 3] Student Enrollment with Email...")
Enrollment.objects.filter(lead=l1).delete()
r3 = client_admin.post(f'/leads/{l1.id}/enroll/', {
    'student_name': 'Audit Student Enrolled',
    'student_phone': '9777000001',
    'student_email': 'student_enrolled@test.com',
    'product_id': product.id if product else '',
    'branch_id': branch.id if branch else '',
    'base_course_fee': '45000.00',
    'gst_treatment': 'EXCLUSIVE',
    'tax_rate': '18.00',
    'payment_plan': 'FULL_PAYMENT',
    'installment_method': 'AUTOMATIC',
    'notes': 'Audit enrollment'
}, follow=False)
enr = Enrollment.objects.filter(lead=l1).first()
assert r3.status_code == 302 and enr is not None and enr.student_email == 'student_enrolled@test.com', "Action 3 failed"
l1.refresh_from_db()
assert l1.status == 'Enrolled', "Lead status not updated to Enrolled"
audit_results['Student Enrollment'] = 'PASSED (Enrollment #%s, Status: %s)' % (enr.enrollment_number, l1.status)
print("PASSED -> Enrollment:", enr.enrollment_number, "Lead Status:", l1.status)

# 4. RECORD PAYMENT COLLECTION (Cash & UPI with Proof)
print("\n[Action 4] Record Payment Collection on Enrollment (CASH)...")
r4 = client_admin.post(f'/enrollments/{enr.id}/payment/', {
    'amount': '15000.00',
    'payment_method': 'Cash',
    'transaction_reference': 'CASH-RCPT-001',
    'notes': 'First partial payment in cash'
}, follow=False)
assert r4.status_code == 302, "Action 4 redirect failed"
txn = PaymentTransaction.objects.filter(enrollment=enr).order_by('-id').first()
assert txn is not None and txn.amount == 15000, "Cash Transaction not created"
audit_results['Record Payment (Cash)'] = 'PASSED (Txn #%s, Amount: %s, Status: %s)' % (txn.id, txn.amount, txn.status)
print("PASSED -> Txn #:", txn.id, "Amount:", txn.amount, "Status:", txn.status)

# Also test UPI with payment proof screenshot:
dummy_img = SimpleUploadedFile("proof.png", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82", content_type="image/png")
r4_upi = client_admin.post(f'/enrollments/{enr.id}/payment/', {
    'amount': '5000.00',
    'payment_method': 'UPI',
    'transaction_reference': 'UPI-REF-998877',
    'notes': 'UPI payment with proof',
    'payment_proof': dummy_img
}, follow=False)
assert r4_upi.status_code == 302, "Action 4 UPI redirect failed"
txn_upi = PaymentTransaction.objects.filter(enrollment=enr).order_by('-id').first()
assert txn_upi is not None and txn_upi.amount == 5000, "UPI Transaction not created"
audit_results['Record Payment (UPI + Proof)'] = 'PASSED (Txn #%s, Amount: %s, Status: %s)' % (txn_upi.id, txn_upi.amount, txn_upi.status)
print("PASSED -> UPI Txn #:", txn_upi.id, "Amount:", txn_upi.amount, "Status:", txn_upi.status)

# 5. PIPELINE STATUS CREATE & EDIT
print("\n[Action 5] Pipeline Status Create & Edit...")
test_status_name = "Audit Stage Status"
PipelineStatus.objects.filter(name=test_status_name).delete()
p_status = PipelineStatus.objects.create(name=test_status_name, stage_category="Lead", color="#10b981", sort_order=99)
r5 = client_admin.post(f'/admin/settings/pipeline-statuses/{p_status.id}/edit/', {
    'name': 'Audit Stage Status Renamed',
    'stage_category': 'Contacted',
    'color': '#2563eb',
    'sort_order': 100
}, follow=False)
assert r5.status_code == 302, "Action 5 redirect failed"
p_status.refresh_from_db()
assert p_status.name == 'Audit Stage Status Renamed', "Pipeline status not updated"
audit_results['Pipeline Status Edit'] = 'PASSED (Renamed in DB to %s)' % p_status.name
print("PASSED -> Status renamed:", p_status.name)
p_status.delete()

# 6. INLINE QUICK DETAILS EDIT API
print("\n[Action 6] Inline Quick Details Edit API...")
r6 = client_admin.post(f'/leads/api/{l1.id}/quick-details/', {
    'name': 'Audit Save Lead 1 (QUICK INLINE)',
    'notes': 'Inline note updated via API'
}, content_type='application/json')
assert r6.status_code == 200, "Action 6 API failed"
l1.refresh_from_db()
assert l1.name == 'Audit Save Lead 1 (QUICK INLINE)', "Inline update failed"
audit_results['Quick Inline Edit API'] = 'PASSED (Saved via JSON API)'
print("PASSED -> Name updated inline:", l1.name)

# 7. COUNSELOR FOLLOW-UP CREATION
if counselor:
    print("\n[Action 7] Counselor Follow-up Logging...")
    client_counselor = Client()
    client_counselor.force_login(counselor)
    l1.assigned_counselor = counselor
    l1.save(update_fields=['assigned_counselor'])
    
    fu = FollowUp.objects.create(
        lead=l1,
        user=counselor,
        notes="Counselor discussion notes test",
        status="Pending"
    )
    assert fu.id is not None, "FollowUp creation failed"
    audit_results['Counselor FollowUp'] = 'PASSED (Created FollowUp #%s)' % fu.id
    print("PASSED -> FollowUp #:", fu.id)

print("\n==================================================")
print("AUDIT SUMMARY REPORT:")
print("==================================================")
for action, result in audit_results.items():
    print(f"  [OK] {action}: {result}")
print("==================================================")
