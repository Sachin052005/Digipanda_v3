import io
import sys
import pypdf
from xhtml2pdf import pisa
import os

sig_path = r"D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/static/images/shashi_sign.png"
logo_path = r"D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/static/images/digipanda_logo.png"

# Test 1: Only logo
html_logo = f'<html><body><img src="{logo_path}" style="height: 38px;" /></body></html>'
res = io.BytesIO()
pisa.pisaDocument(io.BytesIO(html_logo.encode('utf-8')), res)
r = pypdf.PdfReader(io.BytesIO(res.getvalue()))
print("Only logo XObjects:", list(r.pages[0]['/Resources']['/XObject'].keys()))

# Test 2: Only signature
html_sig = f'<html><body><img src="{sig_path}" style="height: 48px;" /></body></html>'
res = io.BytesIO()
pisa.pisaDocument(io.BytesIO(html_sig.encode('utf-8')), res)
r = pypdf.PdfReader(io.BytesIO(res.getvalue()))
print("Only sig XObjects:", list(r.pages[0]['/Resources']['/XObject'].keys()))

# Test 3: Both with file paths
html_both = f'<html><body><img src="{logo_path}" style="height: 38px;" /><br/><img src="{sig_path}" style="height: 48px;" /></body></html>'
res = io.BytesIO()
pisa.pisaDocument(io.BytesIO(html_both.encode('utf-8')), res)
r = pypdf.PdfReader(io.BytesIO(res.getvalue()))
print("Both with file paths XObjects:", list(r.pages[0]['/Resources']['/XObject'].keys()))
