import sys
import os

sys.path.insert(0, r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from leads.models_enrollment import PaymentTransaction

latest_upi = PaymentTransaction.objects.filter(payment_method='UPI').order_by('-id').first()
print("Latest UPI Transaction ID:", latest_upi.id)
print("Amount:", str(latest_upi.amount))
print("Status:", latest_upi.status)
print("Receipt:", latest_upi.receipt_number)
print("Proof file:", bool(latest_upi.payment_proof))

