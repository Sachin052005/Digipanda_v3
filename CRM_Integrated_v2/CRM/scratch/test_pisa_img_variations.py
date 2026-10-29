import os
import sys
import io
import pypdf
from xhtml2pdf import pisa

sig_path = r"D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/static/images/shashi_sign.png"

# Test 1: with max-width
html1 = f'<html><body><p>Test 1</p><img src="{sig_path}" style="height: 38px; max-width: 150px;" /></body></html>'
res1 = io.BytesIO()
pisa.pisaDocument(io.BytesIO(html1.encode('utf-8')), res1)
reader1 = pypdf.PdfReader(io.BytesIO(res1.getvalue()))
print(f"Test 1 (style with max-width) images: {len(reader1.pages[0].images)}")

# Test 2: style="height: 38px;" without max-width
html2 = f'<html><body><p>Test 2</p><img src="{sig_path}" style="height: 38px;" /></body></html>'
res2 = io.BytesIO()
pisa.pisaDocument(io.BytesIO(html2.encode('utf-8')), res2)
reader2 = pypdf.PdfReader(io.BytesIO(res2.getvalue()))
print(f"Test 2 (style with height only) images: {len(reader2.pages[0].images)}")

# Test 3: width and height attributes
html3 = f'<html><body><p>Test 3</p><img src="{sig_path}" height="38" /></body></html>'
res3 = io.BytesIO()
pisa.pisaDocument(io.BytesIO(html3.encode('utf-8')), res3)
reader3 = pypdf.PdfReader(io.BytesIO(res3.getvalue()))
print(f"Test 3 (height attr only) images: {len(reader3.pages[0].images)}")

# Test 4: base64 data URI
import base64
with open(sig_path, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode('utf-8')
html4 = f'<html><body><p>Test 4</p><img src="data:image/png;base64,{b64}" height="38" /></body></html>'
res4 = io.BytesIO()
pisa.pisaDocument(io.BytesIO(html4.encode('utf-8')), res4)
reader4 = pypdf.PdfReader(io.BytesIO(res4.getvalue()))
print(f"Test 4 (base64 data URI) images: {len(reader4.pages[0].images)}")
