p = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\.venv\Lib\site-packages\xhtml2pdf\xhtml2pdf_reportlab.py"
with open(p, 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if 'def __str__' in l or 'def __repr__' in l or 'PmlImageObject' in l:
        print(f"Line {i+1}: {l.strip()}")
        for j in range(i, min(i+15, len(lines))):
            print(lines[j], end='')
