import os
import sys
import pymupdf
import django

sys.path.insert(0, r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from leads.views_enrollment import get_receipt_context, generate_receipt_pdf
from leads.models_enrollment import PaymentTransaction, PaymentTransactionStatus
from django.test import RequestFactory

print("=== 2. VERIFYING PDF WITH NEW LOGO & SIGNATURE ===")

factory = RequestFactory()
req = factory.get('/')

txn = PaymentTransaction.objects.filter(
    status__in=[PaymentTransactionStatus.APPROVED, PaymentTransactionStatus.SUCCESS]
).first()

ctx = get_receipt_context(req, txn)
print(f"Context logo_path: {ctx.get('logo_path')}")
print(f"Context signature_path: {ctx.get('signature_path')}")
print(f"Context is_authorized: {ctx.get('is_authorized')}")

pdf_bytes = generate_receipt_pdf(ctx)
assert pdf_bytes is not None and len(pdf_bytes) > 0, "PDF rendering failed!"
print(f"PDF bytes size: {len(pdf_bytes)}")

doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
assert len(doc) == 1, f"Expected 1 page, got {len(doc)}"
page = doc[0]

images = page.get_images()
print(f"Embedded images in PDF: {len(images)}")
assert len(images) >= 2, f"Expected at least 2 images (logo and signature), found {len(images)}"

logo_found = False
sig_found = False

for img_info in images:
    xref = img_info[0]
    base_img = doc.extract_image(xref)
    w = base_img["width"]
    h = base_img["height"]
    size = len(base_img["image"])
    print(f" - Image xref {xref}: {w}x{h}, ext={base_img['ext']}, bytes={size}")
    if w == 1024 and h == 359:
        logo_found = True
        print("   -> Matched new DigiPanda brand logo (1024x359)!")
    elif w == 1024 and h == 1024:
        sig_found = True
        print("   -> Matched authentic Shashi Sign image (1024x1024)!")

assert logo_found, "New DigiPanda brand logo (1024x359) NOT found in PDF!"
assert sig_found, "Authentic signature (1024x1024) NOT found in PDF!"

# Render page 0 and crop header
pix = page.get_pixmap(dpi=150)
out_page_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\scratch\verified_pdf_page_with_new_logo.png"
pix.save(out_page_path)
print(f"Saved full page render to {out_page_path}")

# Header crop
header_rect = pymupdf.Rect(0, 0, page.rect.width, page.rect.height * 0.25)
header_pix = page.get_pixmap(clip=header_rect, dpi=200)
out_header_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\scratch\verified_pdf_header_zoom.png"
header_pix.save(out_header_path)
print(f"Saved header zoom to {out_header_path}")

print("SUCCESS: PDF contains both new brand logo and signature with 1-page fit!")
