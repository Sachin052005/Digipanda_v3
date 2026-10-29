import os
import sys
import io
import base64
import pypdf
from xhtml2pdf import pisa
from PIL import Image

src_img = r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\.user_uploaded\media_1793262562651_161531a5.png"

# Read exact binary bytes without any modification
with open(src_img, "rb") as f:
    raw_bytes = f.read()

b64_sig = base64.b64encode(raw_bytes).decode("utf-8")
data_uri = f"data:image/png;base64,{b64_sig}"

# Test rendering in a test HTML document with various scaling
# Since the image is 1024x1024 (1:1 aspect ratio), preserving exact 1:1 proportions:
# e.g., width="120" height="120" or width="100" height="100" or style="width: 120px; height: 120px;"
html_test = f"""
<!DOCTYPE html>
<html>
<head>
<style>
  @page {{ size: a4 portrait; margin: 10mm; }}
  .sig-container {{
    text-align: right;
    margin-top: 20px;
  }}
  .sig-img {{
    width: 130px;
    height: 130px;
  }}
  .sig-label {{
    font-size: 8pt;
    font-weight: bold;
    border-top: 1px solid #718096;
    padding-top: 4px;
    display: inline-block;
  }}
</style>
</head>
<body>
  <h2>Testing Exact Original Signature Rendering</h2>
  <div class="sig-container">
    <div>
      <img src="{data_uri}" width="130" height="130" alt="Authorized Signatory" />
    </div>
    <div class="sig-label">
      AUTHORISED SIGNATORY FOR DigiPanda
    </div>
  </div>
</body>
</html>
"""

result = io.BytesIO()
pisa.pisaDocument(io.BytesIO(html_test.encode("utf-8")), result)
pdf_data = result.getvalue()

reader = pypdf.PdfReader(io.BytesIO(pdf_data))
page = reader.pages[0]
print(f"Number of images embedded in PDF: {len(page.images)}")
for im in page.images:
    print(f"Found image in PDF: name={im.name}, size={len(im.data)} bytes")

# Save PDF to scratch
out_test_pdf = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\scratch\test_exact_original_sig.pdf"
with open(out_test_pdf, "wb") as f:
    f.write(pdf_data)
print(f"Saved test PDF to: {out_test_pdf}")
