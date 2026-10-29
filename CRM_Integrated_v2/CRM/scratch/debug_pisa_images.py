import os
import sys
import io

sys.path.insert(0, r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from xhtml2pdf import pisa
from django.template.loader import get_template
from leads.views_enrollment import get_receipt_context
from leads.models_enrollment import PaymentTransaction
from django.test import RequestFactory

txn = PaymentTransaction.objects.first()
factory = RequestFactory()
req = factory.get('/')
ctx = get_receipt_context(req, txn)

print(f"ctx['signature_path']: {ctx.get('signature_path')}")
print(f"File exists: {os.path.exists(ctx.get('signature_path', ''))}")

template = get_template('leads/receipt_pdf.html')
rendered_html = template.render(ctx)

# Search for img src in rendered HTML
for line in rendered_html.split('\n'):
    if '<img' in line:
        print("HTML IMG TAG:", line.strip())

result = io.BytesIO()
pisa_doc = pisa.pisaDocument(io.BytesIO(rendered_html.encode("utf-8")), result)
print(f"pisa err: {pisa_doc.err}")

import pypdf
reader = pypdf.PdfReader(io.BytesIO(result.getvalue()))
print(f"Number of images in generated PDF: {len(reader.pages[0].images)}")
for im in reader.pages[0].images:
    print(f"Embedded image name: {im.name}, size: {len(im.data)}")
