import os
import sys
sys.path.insert(0, 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.conf import settings
from xhtml2pdf import pisa
import io

font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'Arial.ttf').replace('\\', '/')
logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'techpanda_logo.png').replace('\\', '/')

html_content = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {{
    size: a4 portrait;
    margin: 8mm 10mm 8mm 10mm;
}}
@font-face {{
    font-family: 'ArialCustom';
    src: url('{font_path}');
}}
body {{
    font-family: 'ArialCustom', Arial, sans-serif;
    font-size: 9pt;
    color: #2d3748;
    line-height: 1.35;
}}
table {{
    border-collapse: collapse;
    width: 100%;
}}
.badge {{
    border: 1px solid #4a5568;
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 8pt;
    font-weight: bold;
    color: #2d3748;
    text-transform: uppercase;
}}
.inv-bar {{
    background-color: #f3f4f6;
    border: 1px solid #e5e7eb;
    padding: 6px 10px;
    margin-top: 10px;
    margin-bottom: 10px;
}}
.services-th {{
    border-bottom: 2px solid #000000;
    font-weight: bold;
    font-size: 8.5pt;
    padding: 6px 4px;
}}
.services-td {{
    padding: 8px 4px;
    font-size: 8.5pt;
    border-bottom: 0.5px solid #edf2f7;
}}
.subtotal-td {{
    border-top: 2px solid #000000;
    border-bottom: 2px solid #000000;
    font-weight: bold;
    font-size: 8.5pt;
    padding: 6px 4px;
}}
.summary-table td {{
    padding: 3px 0px;
    font-size: 8.5pt;
}}
.clause-text {{
    font-size: 7pt;
    color: #4a5568;
    margin-top: 3px;
}}
</style>
</head>
<body>

<!-- Header with Logo & Badges -->
<table>
  <tr>
    <td style="width: 55%; vertical-align: top;">
      <img src="{logo_path}" style="height: 38px;" /><br/>
      <div style="font-weight: bold; font-size: 9.5pt; margin-top: 4px;">TechPanda</div>
      <div style="font-size: 7.5pt; color: #4a5568; margin-top: 2px;">
        2nd Floor, No 15, Sy No 33,34A,35, Celestial Complex,<br/>
        South Usman Road, T Nagar, Chennai, Tamil Nadu, 600017<br/>
        Mobile: 9884678282<br/>
        GSTIN: 33AAMCT5031F1ZJ<br/>
        PAN Number: AAMCT5031F<br/>
        Email: admin@itechpanda.com<br/>
        Website: www.itechpanda.com
      </div>
    </td>
    <td style="width: 45%; vertical-align: top; text-align: right;">
      <div style="margin-bottom: 6px;">
        <span class="badge">TAX INVOICE</span>
      </div>
      <div>
        <span class="badge">ORIGINAL FOR RECIPIENT</span>
      </div>
    </td>
  </tr>
</table>

<!-- Invoice Bar -->
<div class="inv-bar">
  <table>
    <tr>
      <td style="font-weight: bold; font-size: 8.5pt;">Invoice No.: TP12519</td>
      <td style="text-align: right; font-weight: bold; font-size: 8.5pt;">Invoice Date: 08/10/2026</td>
    </tr>
  </table>
</div>

<!-- Bill To -->
<div style="margin-top: 6px; margin-bottom: 12px;">
  <div style="font-size: 7.5pt; font-weight: bold; color: #718096; text-transform: uppercase;">BILL TO</div>
  <div style="font-size: 10pt; font-weight: bold; color: #1a202c; margin-top: 1px;">M DEEPAK ROSHAN</div>
  <div style="font-size: 8pt; color: #4a5568; margin-top: 2px;">Mobile: 9876543210</div>
  <div style="font-size: 8pt; color: #4a5568;">Place of Supply: Tamil Nadu</div>
</div>

<!-- Services Table -->
<table>
  <thead>
    <tr>
      <th class="services-th" style="text-align: left; width: 45%;">SERVICES</th>
      <th class="services-th" style="text-align: right; width: 18%;">RATE</th>
      <th class="services-th" style="text-align: right; width: 18%;">TAX</th>
      <th class="services-th" style="text-align: right; width: 19%;">AMOUNT</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td class="services-td" style="font-weight: bold;">DATA ANALYTICS COURSE</td>
      <td class="services-td" style="text-align: right;">₹ 35,000.00</td>
      <td class="services-td" style="text-align: right;">₹ 6,300.00 (18%)</td>
      <td class="services-td" style="text-align: right; font-weight: bold;">₹ 41,300.00</td>
    </tr>
    <tr>
      <td class="subtotal-td">SUBTOTAL</td>
      <td class="subtotal-td"></td>
      <td class="subtotal-td" style="text-align: right;">₹ 6,300.00</td>
      <td class="subtotal-td" style="text-align: right;">₹ 41,300.00</td>
    </tr>
  </tbody>
