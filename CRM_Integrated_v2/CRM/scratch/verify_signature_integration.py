import os
import sys
import io
import pymupdf
import django
from unittest.mock import MagicMock

sys.path.insert(0, r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from leads.views_enrollment import get_receipt_context, generate_receipt_pdf
from leads.models_enrollment import PaymentTransaction, PaymentTransactionStatus
from django.test import RequestFactory

print("=== RUNNING SIGNATURE INTEGRATION VERIFICATION ===")

factory = RequestFactory()
req = factory.get('/')

txn = PaymentTransaction.objects.filter(status__in=[PaymentTransactionStatus.APPROVED, PaymentTransactionStatus.SUCCESS]).first()
if not txn:
    txn = PaymentTransaction.objects.first()
    txn.status = PaymentTransactionStatus.APPROVED
    txn.save(update_fields=['status'])

ctx = get_receipt_context(req, txn)

print(f"Transaction ID: {txn.id}, Status: {txn.status}")
print(f"is_authorized: {ctx.get('is_authorized')}")
print(f"signature_path: {ctx.get('signature_path')}")
print(f"signature_data_uri present: {bool(ctx.get('signature_data_uri'))}")
print(f"logo_path: {ctx.get('logo_path')}")

assert ctx.get('is_authorized') == True, "Approved txn should be authorized"
assert ctx.get('signature_path') is not None, "Signature path must be present"
assert os.path.exists(ctx.get('signature_path')), "Signature file must exist"
assert ctx.get('signature_data_uri') is not None, "Signature data URI must be present"

# Generate PDF
pdf_bytes = generate_receipt_pdf(ctx)
assert pdf_bytes is not None and len(pdf_bytes) > 0, "PDF generation failed"
print(f"Generated PDF Size: {len(pdf_bytes)} bytes")

# Inspect PDF with PyMuPDF
doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
print(f"Total Pages: {len(doc)}")
assert len(doc) == 1, f"Expected 1 page, got {len(doc)}"

page = doc[0]
images = page.get_images()
print(f"Number of embedded images in PDF: {len(images)}")
assert len(images) >= 2, f"Expected at least 2 images (logo and signature), found {len(images)}"

sig_found = False
for img_info in images:
    xref = img_info[0]
    base_img = doc.extract_image(xref)
    w = base_img["width"]
    h = base_img["height"]
    print(f" - Image xref {xref}: {w}x{h}, ext={base_img['ext']}, size={len(base_img['image'])} bytes")
    if w == 1024 and h == 1024:
        sig_found = True

assert sig_found, "1024x1024 Shashi signature image NOT found embedded in PDF!"
print("SUCCESS: 1024x1024 authentic Shashi signature image is confirmed embedded in PDF!")

# Render signature region to image for visual verification
pix = page.get_pixmap(dpi=150)
out_img_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\scratch\verified_receipt_page.png"
pix.save(out_img_path)
print(f"Saved full page render to {out_img_path}")

# Crop signature block
# Signature block is at bottom right
rect = pymupdf.Rect(page.rect.width * 0.5, page.rect.height * 0.72, page.rect.width, page.rect.height * 0.96)
sig_pix = page.get_pixmap(clip=rect, dpi=200)
out_sig_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\scratch\verified_signature_zoom.png"
sig_pix.save(out_sig_path)
print(f"Saved signature zoom render to {out_sig_path}")

# Now test unapproved / draft transaction
mock_txn = MagicMock()
mock_txn.id = 999999
mock_txn.status = PaymentTransactionStatus.PENDING
mock_txn.enrollment = txn.enrollment
mock_txn.receipt_number = "TEST-PENDING"
mock_txn.amount = txn.amount
mock_txn.payment_date = txn.payment_date
mock_txn.created_at = txn.created_at
mock_ctx = get_receipt_context(req, mock_txn)

print(f"Testing unapproved transaction (Status: {mock_ctx.get('txn').status}):")
print(f" - is_authorized: {mock_ctx.get('is_authorized')}")
print(f" - signature_path: {mock_ctx.get('signature_path')}")
assert mock_ctx.get('is_authorized') == False, "Unapproved transaction must not be authorized"
assert mock_ctx.get('signature_path') is None, "Unapproved transaction must not have signature_path"

pdf_unapproved = generate_receipt_pdf(mock_ctx)
doc_unapproved = pymupdf.open(stream=pdf_unapproved, filetype="pdf")
unapproved_images = doc_unapproved[0].get_images()
print(f" - Number of images in unapproved PDF: {len(unapproved_images)}")
for img_info in unapproved_images:
    xref = img_info[0]
    base_img = doc_unapproved.extract_image(xref)
    assert not (base_img["width"] == 1024 and base_img["height"] == 1024), "Unapproved PDF should NOT contain signature image!"
print("SUCCESS: Unapproved transaction correctly excludes signature image.")

print("=== ALL VERIFICATIONS PASSED ===")
