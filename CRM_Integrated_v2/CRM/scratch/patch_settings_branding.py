import os

settings_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\config\settings.py"
with open(settings_path, "r", encoding="utf-8") as f:
    sc = f.read()

sc = sc.replace("COMPANY_NAME = os.getenv('COMPANY_NAME', 'TECHPANDA')", "COMPANY_NAME = os.getenv('COMPANY_NAME', 'DIGIPANDA')")
sc = sc.replace("# TECHPANDA CRM Core Apps", "# DIGIPANDA CRM Core Apps")

with open(settings_path, "w", encoding="utf-8", newline="\n") as f:
    f.write(sc)
print("Updated config/settings.py")

accounts_services_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\accounts\services.py"
with open(accounts_services_path, "r", encoding="utf-8") as f:
    ac = f.read()

ac = ac.replace("Accounts Service Layer for TECHPANDA CRM.", "Accounts Service Layer for DigiPanda CRM.")
ac = ac.replace("getattr(settings, 'COMPANY_NAME', 'TECHPANDA')", "getattr(settings, 'COMPANY_NAME', 'DIGIPANDA')")
ac = ac.replace("no-reply@techpanda.academy", "no-reply@digipanda.academy")

with open(accounts_services_path, "w", encoding="utf-8", newline="\n") as f:
    f.write(ac)
print("Updated accounts/services.py")