</table>

<!-- Bottom 2-Column Section -->
<table style="margin-top: 15px;">
  <tr>
    <!-- Left Column: Bank Details & Terms -->
    <td style="width: 54%; vertical-align: top; padding-right: 15px;">
      <div style="font-size: 8.5pt; font-weight: bold; color: #1a202c; text-transform: uppercase; margin-bottom: 4px;">
        BANK DETAILS
      </div>
      <div style="font-size: 7.5pt; color: #2d3748; line-height: 1.4;">
        <strong>Name:</strong> Techpanda Software Training Private Limited<br/>
        <strong>IFSC:</strong> HDFC0000141<br/>
        <strong>Account No:</strong> 50200115357040<br/>
        <strong>Bank:</strong> HDFC Bank, CHENNAI - R A PURAM
      </div>

      <div style="font-size: 8.5pt; font-weight: bold; color: #1a202c; text-transform: uppercase; margin-top: 14px; margin-bottom: 4px;">
        TERMS AND CONDITIONS
      </div>
      <div class="clause-text">
        <strong>1. Enrollment and Fees:</strong> Fees once paid for the training program are non-refundable and non-transferable under any circumstances.
      </div>
      <div class="clause-text">
        <strong>2. Course Access:</strong> Access to course materials, online platforms, and software licenses is granted for the duration of the course only and may not be shared with others.
      </div>
    </td>

    <!-- Right Column: Financial Breakdown -->
    <td style="width: 46%; vertical-align: top; padding-left: 10px;">
      <table class="summary-table">
        <tr>
          <td style="color: #4a5568;">Taxable Amount</td>
          <td style="text-align: right;">₹ 35,000.00</td>
        </tr>
        <tr>
          <td style="color: #4a5568;">CGST @9%</td>
          <td style="text-align: right;">₹ 3,150.00</td>
        </tr>
        <tr>
          <td style="color: #4a5568;">SGST @9%</td>
          <td style="text-align: right;">₹ 3,150.00</td>
        </tr>
        <tr style="border-top: 1px solid #cbd5e0; border-bottom: 1px solid #cbd5e0;">
          <td style="font-weight: bold; font-size: 9.5pt; padding: 4px 0;">Total Amount</td>
          <td style="text-align: right; font-weight: bold; font-size: 9.5pt; padding: 4px 0;">₹ 41,300.00</td>
        </tr>
        <tr>
          <td style="color: #4a5568; padding-top: 6px;">Received Amount</td>
          <td style="text-align: right; padding-top: 6px;">₹ 41,300.00</td>
        </tr>
        <tr>
          <td style="font-weight: bold; color: #1a202c;">Balance</td>
          <td style="text-align: right; font-weight: bold; color: #1a202c;">₹ 0.00</td>
        </tr>
      </table>

      <!-- Amount in words -->
      <div style="margin-top: 12px; font-size: 7.5pt; color: #4a5568;">
        <strong>Total Amount (in words)</strong><br/>
        <span style="font-style: italic; color: #1a202c; font-size: 8pt;">Forty One Thousand Three Hundred Rupees Only</span>
      </div>

      <!-- Authorised Signatory -->
      <div style="margin-top: 25px; text-align: right;">
        <div style="font-size: 16pt; font-style: italic; font-family: 'Brush Script MT', cursive, Georgia, serif; color: #1a365d; margin-bottom: 3px;">
          TechPanda
        </div>
        <div style="font-size: 7.5pt; font-weight: bold; color: #2d3748; border-top: 1px solid #718096; padding-top: 4px; display: inline-block;">
          AUTHORISED SIGNATORY FOR TechPanda
        </div>
      </div>
    </td>
  </tr>
</table>

</body>
</html>
"""

res = io.BytesIO()
p = pisa.pisaDocument(io.BytesIO(html_content.encode('utf-8')), res)
print("pisa err:", p.err)
pdf_data = res.getvalue()
print("PDF length:", len(pdf_data))
with open('D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/scratch/test_tax_invoice.pdf', 'wb') as f:
    f.write(pdf_data)
print("Saved test_tax_invoice.pdf successfully!")
