import re

# 1. Update receipt.html
receipt_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\leads\receipt.html"
with open(receipt_path, "r", encoding="utf-8") as f:
    c = f.read()

c = re.sub(
    r'<div class="brand-logo-wrap">\s*<svg.*?</svg>\s*</div>',
    r'<div class="brand-logo-wrap">\n          <img src="{% static \'images/digipanda_logo.png\' %}" alt="DigiPanda" style="height: 44px; max-width: 190px; object-fit: contain;">\n        </div>',
    c,
    flags=re.DOTALL
)

with open(receipt_path, "w", encoding="utf-8") as f:
    f.write(c)
print("Updated receipt.html")

# 2. Update receipt_pdf.html
pdf_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\leads\receipt_pdf.html"
with open(pdf_path, "r", encoding="utf-8") as f:
    c = f.read()

c = c.replace(
    '<span class="logo-brand">tech<span class="logo-brand-white">panda</span></span>',
    '<span class="logo-brand">digi<span class="logo-brand-green" style="color:#22C55E;">p</span><span class="logo-brand-white">anda</span></span>'
)

with open(pdf_path, "w", encoding="utf-8") as f:
    f.write(c)
print("Updated receipt_pdf.html")

# 3. Update base.html for Favicon & Sidebar Brand
base_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\base.html"
with open(base_path, "r", encoding="utf-8") as f:
    c = f.read()

# Add Favicon if not present
if "favicon.png" not in c:
    c = c.replace(
        '<meta name="color-scheme" content="light dark">',
        '<meta name="color-scheme" content="light dark">\n  <link rel="icon" type="image/png" href="{% static \'images/favicon.png\' %}">\n  <link rel="shortcut icon" href="{% static \'images/favicon.ico\' %}">'
    )

# Sidebar brand
sidebar_old = re.search(r'<a href="{% url \'login_redirect\' %}" class="brand-logo">.*?</a>', c, flags=re.DOTALL)
if sidebar_old:
    sidebar_new = '''<a href="{% url 'login_redirect' %}" class="brand-logo" style="display: flex; align-items: center; gap: 10px;">
          <img src="{% static 'images/digipanda_symbol.png' %}" alt="DigiPanda" width="28" height="31" style="object-fit: contain; flex-shrink: 0;">
          <span class="brand-text">DIGIPANDA</span>
        </a>'''
    c = c.replace(sidebar_old.group(0), sidebar_new)

with open(base_path, "w", encoding="utf-8") as f:
    f.write(c)
print("Updated base.html")
