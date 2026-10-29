import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.test import RequestFactory
from leads.models import PaymentTransaction
from leads.views_enrollment import generate_receipt_pdf, get_receipt_context
from services.email_service import send_template_email

recipient = "tamilselvan2002a@gmail.com"
print(f"Preparing Tax Invoice test email to: {recipient}...")

txn = PaymentTransaction.objects.select_related('enrollment', 'enrollment__product', 'enrollment__branch').first()
if not txn:
    print("No payment transaction found in database.")
    sys.exit(1)

factory = RequestFactory()
req = factory.get('/')
ctx = get_receipt_context(req, txn)

# Override student name / recipient display for test if desired, or keep actual transaction
ctx['customer_email'] = recipient

# Generate PDF attachment
pdf_bytes = generate_receipt_pdf(ctx)
if not pdf_bytes:
    print("Failed to generate PDF attachment.")
    sys.exit(1)

filename = f"TechPanda_Tax_Invoice_{ctx['invoice_number']}.pdf"
attachments = [
    (filename, pdf_bytes, "application/pdf")
]

subject = f"Tax Invoice — {ctx['invoice_number']} — TechPanda"

print(f"Dispatching email via SMTP to {recipient} with attachment {filename} ({len(pdf_bytes)} bytes)...")
success, msg = send_template_email(
    subject=subject,
    recipient=recipient,
    html_template='emails/payment_receipt.html',
    text_template='emails/payment_receipt.txt',
    context=ctx,
    attachments=attachments
)

print(f"Result: success={success}, msg={msg}")
if success:
    print("Test email sent successfully!")
else:
    print("Test email sending failed!")
