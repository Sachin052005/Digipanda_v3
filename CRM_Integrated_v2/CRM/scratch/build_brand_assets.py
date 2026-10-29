import os
import base64
import numpy as np
from PIL import Image

src_path = r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\.user_uploaded\media_1793265481842_c385788b.png"
static_dir = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\static\images"

print(f"Loading source logo from: {src_path}")
img = Image.open(src_path).convert("RGBA")
w, h = img.size
print(f"Original size: {w}x{h}")

# 1. Light theme logo: Original PNG
light_logo_path = os.path.join(static_dir, "digipanda_logo.png")
img.save(light_logo_path, format="PNG")
print(f"Saved light theme logo: {light_logo_path}")

# Also save to digipanda_crm_logo.png and digipanda_logo_transparent.png
img.save(os.path.join(static_dir, "digipanda_crm_logo.png"), format="PNG")
img.save(os.path.join(static_dir, "digipanda_logo_transparent.png"), format="PNG")

# 2. Dark theme logo: Black text converted to crisp white
arr = np.array(img, dtype=np.uint8)
r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]

# Pixels belonging to "panda" (dark text)
# r < 75, g < 75, b < 75, and a > 20
dark_mask = (r < 75) & (g < 75) & (b < 75) & (a > 20)

arr_dark = arr.copy()
arr_dark[dark_mask, 0] = 255
arr_dark[dark_mask, 1] = 255
arr_dark[dark_mask, 2] = 255

img_dark = Image.fromarray(arr_dark)
dark_logo_path = os.path.join(static_dir, "digipanda_logo_dark.png")
img_dark.save(dark_logo_path, format="PNG")
print(f"Saved dark theme logo: {dark_logo_path}")

# 3. SVG wrappers
with open(light_logo_path, "rb") as f:
    b64_light = base64.b64encode(f.read()).decode("utf-8")

svg_light_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <image href="data:image/png;base64,{b64_light}" width="{w}" height="{h}" />
</svg>
'''
svg_light_path = os.path.join(static_dir, "digipanda_logo.svg")
with open(svg_light_path, "w", encoding="utf-8") as f:
    f.write(svg_light_content)
print(f"Saved light theme SVG: {svg_light_path}")

with open(dark_logo_path, "rb") as f:
    b64_dark = base64.b64encode(f.read()).decode("utf-8")

svg_dark_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <image href="data:image/png;base64,{b64_dark}" width="{w}" height="{h}" />
</svg>
'''
svg_dark_path = os.path.join(static_dir, "digipanda_logo_dark.svg")
with open(svg_dark_path, "w", encoding="utf-8") as f:
    f.write(svg_dark_content)
print(f"Saved dark theme SVG: {svg_dark_path}")

# 4. Symbol monogram: Crop initial 'd' with green inner dot
# bbox is (19, 32, 361, 332)
symbol_crop = img.crop((19, 32, 361, 332))
# Add padding to make square 340x340
sym_w, sym_h = symbol_crop.size
max_dim = max(sym_w, sym_h) + 20
square_symbol = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))
offset_x = (max_dim - sym_w) // 2
offset_y = (max_dim - sym_h) // 2
square_symbol.paste(symbol_crop, (offset_x, offset_y), symbol_crop)

symbol_path = os.path.join(static_dir, "digipanda_symbol.png")
square_symbol.save(symbol_path, format="PNG")
print(f"Saved brand symbol: {symbol_path} ({max_dim}x{max_dim})")

# 5. Favicon
favicon = square_symbol.resize((64, 64), Image.Resampling.LANCZOS)
favicon_path = os.path.join(static_dir, "favicon.png")
favicon.save(favicon_path, format="PNG")
print(f"Saved favicon: {favicon_path}")

print("=== ALL ASSETS GENERATED SUCCESSFULLY ===")
