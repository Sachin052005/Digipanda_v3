import os

CRM_ROOT = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM"

# 1. Patch leads/views_enrollment.py
enrollment_views_path = os.path.join(CRM_ROOT, "leads", "views_enrollment.py")
with open(enrollment_views_path, "r", encoding="utf-8") as f:
    ev = f.read()

ev = ev.replace(
    'branch_address = "TechPanda Towers, Knowledge Park, OMR, Chennai, Tamil Nadu - 600096"',
    'branch_address = "DigiPanda Towers, Knowledge Park, OMR, Chennai, Tamil Nadu - 600096"'
)
ev = ev.replace(
    "logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'techpanda_logo.png').replace('\\\\', '/')",
    "logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'digipanda_logo.png').replace('\\\\', '/')"
)

old_sig_addition = """    # Font & Logo local paths for xhtml2pdf rendering"""
new_sig_addition = """    # Signature, Font & Logo local paths for xhtml2pdf rendering
    signature_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'shashi_sign.png').replace('\\\\', '/')
    if not os.path.exists(signature_path):
        signature_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'Shashi_Sign.png').replace('\\\\', '/')"""

if old_sig_addition in ev and "signature_path = " not in ev:
    ev = ev.replace(old_sig_addition, new_sig_addition)

old_context_tail = """        'font_path': font_path,

        'logo_path': logo_path,

    }"""

new_context_tail = """        'font_path': font_path,

        'logo_path': logo_path,

        'signature_path': signature_path if os.path.exists(signature_path) else None,

        'signature_url': '/static/images/shashi_sign.png',

    }"""

if old_context_tail in ev:
    ev = ev.replace(old_context_tail, new_context_tail)

ev = ev.replace(
    'filename = f"TechPanda_Receipt_{txn.receipt_number}.pdf"',
    'filename = f"DigiPanda_Receipt_{txn.receipt_number}.pdf"'
)

with open(enrollment_views_path, "w", encoding="utf-8", newline="\n") as f:
    f.write(ev)
print("Updated leads/views_enrollment.py")

# 2. Patch templates/leads/receipt_pdf.html
pdf_template_path = os.path.join(CRM_ROOT, "templates", "leads", "receipt_pdf.html")
with open(pdf_template_path, "r", encoding="utf-8") as f:
    pv = f.read()

pv = pv.replace(
    "<title>Tax Invoice {{ invoice_number }} - TechPanda</title>",
    "<title>Tax Invoice {{ invoice_number }} - DigiPanda</title>"
)

old_signatory_pdf = """      <!-- Authorised Signatory Block -->
      <div style="margin-top: 22px; text-align: right;">
        <div style="font-size: 16pt; font-style: italic; font-family: 'Brush Script MT', cursive, Georgia, serif; color: #1a365d; margin-bottom: 2px;">
          TechPanda
        </div>
        <div style="font-size: 7.2pt; font-weight: bold; color: #2d3748; border-top: 1px solid #718096; padding-top: 4px; display: inline-block;">
          {{ signatory_label }}
        </div>
      </div>"""

new_signatory_pdf = """      <!-- Authorised Signatory Block -->
      <div style="margin-top: 14px; text-align: right;">
        {% if signature_path %}
        <div style="margin-bottom: 3px;">
          <img src="{{ signature_path }}" style="height: 38px; max-width: 150px;" alt="Authorized Signatory" />
        </div>
        {% else %}
        <div style="font-size: 14pt; font-style: italic; font-family: 'Brush Script MT', cursive, Georgia, serif; color: #1a365d; margin-bottom: 2px;">
          DigiPanda
        </div>
        {% endif %}
        <div style="font-size: 7.2pt; font-weight: bold; color: #2d3748; border-top: 1px solid #718096; padding-top: 3px; display: inline-block;">
          {{ signatory_label }}
        </div>
      </div>"""

if old_signatory_pdf in pv:
    pv = pv.replace(old_signatory_pdf, new_signatory_pdf)

with open(pdf_template_path, "w", encoding="utf-8", newline="\n") as f:
    f.write(pv)
print("Updated templates/leads/receipt_pdf.html")

# 3. Patch templates/leads/receipt.html
html_template_path = os.path.join(CRM_ROOT, "templates", "leads", "receipt.html")
with open(html_template_path, "r", encoding="utf-8") as f:
    hv = f.read()

hv = hv.replace(
    "<title>Tax Invoice {{ invoice_number }} — Official Student Fee Receipt — TechPanda</title>",
    "<title>Tax Invoice {{ invoice_number }} — Official Student Fee Receipt — DigiPanda</title>"
)

old_signatory_html = """        <!-- Signatory -->
        <div class="signatory-box">
          <div class="signatory-cursive">TechPanda</div>
          <div class="signatory-label">{{ signatory_label }}</div>
        </div>"""

new_signatory_html = """        <!-- Signatory -->
        <div class="signatory-box">
          <div style="margin-bottom: 4px;">
            <img src="{% static 'images/shashi_sign.png' %}" style="height: 42px; width: auto; max-width: 160px; object-fit: contain;" alt="Authorized Signatory" />
          </div>
          <div class="signatory-label">{{ signatory_label }}</div>
        </div>"""

if old_signatory_html in hv:
    hv = hv.replace(old_signatory_html, new_signatory_html)

with open(html_template_path, "w", encoding="utf-8", newline="\n") as f:
    f.write(hv)
print("Updated templates/leads/receipt.html")
