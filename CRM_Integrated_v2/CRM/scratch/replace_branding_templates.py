import os

template_dir = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates"

replacements = [
    ("TECHPANDA CRM", "DIGIPANDA CRM"),
    ("TechPanda CRM", "DigiPanda CRM"),
    ("techpanda CRM", "digipanda CRM"),
    ("TECHPANDA", "DIGIPANDA"),
    ("TechPanda", "DigiPanda"),
    ("techpanda", "digipanda"),
    ("Tech Panda", "DigiPanda"),
    ("tech panda", "digipanda"),
]

modified_files = []
total_subs = 0

for root, dirs, files in os.walk(template_dir):
    for f in files:
        if f.endswith(".html"):
            path = os.path.join(root, f)
            with open(path, "r", encoding="utf-8") as file:
                content = file.read()
            
            orig_content = content
            file_subs = 0
            for old_val, new_val in replacements:
                count = content.count(old_val)
                if count > 0:
                    content = content.replace(old_val, new_val)
                    file_subs += count
            
            if content != orig_content:
                with open(path, "w", encoding="utf-8") as file:
                    file.write(content)
                modified_files.append((os.path.relpath(path, template_dir), file_subs))
                total_subs += file_subs

print(f"Total replacements: {total_subs} across {len(modified_files)} files.")
for f, cnt in modified_files[:20]:
    print(f" - {f}: {cnt} replacement(s)")
if len(modified_files) > 20:
    print(f" ... and {len(modified_files) - 20} more files.")
