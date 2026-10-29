import os

tags_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\.venv\Lib\site-packages\xhtml2pdf\tags.py"
with open(tags_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'class pisaTagIMG' in line:
        print(f"pisaTagIMG at line {i+1}")
        for j in range(i, min(i + 100, len(lines))):
            print(lines[j], end='')
        break
