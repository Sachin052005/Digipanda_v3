import os
import numpy as np
from PIL import Image

src_path = r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\.user_uploaded\media_1793265481842_c385788b.png"
img = Image.open(src_path).convert("RGBA")

# Create dark theme variant: where pixels are dark/black, make them white (255, 255, 255) while keeping alpha
arr = np.array(img, dtype=np.uint8)

r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]

# Mask for dark/black text (panda)
# From our palette analysis: r < 60, g < 60, b < 60, and a > 50
dark_mask = (r < 70) & (g < 70) & (b < 70) & (a > 30)

arr_dark_theme = arr.copy()
# Change dark text to white, preserving alpha
arr_dark_theme[dark_mask, 0] = 255
arr_dark_theme[dark_mask, 1] = 255
arr_dark_theme[dark_mask, 2] = 255

img_dark_theme = Image.fromarray(arr_dark_theme)

# Also create side-by-side preview on Light background (#ffffff) and Dark background (#0f172a)
preview_w, preview_h = 1024, 500
preview = Image.new("RGBA", (preview_w, preview_h), (255, 255, 255, 255))

# Top half: Light theme background with original logo
bg_light = Image.new("RGBA", (1024, 250), (255, 255, 255, 255))
# Scale logo down to height 100
logo_light_scaled = img.copy()
logo_light_scaled.thumbnail((600, 120), Image.Resampling.LANCZOS)
x_pos = (1024 - logo_light_scaled.width) // 2
y_pos = (250 - logo_light_scaled.height) // 2
bg_light.paste(logo_light_scaled, (x_pos, y_pos), logo_light_scaled)

# Bottom half: Dark theme background (#0f172a) with dark theme logo
bg_dark = Image.new("RGBA", (1024, 250), (15, 23, 42, 255))
logo_dark_scaled = img_dark_theme.copy()
logo_dark_scaled.thumbnail((600, 120), Image.Resampling.LANCZOS)
x_pos_dark = (1024 - logo_dark_scaled.width) // 2
y_pos_dark = (250 - logo_dark_scaled.height) // 2
bg_dark.paste(logo_dark_scaled, (x_pos_dark, y_pos_dark), logo_dark_scaled)

preview.paste(bg_light, (0, 0))
preview.paste(bg_dark, (0, 250))

out_preview = r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\logo_theme_preview.png"
preview.save(out_preview)

out_dark_logo = r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\digipanda_logo_dark.png"
img_dark_theme.save(out_dark_logo)

print("Generated dark logo and preview successfully!")
