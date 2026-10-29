import re

def update_file(path, old_sub, new_sub):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if old_sub in content:
        content = content.replace(old_sub, new_sub, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated {path} successfully!")
        return True
    else:
        print(f"Sub not found in {path}")
        return False

# 1. enrollment_confirmation.html
ec_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\emails\enrollment_confirmation.html"
with open(ec_path, "r", encoding="utf-8") as f:
    ec_content = f.read()

ec_pattern = r'<!-- Logo badge & text -->[\s\S]*?</span>\s*</td>\s*</tr>\s*</table>'
ec_replacement = """<!-- DigiPanda Logo -->
                          <img src="{% if logo_data_uri %}{{ logo_data_uri }}{% else %}https://digipanda.org/static/images/digipanda_logo.png{% endif %}" height="36" style="height: 36px; width: auto; max-width: 140px; display: block; border: none;" alt="DigiPanda" />"""

if re.search(ec_pattern, ec_content):
    ec_content = re.sub(ec_pattern, ec_replacement, ec_content, count=1)
    with open(ec_path, "w", encoding="utf-8") as f:
        f.write(ec_content)
    print("Updated enrollment_confirmation.html successfully!")
else:
    print("Could not match pattern in enrollment_confirmation.html")

# 2. installment_reminder.html
ir_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\emails\installment_reminder.html"
with open(ir_path, "r", encoding="utf-8") as f:
    ir_content = f.read()

ir_pattern = r'<!-- DigiPanda Logo Badge & Wordmark -->[\s\S]*?</span>\s*</td>\s*</tr>\s*</table>'
ir_replacement = """<!-- DigiPanda Logo -->
                          <img src="{% if logo_data_uri %}{{ logo_data_uri }}{% else %}https://digipanda.org/static/images/digipanda_logo.png{% endif %}" height="36" style="height: 36px; width: auto; max-width: 140px; display: block; border: none;" alt="DigiPanda" />"""

if re.search(ir_pattern, ir_content):
    ir_content = re.sub(ir_pattern, ir_replacement, ir_content, count=1)
    with open(ir_path, "w", encoding="utf-8") as f:
        f.write(ir_content)
    print("Updated installment_reminder.html successfully!")
else:
    print("Could not match pattern in installment_reminder.html")

# 3. payment_receipt.html
pr_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\emails\payment_receipt.html"
with open(pr_path, "r", encoding="utf-8") as f:
    pr_content = f.read()

pr_pattern = r'<div style="font-size: 20px; font-weight: 800; color: #1E3A8A; letter-spacing: -0.5px;">\s*DigiPanda\s*</div>'
pr_replacement = """<div style="margin-bottom: 6px;">
                      <img src="{% if logo_data_uri %}{{ logo_data_uri }}{% else %}https://digipanda.org/static/images/digipanda_logo.png{% endif %}" height="36" style="height: 36px; width: auto; max-width: 140px; display: block; border: none;" alt="DigiPanda" />
                    </div>"""

if re.search(pr_pattern, pr_content):
    pr_content = re.sub(pr_pattern, pr_replacement, pr_content, count=1)
    with open(pr_path, "w", encoding="utf-8") as f:
        f.write(pr_content)
    print("Updated payment_receipt.html successfully!")
else:
    print("Could not match pattern in payment_receipt.html")
