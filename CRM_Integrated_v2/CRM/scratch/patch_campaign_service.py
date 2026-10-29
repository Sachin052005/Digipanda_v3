import os

p_cs = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\chat\campaign_service.py"
with open(p_cs, "r", encoding="utf-8") as f:
    c = f.read()

c = c.replace("Bulk WhatsApp Campaign Service for TECHPANDA CRM.", "Bulk WhatsApp Campaign Service for DigiPanda CRM.")
c = c.replace('name="TECHPANDA Official Admissions Line"', 'name="DIGIPANDA Official Admissions Line"')
c = c.replace("interest in TECHPANDA.", "interest in DIGIPANDA.")
c = c.replace('footer_text="TECHPANDA Academy - Career Growth"', 'footer_text="DIGIPANDA Academy - Career Growth"')
c = c.replace("welcome to TECHPANDA!", "welcome to DIGIPANDA!")
c = c.replace('footer_text="TECHPANDA Learning"', 'footer_text="DIGIPANDA Learning"')
c = c.replace('footer_text="TECHPANDA Admissions"', 'footer_text="DIGIPANDA Admissions"')
c = c.replace("existing TECHPANDA WhatsApp Inbox", "existing DigiPanda WhatsApp Inbox")

with open(p_cs, "w", encoding="utf-8", newline="\n") as f:
    f.write(c)

print("Updated chat/campaign_service.py")
