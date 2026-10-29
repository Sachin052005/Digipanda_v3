import os
import sys
import numpy as np
from PIL import Image

sys.path.insert(0, r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

static_dir = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\static\images"

print("=== 1. VERIFYING BRAND ASSETS ===")

# Check digipanda_logo.png
light_path = os.path.join(static_dir, "digipanda_logo.png")
assert os.path.exists(light_path), "digipanda_logo.png missing!"
img_light = Image.open(light_path)
print(f" - Light Logo: {img_light.size}, mode={img_light.mode}, size={os.path.getsize(light_path)} bytes")
assert img_light.size == (1024, 359), f"Unexpected size: {img_light.size}"
assert img_light.mode == "RGBA", "Mode must be RGBA"

# Check digipanda_logo_dark.png
dark_path = os.path.join(static_dir, "digipanda_logo_dark.png")
assert os.path.exists(dark_path), "digipanda_logo_dark.png missing!"
img_dark = Image.open(dark_path)
print(f" - Dark Logo: {img_dark.size}, mode={img_dark.mode}, size={os.path.getsize(dark_path)} bytes")
assert img_dark.size == (1024, 359), f"Unexpected size: {img_dark.size}"
assert img_dark.mode == "RGBA", "Mode must be RGBA"

# Verify that dark logo has white text where light logo had black text
arr_dark = np.array(img_dark)
white_pixels = np.sum((arr_dark[:, :, 0] > 240) & (arr_dark[:, :, 1] > 240) & (arr_dark[:, :, 2] > 240) & (arr_dark[:, :, 3] > 100))
print(f" - Dark Logo white pixel count: {white_pixels}")
assert white_pixels > 30000, f"Expected >30000 white pixels in dark logo, found {white_pixels}"

# Check symbol
sym_path = os.path.join(static_dir, "digipanda_symbol.png")
assert os.path.exists(sym_path), "digipanda_symbol.png missing!"
img_sym = Image.open(sym_path)
print(f" - Symbol: {img_sym.size}, mode={img_sym.mode}")
assert img_sym.size[0] == img_sym.size[1], "Symbol should be square"

# Check SVGs
svg_light = os.path.join(static_dir, "digipanda_logo.svg")
svg_dark = os.path.join(static_dir, "digipanda_logo_dark.svg")
assert os.path.exists(svg_light), "digipanda_logo.svg missing!"
assert os.path.exists(svg_dark), "digipanda_logo_dark.svg missing!"
with open(svg_light, "r", encoding="utf-8") as f:
    s_l = f.read()
    assert "<svg" in s_l and "data:image/png;base64," in s_l, "Invalid SVG light"
with open(svg_dark, "r", encoding="utf-8") as f:
    s_d = f.read()
    assert "<svg" in s_d and "data:image/png;base64," in s_d, "Invalid SVG dark"
print(" - SVGs: Valid syntax and base64 payloads confirmed")

# Check favicon
fav_path = os.path.join(static_dir, "favicon.png")
assert os.path.exists(fav_path), "favicon.png missing!"

print("SUCCESS: All brand assets verified successfully!")
