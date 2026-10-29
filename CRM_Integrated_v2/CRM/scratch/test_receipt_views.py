import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.test import RequestFactory
from accounts.models import User
from leads.models import PaymentTransaction
from leads.views_enrollment import enrollment_receipt_view, enrollment_receipt_pdf_view

admin_user = User.objects.filter(is_superuser=True).first() or User.objects.filter(role='ADMIN').first()
txn = PaymentTransaction.objects.first()

print(f"Testing views with admin user: {admin_user.username}, txn: #{txn.receipt_number}")

factory = RequestFactory()

from django.contrib.sessions.middleware import SessionMiddleware

def add_session_to_request(request):
    """Annotate a request object with a session."""
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)
    request.session.save()
    return request

# 1. Test HTML view
req_html = factory.get(f'/enrollments/receipt/{txn.id}/')
req_html.user = admin_user
add_session_to_request(req_html)
resp_html = enrollment_receipt_view(req_html, txn.id)
assert resp_html.status_code == 200, f"HTML view failed with status {resp_html.status_code}"
content = resp_html.content.decode('utf-8')
assert "TAX INVOICE" in content
assert "ORIGINAL FOR RECIPIENT" in content
assert "HDFC0000141" in content
assert "TechPanda" in content
print(f"  PASS: HTML View returned 200 ({len(content)} characters)")

# 2. Test PDF download view
req_pdf = factory.get(f'/enrollments/receipt/{txn.id}/pdf/')
req_pdf.user = admin_user
add_session_to_request(req_pdf)
resp_pdf = enrollment_receipt_pdf_view(req_pdf, txn.id)
assert resp_pdf.status_code == 200, f"PDF view failed with status {resp_pdf.status_code}"
assert resp_pdf['Content-Type'] == 'application/pdf', f"Unexpected Content-Type: {resp_pdf['Content-Type']}"
assert resp_pdf.content.startswith(b'%PDF'), "PDF content did not start with %PDF!"
print(f"  PASS: PDF Direct Endpoint returned 200 ({len(resp_pdf.content)} bytes)")

# 3. Test ?download=pdf query param
req_dl = factory.get(f'/enrollments/receipt/{txn.id}/?download=pdf')
req_dl.user = admin_user
add_session_to_request(req_dl)
resp_dl = enrollment_receipt_view(req_dl, txn.id)
assert resp_dl.status_code == 200
assert resp_dl['Content-Type'] == 'application/pdf'
assert resp_dl.content.startswith(b'%PDF')
print(f"  PASS: HTML View with ?download=pdf returned PDF ({len(resp_dl.content)} bytes)")

print("\nALL RECEIPT VIEW INTEGRATION TESTS PASSED!")
