p = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\.venv\Lib\site-packages\xhtml2pdf\xhtml2pdf_reportlab.py"
with open(p, 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if 'def getImage(' in l:
        for j in range(i, min(i+30, len(lines))):
            print(lines[j], end='')
        break
