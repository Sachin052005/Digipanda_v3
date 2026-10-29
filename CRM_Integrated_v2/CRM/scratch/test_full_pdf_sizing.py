import os
import sys
import io
import pypdf
import django

sys.path.insert(0, r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from leads.views_enrollment import get_receipt_context
from leads.models_enrollment import PaymentTransaction
from django.template import Template, Context
from xhtml2pdf import pisa, xhtml2pdf_reportlab
import hashlib

# Apply multi-image fix
def _pml_reader_str(self):
    if hasattr(self, '_image') and self._image:
        try:
            return f"PmlImageObject_{hashlib.md5(self._image.tobytes()).hexdigest()}"
        except Exception:
            pass
    return f"PmlImageObject_{id(self)}"

xhtml2pdf_reportlab.PmlImageReader.__str__ = _pml_reader_str

txn = PaymentTransaction.objects.first()
from django.test import RequestFactory
req = RequestFactory().get('/')
ctx = get_receipt_context(req, txn)

# Exact uncropped original image
exact_sig_path = r"D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/static/images/shashi_sign.png"
ctx['signature_path'] = exact_sig_path

with open(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\leads\receipt_pdf.html", "r", encoding="utf-8") as f:
    template_str = f.read()

# Let's test a few sizes: 80x80, 100x100, 120x120, 140x140
for size in [70, 90, 110, 130]:
    modified_tmpl = template_str.replace(
        'style="height: 38px; max-width: 150px;"',
        f'height="{size}" width="{size}" style="height: {size}px; width: {size}px;"'
    )
    # Remove cursive fallback
    old_block = """        {% else %}
        <div style="font-size: 14pt; font-style: italic; font-family: 'Brush Script MT', cursive, Georgia, serif; color: #1a365d; margin-bottom: 2px;">
          DigiPanda
        </div>
        {% endif %}"""
    modified_tmpl = modified_tmpl.replace(old_block, "{% endif %}")

    t = Template(modified_tmpl)
    rendered = t.render(Context(ctx))

    res = io.BytesIO()
    pisa.pisaDocument(io.BytesIO(rendered.encode('utf-8')), res)
    reader = pypdf.PdfReader(io.BytesIO(res.getvalue()))
    page = reader.pages[0]
    xobjs = page['/Resources']['/XObject']
    print(f"Size {size}x{size}: Total pages = {len(reader.pages)}, XObjects = {len(xobjs)}")
    for k, v in xobjs.items():
        print(f"  {k}: {v.get_object().get('/Width')}x{v.get_object().get('/Height')}")
