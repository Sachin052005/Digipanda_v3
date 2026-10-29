import io
import sys
import pypdf
from xhtml2pdf import pisa
from django.template.loader import get_template
import django, os
sys.path.insert(0, r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from leads.views_enrollment import get_receipt_context
from leads.models_enrollment import PaymentTransaction
from django.test import RequestFactory

txn = PaymentTransaction.objects.first()
factory = RequestFactory()
req = factory.get('/')
ctx = get_receipt_context(req, txn)

template = get_template('leads/receipt_pdf.html')
rendered_html = template.render(ctx)

result = io.BytesIO()
pisa.pisaDocument(io.BytesIO(rendered_html.encode('utf-8')), result)

reader = pypdf.PdfReader(io.BytesIO(result.getvalue()))
print(f"Total pages: {len(reader.pages)}")
for p_idx, page in enumerate(reader.pages):
    print(f"Page {p_idx} images: {len(page.images)}")
    for im in page.images:
        print(f"  Image: {im.name}, size: {len(im.data)}")
