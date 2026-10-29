import io
import sys
import logging
import django, os

sys.path.insert(0, r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

# Configure logging to show all xhtml2pdf and reportlab logs
logging.basicConfig(level=logging.DEBUG)

from xhtml2pdf import pisa
from django.template.loader import get_template
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
pisa_doc = pisa.pisaDocument(io.BytesIO(rendered_html.encode('utf-8')), result)
print("Finished rendering. Warnings/errors count:", len(pisa_doc.log))
for item in pisa_doc.log:
    print("LOG ITEM:", item)
