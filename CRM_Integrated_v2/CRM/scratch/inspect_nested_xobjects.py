import io
import sys
import pypdf
from xhtml2pdf import pisa

sig_path = r"D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/static/images/shashi_sign.png"
logo_path = r"D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/static/images/digipanda_logo.png"

html_both = f'<html><body><img src="{logo_path}" style="height: 38px;" /><br/><img src="{sig_path}" style="height: 48px;" /></body></html>'
res = io.BytesIO()
pisa.pisaDocument(io.BytesIO(html_both.encode('utf-8')), res)
r = pypdf.PdfReader(io.BytesIO(res.getvalue()))
page = r.pages[0]

form_xobj = page['/Resources']['/XObject']['/FormXob.23e5316baac4f63e7e59031258f6ea30']
print("Form XObject Subtype:", form_xobj.get('/Subtype'))
print("Form XObject Resources:", form_xobj.get('/Resources'))
if '/Resources' in form_xobj and '/XObject' in form_xobj['/Resources']:
    sub_xobjs = form_xobj['/Resources']['/XObject']
    print("Nested XObjects:", list(sub_xobjs.keys()))
    for k in sub_xobjs.keys():
        print("  Sub image:", k, sub_xobjs[k].get('/Subtype'), sub_xobjs[k].get('/Width'), sub_xobjs[k].get('/Height'))
