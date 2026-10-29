import os
import sys
import io
import base64
import pypdf
import django

sys.path.insert(0, r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from leads.views_enrollment import get_receipt_context
from leads.models_enrollment import PaymentTransaction
from django.template.loader import get_template
from django.test import RequestFactory
from xhtml2pdf import pisa

src_img = r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\.user_uploaded\media_1793262562651_161531a5.png"
with open(src_img, "rb") as f:
    raw_bytes = f.read()
b64_sig = base64.b64encode(raw_bytes).decode("utf-8")
sig_data_uri = f"data:image/png;base64,{b64_sig}"

txn = PaymentTransaction.objects.first()
factory = RequestFactory()
req = factory.get('/')
ctx = get_receipt_context(req, txn)
ctx['signature_data_uri'] = sig_data_uri
ctx['signature_path'] = sig_data_uri

template = get_template('leads/receipt_pdf.html')
rendered_html = template.render(ctx)

result = io.BytesIO()
pisa.pisaDocument(io.BytesIO(rendered_html.encode('utf-8')), result)

reader = pypdf.PdfReader(io.BytesIO(result.getvalue()))
print(f"Total pages: {len(reader.pages)}")
page = reader.pages[0]
print(f"Page 0 embedded images: {len(page.images)}")
for im in page.images:
    print(f"  Image: {im.name}, size: {len(im.data)}")

out_pdf = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\scratch\test_full_invoice_with_b64_sig.pdf"
with open(out_pdf, "wb") as f:
    f.write(result.getvalue())
print(f"Saved full invoice PDF: {out_pdf}")
