import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.test import RequestFactory
from leads.models_enrollment import PaymentTransaction, PaymentTransactionStatus
from leads.views_enrollment import generate_receipt_pdf, get_receipt_context
from services.email_service import send_template_email

recipient = "tamilselvan2002a@gmail.com"
print(f"Preparing sample email with official DigiPanda Tax Invoice & Signature to: {recipient}...")

txn = PaymentTransaction.objects.filter(
    status__in=[PaymentTransactionStatus.APPROVED, PaymentTransactionStatus.SUCCESS]
).select_related('enrollment', 'enrollment__product', 'enrollment__branch').first()

if not txn:
    txn = PaymentTransaction.objects.select_related('enrollment', 'enrollment__product', 'enrollment__branch').first()
    if txn:
        txn.status = PaymentTransactionStatus.APPROVED
        txn.save(update_fields=['status'])

if not txn:
    print("Error: No PaymentTransaction found.")
    sys.exit(1)

factory = RequestFactory()
req = factory.get('/')
ctx = get_receipt_context(req, txn)

# Ensure recipient is set
ctx['customer_email'] = recipient

# Inline images (such as QR code)
inline_images = []
qr_png_bytes = ctx.get('qr_png_bytes')
if qr_png_bytes:
    inline_images.append(('receipt_qr_code', qr_png_bytes, 'image/png'))

# Generate official PDF attachment with embedded Shashi signature
pdf_bytes = generate_receipt_pdf(ctx)
if not pdf_bytes:
    print("Error: Failed to render PDF.")
    sys.exit(1)

filename = f"DigiPanda_Tax_Invoice_{ctx['invoice_number']}.pdf"
attachments = [
    (filename, pdf_bytes, "application/pdf")
]

subject = f"Tax Invoice {ctx['invoice_number']} — DigiPanda Fee Receipt & Verification"

print(f"Signature path in context: {ctx.get('signature_path')}")
print(f"Signatory label: {ctx.get('signatory_label')}")
print(f"Company name: {ctx.get('invoice_config', {}).get('company_name')}")
print(f"Dispatching email via SMTP to {recipient} with attachment {filename} ({len(pdf_bytes)} bytes)...")

success, msg = send_template_email(
    subject=subject,
    recipient=recipient,
    html_template='emails/payment_receipt.html',
    text_template='emails/payment_receipt.txt',
    context=ctx,
    attachments=attachments,
    inline_images=inline_images
)

print(f"Result: success={success}, msg={msg}")
if success:
    print("Sample email sent successfully to tamilselvan2002a@gmail.com!")
else:
    print("Failed to send sample email.")
    sys.exit(1)
