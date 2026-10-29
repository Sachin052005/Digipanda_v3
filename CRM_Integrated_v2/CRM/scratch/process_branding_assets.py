import os
from PIL import Image

src_symbol = r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\.user_uploaded\media_1792828071349_adb7f9cb.png"
src_full = r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\.user_uploaded\media_1792828076643_f22ca642.png"
dest_dir = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\static\images"
os.makedirs(dest_dir, exist_ok=True)

# 1. Process Symbol
sym = Image.open(src_symbol).convert("RGBA")
sym.save(os.path.join(dest_dir, "digipanda_symbol.png"))
# Generate favicon.png and favicon.ico
fav = sym.resize((64, 64), Image.Resampling.LANCZOS)
fav.save(os.path.join(dest_dir, "favicon.png"))
sym.save(os.path.join(dest_dir, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])

# 2. Process Full Logo
full = Image.open(src_full).convert("RGBA")
# Check pixels
# In full logo, background is white/near-white with a few grid dots.
# Let's create two versions:
# a) standard digipanda_logo.png
full.save(os.path.join(dest_dir, "digipanda_logo_original.png"))

# b) transparent version: replace pure white / near-white and faint grid dots with transparency
pix = full.load()
width, height = full.size
clean_trans = Image.new("RGBA", (width, height))
clean_pix = clean_trans.load()

for y in range(height):
    for x in range(width):
        r, g, b, a = pix[x, y]
        # Check if it's near white background or faint gray grid dot (r>230, g>230, b>235)
        if r > 230 and g > 230 and b > 230:
            clean_pix[x, y] = (0, 0, 0, 0)
        else:
            clean_pix[x, y] = (r, g, b, a)

clean_trans.save(os.path.join(dest_dir, "digipanda_logo.png"))
clean_trans.save(os.path.join(dest_dir, "digipanda_logo_transparent.png"))

print("Static assets generated in:", dest_dir)
for f in os.listdir(dest_dir):
    print(" -", f)
