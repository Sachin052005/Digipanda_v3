import os
import sys
import io
import fitz
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

exact_sig_path = r"D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/static/images/shashi_sign.png"
ctx['signature_path'] = exact_sig_path

with open(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\leads\receipt_pdf.html", "r", encoding="utf-8") as f:
    template_str = f.read()

# Let's test with margin-bottom: -30px and size 120x120
old_sig_block = """      <!-- Authorised Signatory Block -->
      <div style="margin-top: 14px; text-align: right;">
        {% if signature_path %}
        <div style="margin-bottom: 3px;">
          <img src="{{ signature_path }}" style="height: 38px; max-width: 150px;" alt="Authorized Signatory" />
        </div>
        {% else %}
        <div style="font-size: 14pt; font-style: italic; font-family: 'Brush Script MT', cursive, Georgia, serif; color: #1a365d; margin-bottom: 2px;">
          DigiPanda
        </div>
        {% endif %}
        <div style="font-size: 7.2pt; font-weight: bold; color: #2d3748; border-top: 1px solid #718096; padding-top: 3px; display: inline-block;">
          {{ signatory_label }}
        </div>
      </div>"""

new_sig_block = """      <!-- Authorised Signatory Block -->
      <div style="margin-top: 10px; text-align: right;">
        {% if signature_path %}
        <div style="margin-bottom: -32px;">
          <img src="{{ signature_path }}" width="125" height="125" style="width: 125px; height: 125px;" alt="Authorized Signatory" />
        </div>
        {% endif %}
        <div style="font-size: 7.2pt; font-weight: bold; color: #2d3748; border-top: 1px solid #718096; padding-top: 3px; display: inline-block;">
          {{ signatory_label }}
        </div>
      </div>"""

modified_tmpl = template_str.replace(old_sig_block, new_sig_block)
t = Template(modified_tmpl)
rendered = t.render(Context(ctx))

res = io.BytesIO()
pisa.pisaDocument(io.BytesIO(rendered.encode('utf-8')), res)
pdf_bytes = res.getvalue()

doc = fitz.open(stream=pdf_bytes, filetype="pdf")
print("PDF page count:", len(doc))
page = doc[0]
pix = page.get_pixmap(dpi=150)
output_img = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\scratch\aligned_receipt_visual.png"
pix.save(output_img)

from PIL import Image
pimg = Image.open(output_img)
w, h = pimg.size
bottom_half = pimg.crop((int(w * 0.45), int(h * 0.60), w, h))
bottom_half.save(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\scratch\aligned_sig_zoom.png")
print("Saved aligned_sig_zoom.png")
