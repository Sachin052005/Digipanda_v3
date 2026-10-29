import sys
import os

sys.path.insert(0, r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.test import Client
from accounts.models import User, UserRole
from leads.models_enrollment import PaymentTransaction, PaymentTransactionStatus

admin_user = User.objects.filter(role=UserRole.ADMIN, is_active=True).first()
accountant = User.objects.filter(role=UserRole.ACCOUNTANT, is_active=True).first()
approver = accountant if accountant else admin_user

client = Client()
client.force_login(approver)

txn = PaymentTransaction.objects.filter(payment_method='UPI', status=PaymentTransactionStatus.PENDING_VERIFICATION).order_by('-id').first()
assert txn is not None, "Pending UPI transaction not found!"

print("Testing Accountant Payment Approval for Txn #:", txn.id)
res = client.post(f'/accountant/verification/{txn.id}/approve/', follow=False)
print("Approval Status Code:", res.status_code)

txn.refresh_from_db()
print("Transaction Status after approval:", txn.status)
print("Reviewed by:", txn.reviewed_by)
print("Reviewed at:", txn.reviewed_at)

assert txn.status == PaymentTransactionStatus.APPROVED, "Transaction was not approved!"
print("ACCOUNTANT PAYMENT APPROVAL PASSED SUCCESSFULLY!")

