import io
import sys
import pypdf
from xhtml2pdf import pisa

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
contents = page.get_contents().get_data().decode('latin1', errors='ignore')
print("=== CONTENT STREAM SNIPPET ===")
for line in contents.split('\n'):
    if '/FormXob' in line or 'Do' in line:
        print(line)
