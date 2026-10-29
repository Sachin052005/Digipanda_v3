import os

p_lcv = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\lead_channels\views.py"
with open(p_lcv, "r", encoding="utf-8") as f:
    c = f.read()

c = c.replace("TechPanda Academy", "DigiPanda Academy")
c = c.replace("TechPanda Training & Certifications", "DigiPanda Training & Certifications")
c = c.replace("TechPanda Global Learning", "DigiPanda Global Learning")
c = c.replace("TechPanda - ", "DigiPanda - ")
c = c.replace("crm.techpanda.academy", "crm.digipanda.academy")

with open(p_lcv, "w", encoding="utf-8", newline="\n") as f:
    f.write(c)

print("Updated lead_channels/views.py")
