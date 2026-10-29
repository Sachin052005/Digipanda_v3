import os
from PIL import Image, ImageDraw, ImageFont
import base64

SRC_IMG = r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\.user_uploaded\media_1792832948629_962b5816.png"
STATIC_DIR = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\static\images"

src_im = Image.open(SRC_IMG).convert("RGBA")
w, h = src_im.size

# Transparent version of src_im (remove white background with smooth alpha)
clean_orig = Image.new("RGBA", (w, h), (0, 0, 0, 0))
pix_src = src_im.load()
pix_clean = clean_orig.load()

for y in range(h):
    for x in range(w):
        r, g, b, a = pix_src[x, y]
        # Calculate brightness
        br = (r + g + b) / 3.0
        if r >= 248 and g >= 248 and b >= 248:
            pix_clean[x, y] = (r, g, b, 0)
        elif br > 235:
            alpha = int(255 * (255 - br) / 20.0)
            pix_clean[x, y] = (r, g, b, max(0, min(255, alpha)))
        else:
            pix_clean[x, y] = (r, g, b, 255)

# Letter 'a' ends at x=252. Baseline sits at y=73.
right_x = 252
gap = 7
font_path = r"C:\Windows\Fonts\segoeuib.ttf"
font = ImageFont.truetype(font_path, 52)

# Measure CRM
dummy = Image.new("RGBA", (1, 1))
d_draw = ImageDraw.Draw(dummy)
crm_bbox = d_draw.textbbox((0, 0), "CRM", font=font)
crm_w = crm_bbox[2] - crm_bbox[0]
crm_h = crm_bbox[3] - crm_bbox[1]
print(f"CRM width: {crm_w}, height: {crm_h}, bbox: {crm_bbox}")

new_w = right_x + gap + crm_w + 10
new_h = h

# 1. Standard DigipandaCRM (CRM in vibrant green #36B44C / (54, 180, 76))
crm_green = (54, 180, 76, 255)
logo_transparent = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
logo_transparent.paste(clean_orig, (0, 0), clean_orig)

draw = ImageDraw.Draw(logo_transparent)
text_x = right_x + gap
text_y = 73 - crm_bbox[3]
draw.text((text_x, text_y), "CRM", fill=crm_green, font=font)

# Save transparent PNGs
logo_transparent.save(os.path.join(STATIC_DIR, "digipanda_crm_logo.png"))
logo_transparent.save(os.path.join(STATIC_DIR, "digipanda_logo.png"))
logo_transparent.save(os.path.join(STATIC_DIR, "digipanda_logo_transparent.png"))

# 2. White background version
logo_white = Image.new("RGBA", (new_w, new_h), (255, 255, 255, 255))
logo_white.paste(logo_transparent, (0, 0), logo_transparent)
logo_white.save(os.path.join(STATIC_DIR, "digipanda_logo_whitebg.png"))

# 3. Base64 SVG version
with open(os.path.join(STATIC_DIR, "digipanda_logo.png"), "rb") as f:
    b64 = base64.b64encode(f.read()).decode("ascii")

svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {new_w} {new_h}" width="{new_w}" height="{new_h}">
  <image href="data:image/png;base64,{b64}" width="{new_w}" height="{new_h}" />
</svg>
'''
with open(os.path.join(STATIC_DIR, "digipanda_logo.svg"), "w", encoding="utf-8") as f:
    f.write(svg_content)

print(f"Successfully generated all logo assets! Size: {new_w}x{new_h}")
