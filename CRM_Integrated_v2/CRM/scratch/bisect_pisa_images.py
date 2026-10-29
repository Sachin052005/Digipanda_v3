import io
import sys
import pypdf
from xhtml2pdf import pisa
import base64

sig_path = r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\.user_uploaded\media_1793262562651_161531a5.png"
with open(sig_path, "rb") as f:
    b64 = base64.b64encode(f.read()).decode("utf-8")
sig_uri = f"data:image/png;base64,{b64}"

logo_path = r"D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/static/images/digipanda_logo.png"

# Test having both images in simple html
html = f"""
<html>
<body>
  <table>
    <tr>
      <td><img src="{logo_path}" style="height: 38px;" /></td>
    </tr>
  </table>
  <table>
    <tr>
      <td>
        <img src="{sig_uri}" style="height: 48px;" />
      </td>
    </tr>
  </table>
</body>
</html>
"""
res = io.BytesIO()
pisa.pisaDocument(io.BytesIO(html.encode('utf-8')), res)
reader = pypdf.PdfReader(io.BytesIO(res.getvalue()))
print(f"Simple two-table HTML: page images = {len(reader.pages[0].images)}")
for im in reader.pages[0].images:
    print(" ", im.name, len(im.data))
