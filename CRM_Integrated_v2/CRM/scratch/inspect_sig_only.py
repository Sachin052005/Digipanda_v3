import io
import sys
import pypdf
from xhtml2pdf import pisa

sig_path = r"D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/static/images/shashi_sign.png"

html_sig = f'<html><body><img src="{sig_path}" style="height: 48px;" /></body></html>'
res = io.BytesIO()
pisa.pisaDocument(io.BytesIO(html_sig.encode('utf-8')), res)
r = pypdf.PdfReader(io.BytesIO(res.getvalue()))
page = r.pages[0]

xobjs = page['/Resources']['/XObject']
for k, v in xobjs.items():
    print("Key:", k)
    obj = v.get_object()
    print("  Subtype:", obj.get('/Subtype'))
    print("  Width:", obj.get('/Width'), "Height:", obj.get('/Height'))
