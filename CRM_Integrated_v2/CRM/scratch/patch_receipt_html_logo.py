import os

p_r = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\leads\receipt.html"
with open(p_r, "r", encoding="utf-8") as f:
    c = f.read()

c = c.replace(
    """<img src="{% static 'images/techpanda_logo.png' %}" alt="TechPanda" class="company-logo" onerror="this.onerror=null; this.src='/static/images/techpanda_logo.png';" />""",
    """<img src="{% static 'images/digipanda_logo.png' %}" alt="DigiPanda" class="company-logo" onerror="this.onerror=null; this.src='/static/images/digipanda_logo.png';" />"""
)

with open(p_r, "w", encoding="utf-8", newline="\n") as f:
    f.write(c)

print("Updated receipt.html logo image")
