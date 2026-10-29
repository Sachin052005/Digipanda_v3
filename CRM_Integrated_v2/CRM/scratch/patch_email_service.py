import os

email_service_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\services\email_service.py"
with open(email_service_path, "r", encoding="utf-8") as f:
    c = f.read()

c = c.replace("Shared Email Service for TECHPANDA CRM.", "Shared Email Service for DigiPanda CRM.")
c = c.replace("'company_name': getattr(settings, 'COMPANY_NAME', 'TECHPANDA')", "'company_name': getattr(settings, 'COMPANY_NAME', 'DIGIPANDA')")
c = c.replace("'portal_url': 'https://learn.techpanda.in'", "'portal_url': 'https://learn.digipanda.in'")
c = c.replace('filename = f"TechPanda_Receipt_{payment.receipt_number}.pdf"', 'filename = f"DigiPanda_Receipt_{payment.receipt_number}.pdf"')
c = c.replace("'accounts_email': getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@techpanda.in')", "'accounts_email': getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@digipanda.in')")
c = c.replace("'payment_url': 'https://pay.techpanda.in'", "'payment_url': 'https://pay.digipanda.in'")

with open(email_service_path, "w", encoding="utf-8", newline="\n") as f:
    f.write(c)

print("Updated services/email_service.py")
