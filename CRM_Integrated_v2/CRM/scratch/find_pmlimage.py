import os

pkg_dir = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\.venv\Lib\site-packages\xhtml2pdf"
for root, dirs, files in os.walk(pkg_dir):
    for f in files:
        if f.endswith('.py'):
            p = os.path.join(root, f)
            with open(p, 'r', encoding='utf-8', errors='ignore') as fh:
                if 'class PmlImage' in fh.read():
                    print("PmlImage in:", os.path.relpath(p, pkg_dir))
