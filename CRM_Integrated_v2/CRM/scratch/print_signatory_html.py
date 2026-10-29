import sys
import django, os
sys.path.insert(0, r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from leads.views_enrollment import get_receipt_context
from leads.models_enrollment import PaymentTransaction
from django.template.loader import get_template
from django.test import RequestFactory

txn = PaymentTransaction.objects.first()
factory = RequestFactory()
req = factory.get('/')
ctx = get_receipt_context(req, txn)

template = get_template('leads/receipt_pdf.html')
rendered_html = template.render(ctx)

lines = rendered_html.split('\n')
for i, line in enumerate(lines):
    if 'Signatory' in line or 'signature' in line.lower() or 'shashi' in line.lower() or 'digipanda' in line.lower():
        print(f"{i+1}: {line}")
