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
    b64_sig = base64.b64encode(f.read()).decode("utf-8")
sig_data_uri = f"data:image/png;base64,{b64_sig}"

txn = PaymentTransaction.objects.first()
factory = RequestFactory()
req = factory.get('/')
ctx = get_receipt_context(req, txn)
ctx['signature_path'] = sig_data_uri

# Let's read receipt_pdf.html and replace style="height: 38px; max-width: 150px;" with style="height: 48px;"
with open(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\leads\receipt_pdf.html", "r", encoding="utf-8") as f:
    template_str = f.read()

# Replace with clean HTML attribute or simple style
test_template_str = template_str.replace(
    'style="height: 38px; max-width: 150px;"',
    'style="height: 48px;"'
)

from django.template import Template, Context
t = Template(test_template_str)
rendered = t.render(Context(ctx))

result = io.BytesIO()
pisa.pisaDocument(io.BytesIO(rendered.encode('utf-8')), result)

reader = pypdf.PdfReader(io.BytesIO(result.getvalue()))
print(f"Total pages: {len(reader.pages)}")
page = reader.pages[0]
print(f"Page 0 embedded images: {len(page.images)}")
for im in page.images:
    print(f"  Image: {im.name}, size: {len(im.data)}")
