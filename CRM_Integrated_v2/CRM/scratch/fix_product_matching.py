views_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\leads\views_walkin.py"
with open(views_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """        if not product and course_track:

            product = Product.objects.filter(name__icontains=course_track).first()"""

replacement = """        if not product and course_track:
            product = Product.objects.filter(name__icontains=course_track).first()
        if not product and interested_courses:
            for ic in interested_courses:
                p_match = Product.objects.filter(name__icontains=ic).first()
                if p_match:
                    product = p_match
                    break"""

if target in content:
    content = content.replace(target, replacement)
else:
    import re
    content = re.sub(
        r'if not product and course_track:\s+product = Product\.objects\.filter\(name__icontains=course_track\)\.first\(\)',
        replacement,
        content
    )

with open(views_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated product matching in views_walkin.py")
