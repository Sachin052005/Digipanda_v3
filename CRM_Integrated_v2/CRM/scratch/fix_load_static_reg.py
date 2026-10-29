import os

REG_DIR = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\registration"

fixed = []
for fn in os.listdir(REG_DIR):
    if fn.endswith(".html"):
        fp = os.path.join(REG_DIR, fn)
        with open(fp, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Check if uses static but doesn't load it
        if "{% static" in content and "{% load static" not in content:
            # Place {% load static %} after {% extends ... %} or at the very top
            if "{% extends" in content:
                # Find end of {% extends ... %} line
                lines = content.splitlines(True)
                new_lines = []
                for line in lines:
                    new_lines.append(line)
                    if line.strip().startswith("{% extends"):
                        new_lines.append("{% load static %}\n")
                content = "".join(new_lines)
            else:
                content = "{% load static %}\n" + content
            
            with open(fp, "w", encoding="utf-8") as f:
                f.write(content)
            fixed.append(fn)

print(f"Fixed {len(fixed)} templates by adding {{% load static %}}: {fixed}")
