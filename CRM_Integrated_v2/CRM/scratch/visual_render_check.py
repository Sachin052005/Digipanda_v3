import os
import sys
import io
import fitz  # PyMuPDF
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

# Test size 100x100
modified_tmpl = template_str.replace(
    'style="height: 38px; max-width: 150px;"',
    'height="100" width="100" style="height: 100px; width: 100px;"'
)
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
pdf_bytes = res.getvalue()

# Convert page 0 of PDF to PNG
doc = fitz.open(stream=pdf_bytes, filetype="pdf")
print("PDF page count:", len(doc))
page = doc[0]
pix = page.get_pixmap(dpi=150)
output_img = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\scratch\receipt_page0_visual.png"
pix.save(output_img)
print(f"Saved rendered page 0 image to: {output_img}")
print(f"Image dimensions: {pix.width}x{pix.height}")

# Crop and check the bottom right signatory area
from PIL import Image
pimg = Image.open(output_img)
# The signatory area is in bottom-right (approx x: 50% to 100%, y: 70% to 100%)
w, h = pimg.size
sig_crop = pimg.crop((int(w * 0.55), int(h * 0.70), w, int(h * 0.98)))
crop_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\scratch\signatory_area_crop.png"
sig_crop.save(crop_path)
print(f"Saved signatory area crop to: {crop_path}")
