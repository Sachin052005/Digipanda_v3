import os
import re

CRM_ROOT = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM"

# 1. templates/registration/password_reset_subject.txt
p_subj = os.path.join(CRM_ROOT, "templates", "registration", "password_reset_subject.txt")
with open(p_subj, "w", encoding="utf-8", newline="\n") as f:
    f.write("DigiPanda CRM - Password Reset Request\n")
print("Updated password_reset_subject.txt")

# 2. templates/emails/enrollment_confirmation.txt
p_ec = os.path.join(CRM_ROOT, "templates", "emails", "enrollment_confirmation.txt")
with open(p_ec, "r", encoding="utf-8") as f:
    txt = f.read()
txt = txt.replace("TECHPANDA", "DIGIPANDA")
txt = txt.replace("techpanda.in", "digipanda.in")
with open(p_ec, "w", encoding="utf-8", newline="\n") as f:
    f.write(txt)
print("Updated enrollment_confirmation.txt")

# 3. templates/emails/installment_reminder.txt
p_ir = os.path.join(CRM_ROOT, "templates", "emails", "installment_reminder.txt")
with open(p_ir, "r", encoding="utf-8") as f:
    txt = f.read()
txt = txt.replace("TECHPANDA", "DIGIPANDA")
txt = txt.replace("techpanda.in", "digipanda.in")
with open(p_ir, "w", encoding="utf-8", newline="\n") as f:
    f.write(txt)
print("Updated installment_reminder.txt")

# 4. templates/emails/payment_receipt.txt
p_prt = os.path.join(CRM_ROOT, "templates", "emails", "payment_receipt.txt")
with open(p_prt, "r", encoding="utf-8") as f:
    txt = f.read()
txt = txt.replace("TechPanda", "DigiPanda")
txt = txt.replace("TECHPANDA", "DIGIPANDA")
txt = txt.replace("admin@itechpanda.com", "admin@digipanda.com")
with open(p_prt, "w", encoding="utf-8", newline="\n") as f:
    f.write(txt)
print("Updated payment_receipt.txt")

# 5. templates/emails/payment_receipt.html
p_prh = os.path.join(CRM_ROOT, "templates", "emails", "payment_receipt.html")
with open(p_prh, "r", encoding="utf-8") as f:
    txt = f.read()
txt = txt.replace("TechPanda", "DigiPanda")
txt = txt.replace("TECHPANDA", "DIGIPANDA")
txt = txt.replace("admin@itechpanda.com", "admin@digipanda.com")
with open(p_prh, "w", encoding="utf-8", newline="\n") as f:
    f.write(txt)
print("Updated payment_receipt.html")

# 6. templates/finance/*.html
fin_dir = os.path.join(CRM_ROOT, "templates", "finance")
for fname in os.listdir(fin_dir):
    if fname.endswith(".html"):
        fp = os.path.join(fin_dir, fname)
        with open(fp, "r", encoding="utf-8") as f:
            c = f.read()
        if "TechPanda CRM" in c or "TechPanda" in c:
            c = c.replace("TechPanda CRM", "DigiPanda CRM")
            c = c.replace("TechPanda", "DigiPanda")
            with open(fp, "w", encoding="utf-8", newline="\n") as f:
                f.write(c)
            print(f"Updated finance template: {fname}")

# 7. templates/admin/offline_leads.html
p_ol = os.path.join(CRM_ROOT, "templates", "admin", "offline_leads.html")
with open(p_ol, "r", encoding="utf-8") as f:
    c = f.read()
c = c.replace("TechPanda CRM", "DigiPanda CRM")
with open(p_ol, "w", encoding="utf-8", newline="\n") as f:
    f.write(c)
print("Updated offline_leads.html")

# 8. templates/chat/campaigns/campaign_composer.html
p_cc = os.path.join(CRM_ROOT, "templates", "chat", "campaigns", "campaign_composer.html")
with open(p_cc, "r", encoding="utf-8") as f:
    c = f.read()
c = c.replace("welcome to TECHPANDA!", "welcome to DIGIPANDA!")
with open(p_cc, "w", encoding="utf-8", newline="\n") as f:
    f.write(c)
print("Updated campaign_composer.html")

# 9. templates/public/landing_page.html
p_lp = os.path.join(CRM_ROOT, "templates", "public", "landing_page.html")
with open(p_lp, "r", encoding="utf-8") as f:
    c = f.read()
c = c.replace("TechPanda CRM", "DigiPanda CRM")
c = c.replace("TechPanda", "DigiPanda")
c = c.replace("techpanda_logo.png", "digipanda_logo.png")
c = c.replace("techpanda_logo.svg", "digipanda_logo.svg")
with open(p_lp, "w", encoding="utf-8", newline="\n") as f:
    f.write(c)
print("Updated landing_page.html")
