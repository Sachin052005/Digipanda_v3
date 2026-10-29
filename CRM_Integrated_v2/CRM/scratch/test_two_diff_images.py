import io
import sys
import pypdf
from xhtml2pdf import pisa

sig_path = r"D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/static/images/shashi_sign.png"
logo_path = r"D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/static/images/digipanda_logo.png"

html_both = f'''<!DOCTYPE html>
<html>
<head></head>
<body>
  <div><img src="{logo_path}" height="38" /></div>
  <div><img src="{sig_path}" height="48" /></div>
</body>
</html>'''

res = io.BytesIO()
pisa.pisaDocument(io.BytesIO(html_both.encode('utf-8')), res)
r = pypdf.PdfReader(io.BytesIO(res.getvalue()))
page = r.pages[0]

xobjs = page['/Resources']['/XObject']
print("Keys in two-image test:", len(xobjs))
for k, v in xobjs.items():
    obj = v.get_object()
    print(" ", k, obj.get('/Width'), obj.get('/Height'))
