import re

poster_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\admin\walkin_form_qr_poster.html"
with open(poster_path, "r", encoding="utf-8") as f:
    c = f.read()

# Add load static if not present
if "{% load static %}" not in c:
    c = "{% load static %}\n" + c

# Replace brand-logo-area
old_logo_area = re.search(r'<div class="brand-logo-area">.*?</div>\s*<!-- Main Poster Headings -->', c, flags=re.DOTALL)
if old_logo_area:
    new_logo_area = '''<div class="brand-logo-area">
      <img src="{% static 'images/digipanda_logo.png' %}" alt="DigiPanda" style="max-height: 56px; max-width: 240px; object-fit: contain; margin-bottom: 8px;">
    </div>

    <!-- Main Poster Headings -->'''
    c = c[:old_logo_area.start()] + new_logo_area + c[old_logo_area.end():]

# Update footer URL
c = c.replace("www.digipandaacademy.com", "www.digipanda.in")
c = c.replace("Digipanda Academy", "DigiPanda Academy")

with open(poster_path, "w", encoding="utf-8") as f:
    f.write(c)

print("Updated walkin_form_qr_poster.html successfully!")
