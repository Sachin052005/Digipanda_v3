import os
import sys
from PIL import Image, ImageDraw, ImageFont

SRC_IMG = r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\.user_uploaded\media_1792832948629_962b5816.png"
STATIC_IMG_DIR = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\static\images"

im = Image.open(SRC_IMG).convert("RGBA")
width, height = im.size
print(f"Source image size: {width}x{height}")

# 1. Convert white background to transparent smoothly
pix = im.load()
trans_im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
trans_pix = trans_im.load()

min_x, min_y, max_x, max_y = width, height, 0, 0

for y in range(height):
    for x in range(width):
        r, g, b, a = pix[x, y]
        # Check whiteness
        # If very close to pure white, alpha -> 0
        brightness = (r + g + b) / 3.0
        if r > 248 and g > 248 and b > 248:
            trans_pix[x, y] = (r, g, b, 0)
        elif r > 230 and g > 230 and b > 230:
            # Smooth feather
            alpha = int(255 * (248 - brightness) / 18.0)
            alpha = max(0, min(255, alpha))
            trans_pix[x, y] = (r, g, b, alpha)
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
        else:
            trans_pix[x, y] = (r, g, b, 255)
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)

print(f"Content bbox: ({min_x}, {min_y}, {max_x}, {max_y}), w={max_x-min_x}, h={max_y-min_y}")

# Find letter baseline: examine 'anda' at right side
# 'anda' ends around max_x. Let's see the bottom of 'anda'
anda_bottom = max_y
anda_top = min_y
print(f"anda_top: {anda_top}, anda_bottom: {anda_bottom}")

# Now let's try fonts for "CRM"
font_candidates = [
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\calibrib.ttf",
]
selected_font_path = None
for fp in font_candidates:
    if os.path.exists(fp):
        selected_font_path = fp
        break

font_size = 48
font = ImageFont.truetype(selected_font_path, font_size)

# Measure CRM
dummy = Image.new("RGBA", (1, 1))
d_draw = ImageDraw.Draw(dummy)
crm_bbox = d_draw.textbbox((0, 0), "CRM", font=font)
crm_w = crm_bbox[2] - crm_bbox[0]
crm_h = crm_bbox[3] - crm_bbox[1]
print(f"Font: {selected_font_path}, size={font_size}, crm_w={crm_w}, crm_h={crm_h}")

# The logo width needs to fit:
# [Panda + digipanda] + gap (8px) + [CRM] + right padding (8px)
gap = 6
pad_right = 10
new_w = max_x + gap + crm_w + pad_right
new_h = height

# Target colors:
# Brand Blue: (23, 75, 137, 255) -> #174B89
# Brand Green: (54, 180, 76, 255) -> #36B44C (matches p in logo)
# Brand Dark: (38, 34, 33, 255) -> #262221

# Create composite on transparent
comp_trans = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
comp_trans.paste(trans_im, (0, 0), trans_im)
draw_trans = ImageDraw.Draw(comp_trans)

# Position CRM vertically so baseline matches 'anda'
# anda_bottom is max_y. crm_bbox[3] is bottom offset.
crm_x = max_x + gap
crm_y = anda_bottom - crm_bbox[3]
draw_trans.text((crm_x, crm_y), "CRM", fill=(54, 180, 76, 255), font=font)

# Save composite transparent logo
crm_logo_path = os.path.join(STATIC_IMG_DIR, "digipanda_crm_logo.png")
comp_trans.save(crm_logo_path)
print(f"Saved: {crm_logo_path} ({new_w}x{new_h})")

# Overwrite digipanda_logo.png so all templates referencing it get DigipandaCRM!
primary_logo_path = os.path.join(STATIC_IMG_DIR, "digipanda_logo.png")
comp_trans.save(primary_logo_path)
print(f"Saved: {primary_logo_path} ({new_w}x{new_h})")

# Also create White background version
comp_white = Image.new("RGBA", (new_w, new_h), (255, 255, 255, 255))
comp_white.paste(comp_trans, (0, 0), comp_trans)
comp_white.save(os.path.join(STATIC_IMG_DIR, "digipanda_logo_whitebg.png"))

# Also create SVG version embedding the new PNG
import base64
with open(primary_logo_path, "rb") as f:
    b64_data = base64.b64encode(f.read()).decode("ascii")

svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {new_w} {new_h}" width="{new_w}" height="{new_h}">
  <image href="data:image/png;base64,{b64_data}" width="{new_w}" height="{new_h}" />
</svg>
'''
svg_path = os.path.join(STATIC_IMG_DIR, "digipanda_logo.svg")
with open(svg_path, "w", encoding="utf-8") as f:
    f.write(svg_content)
print(f"Saved SVG: {svg_path}")
