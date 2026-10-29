import os
import base64

dest_dir = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\static\images"
logo_png = os.path.join(dest_dir, "digipanda_logo.png")
symbol_png = os.path.join(dest_dir, "digipanda_symbol.png")

with open(logo_png, "rb") as f:
    logo_b64 = base64.b64encode(f.read()).decode("utf-8")

with open(symbol_png, "rb") as f:
    symbol_b64 = base64.b64encode(f.read()).decode("utf-8")

# 1. digipanda_logo.svg
svg_logo = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 262 92" width="262" height="92">
  <image href="data:image/png;base64,{logo_b64}" width="262" height="92" />
</svg>'''

with open(os.path.join(dest_dir, "digipanda_logo.svg"), "w", encoding="utf-8") as f:
    f.write(svg_logo)

# 2. digipanda_symbol.svg
svg_symbol = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 181 201" width="181" height="201">
  <image href="data:image/png;base64,{symbol_b64}" width="181" height="201" />
</svg>'''

with open(os.path.join(dest_dir, "digipanda_symbol.svg"), "w", encoding="utf-8") as f:
    f.write(svg_symbol)

# 3. Update techpanda_logo.svg and techpanda_logo_white.svg for zero-breakage fallback
with open(os.path.join(dest_dir, "techpanda_logo.svg"), "w", encoding="utf-8") as f:
    f.write(svg_logo)

with open(os.path.join(dest_dir, "techpanda_logo_white.svg"), "w", encoding="utf-8") as f:
    f.write(svg_logo)

print("SVGs successfully written!")
