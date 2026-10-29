import os

path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\base.html"
with open(path, "r", encoding="utf-8") as f:
    c = f.read()

c = c.replace("theme-manager.js' %}", "theme-manager.js' %}?v=20261022_dropdown_fix")
c = c.replace("crm.css' %}?v=20261020_3d_theme", "crm.css' %}?v=20261022_dropdown_fix")
c = c.replace("design-system.css' %}?v=20261020_3d_theme", "design-system.css' %}?v=20261022_dropdown_fix")
c = c.replace("crm.js' %}?v=20261020_3d_theme", "crm.js' %}?v=20261022_dropdown_fix")

with open(path, "w", encoding="utf-8") as f:
    f.write(c)

print("Bumped cache busting versions in base.html successfully.")
