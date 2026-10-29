import sys
import os
import io
from PIL import Image

sys.path.insert(0, r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from accounts.models import User
from leads.models_enrollment import Enrollment, PaymentTransaction
from django.contrib.messages import get_messages

admin_user = User.objects.filter(role='ADMIN').first()
client = Client()
client.force_login(admin_user)

enr = Enrollment.objects.order_by('-id').first()

# Generate real valid image
im = Image.new('RGB', (100, 100), color='blue')
buf = io.BytesIO()
im.save(buf, format='PNG')
buf.seek(0)

real_img = SimpleUploadedFile("real_proof.png", buf.read(), content_type="image/png")

res = client.post(f'/enrollments/{enr.id}/payment/', {
    'amount': '5000.00',
    'payment_method': 'UPI',
    'transaction_reference': 'UPI-REF-998877',
    'notes': 'UPI payment with real image proof',
    'payment_proof': real_img
}, follow=True)

messages = [str(m) for m in get_messages(res.wsgi_request)]
print("Messages:", messages)
latest_txn = PaymentTransaction.objects.filter(enrollment=enr, payment_method='UPI').order_by('-id').first()
print("Latest UPI Txn:", latest_txn)
if latest_txn:
    print("UPI Payment Success! Txn ID:", latest_txn.id, "Status:", latest_txn.status)

