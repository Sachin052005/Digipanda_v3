from reportlab.lib.utils import ImageReader
from xhtml2pdf import xhtml2pdf_reportlab
import io
import pypdf
import hashlib
from xhtml2pdf import pisa

# Fix __str__ to return unique sha256 hash of image data
def pml_reader_str(self):
    if hasattr(self, '_image') and self._image:
        try:
            return f"PmlImageObject_{hashlib.md5(self._image.tobytes()).hexdigest()}"
        except Exception:
            pass
    return f"PmlImageObject_{id(self)}"

xhtml2pdf_reportlab.PmlImageReader.__str__ = pml_reader_str

sig_path = r"D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/static/images/shashi_sign.png"
logo_path = r"D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/static/images/digipanda_logo.png"

html_both = f'''<!DOCTYPE html>
<html>
<body>
  <p>Logo below</p>
  <img src="{logo_path}" height="38" />
  <p>Sig below</p>
  <img src="{sig_path}" height="48" />
</body>
</html>'''

res = io.BytesIO()
pisa.pisaDocument(io.BytesIO(html_both.encode('utf-8')), res)
r = pypdf.PdfReader(io.BytesIO(res.getvalue()))
page = r.pages[0]

xobjs = page['/Resources']['/XObject']
print("Number of XObjects in PDF after __str__ fix:", len(xobjs))
for k, v in xobjs.items():
    obj = v.get_object()
    print(" ", k, "Width=", obj.get('/Width'), "Height=", obj.get('/Height'))
