from reportlab.lib.utils import ImageReader
from xhtml2pdf import xhtml2pdf_reportlab
import io
import pypdf
from xhtml2pdf import pisa

# Register PmlImageReader as virtual subclass of ImageReader
ImageReader.register(xhtml2pdf_reportlab.PmlImageReader)

print("isinstance after register:", isinstance(xhtml2pdf_reportlab.PmlImageReader(io.BytesIO(open(r"D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/static/images/digipanda_logo.png", "rb").read())), ImageReader))

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
print("Number of XObjects in PDF after fix:", len(xobjs))
for k, v in xobjs.items():
    obj = v.get_object()
    print(" ", k, obj.get('/Width'), obj.get('/Height'))
