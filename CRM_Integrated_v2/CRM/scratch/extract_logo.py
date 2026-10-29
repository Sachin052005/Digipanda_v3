import base64
import re

svg_path = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/static/images/techpanda_logo.svg'
out_path = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/static/images/techpanda_logo.png'

with open(svg_path, 'r', encoding='utf-8') as f:
    content = f.read()

m = re.search(r'data:image/png;base64,([A-Za-z0-9+/=]+)', content)
if m:
    data = base64.b64decode(m.group(1))
    with open(out_path, 'wb') as f:
        f.write(data)
    print(f"Successfully extracted {len(data)} bytes to {out_path}")
else:
    print("Could not find base64 PNG in SVG")
