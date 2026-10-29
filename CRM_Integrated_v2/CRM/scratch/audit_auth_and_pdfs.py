import os
import re

CRM_ROOT = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM"

print("=== AUDITING AUTH TEMPLATES AND FORMS ===")
login_templates = []
for root, dirs, files in os.walk(os.path.join(CRM_ROOT, "templates")):
    for f in files:
        if "login" in f.lower() or "auth" in f.lower() or "signin" in f.lower() or "password" in f.lower():
            login_templates.append(os.path.relpath(os.path.join(root, f), CRM_ROOT))

print("Found relevant auth templates:", login_templates)

print("\n=== AUDITING PDF SERVICES & TEMPLATES ===")
pdf_files = []
for root, dirs, files in os.walk(CRM_ROOT):
    if "venv" in root or ".venv" in root or ".git" in root:
        continue
    for f in files:
        if any(w in f.lower() for w in ["pdf", "receipt", "invoice", "voucher"]):
            pdf_files.append(os.path.relpath(os.path.join(root, f), CRM_ROOT))

print("Found PDF/Receipt/Invoice files:")
for pf in pdf_files:
    print(" -", pf)

print("\n=== AUDITING BRANDING IN TEMPLATES (TECHPANDA) ===")
techpanda_matches = []
for root, dirs, files in os.walk(os.path.join(CRM_ROOT, "templates")):
    for f in files:
        if f.endswith((".html", ".txt")):
            full_path = os.path.join(root, f)
            with open(full_path, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
                matches = re.findall(r"(tech\s*panda|techpanda)", content, re.IGNORECASE)
                if matches:
                    techpanda_matches.append((os.path.relpath(full_path, CRM_ROOT), len(matches)))

print(f"Templates containing 'TECHPANDA' ({len(techpanda_matches)} files):")
for tm, count in techpanda_matches[:20]:
    print(f" - {tm}: {count} occurrences")
if len(techpanda_matches) > 20:
    print(f" ... and {len(techpanda_matches) - 20} more templates.")
