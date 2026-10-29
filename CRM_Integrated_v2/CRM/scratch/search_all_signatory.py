import os

CRM_ROOT = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM"

print("=== SEARCHING FOR ALL SIGNATORY REFERENCES ===")
for root, dirs, files in os.walk(CRM_ROOT):
    if any(x in root for x in ['venv', '.venv', '.git', 'node_modules', '__pycache__']):
        continue
    for f in files:
        if f.endswith(('.html', '.py', '.txt')):
            p = os.path.join(root, f)
            with open(p, 'r', encoding='utf-8', errors='ignore') as fh:
                txt = fh.read()
                if any(k in txt.lower() for k in ['signatory', 'authorised signatory', 'authorized signatory', 'signature_path', 'shashi']):
                    print(os.path.relpath(p, CRM_ROOT))
