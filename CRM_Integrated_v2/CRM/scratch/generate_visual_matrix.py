import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

static_dir = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\static\images"
out_dir = r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d"

logo_light = Image.open(os.path.join(static_dir, "digipanda_logo.png")).convert("RGBA")
logo_dark = Image.open(os.path.join(static_dir, "digipanda_logo_dark.png")).convert("RGBA")
symbol = Image.open(os.path.join(static_dir, "digipanda_symbol.png")).convert("RGBA")

# Create a composite verification image 1200x900
canvas = Image.new("RGBA", (1200, 950), (241, 245, 249, 255))
draw = ImageDraw.Draw(canvas)

# Title Header
draw.rectangle([(0, 0), (1200, 70)], fill=(30, 41, 59, 255))
# Text: DigiPanda CRM Brand Logo & Theme System Verification
# Left side: Light Theme Preview
# Right side: Dark Theme Preview

# Panel 1: Light Theme (Left: x=40 to 580)
# Background white (#ffffff)
draw.rectangle([(40, 90), (580, 900)], fill=(255, 255, 255, 255), outline=(226, 232, 240, 255), width=2)
# Header bar inside light theme
draw.rectangle([(40, 90), (580, 155)], fill=(255, 255, 255, 255), outline=(226, 232, 240, 255), width=1)
# Draw Light Header Logo
l_header = logo_light.copy()
l_header.thumbnail((160, 32), Image.Resampling.LANCZOS)
canvas.paste(l_header, (60, 105), l_header)

# CRM Badge next to logo
draw.rounded_rectangle([(60 + l_header.width + 8, 108), (60 + l_header.width + 48, 132)], radius=4, fill=(43, 179, 75, 30), outline=(43, 179, 75, 80), width=1)

# Sidebar mockup in light theme
draw.rectangle([(40, 155), (200, 500)], fill=(248, 250, 252, 255), outline=(226, 232, 240, 255), width=1)
# Sidebar logo
l_sidebar = logo_light.copy()
l_sidebar.thumbnail((120, 26), Image.Resampling.LANCZOS)
canvas.paste(l_sidebar, (55, 175), l_sidebar)

# Collapsed sidebar with symbol
draw.rectangle([(40, 520), (110, 880)], fill=(248, 250, 252, 255), outline=(226, 232, 240, 255), width=1)
sym_light = symbol.copy()
sym_light.thumbnail((36, 36), Image.Resampling.LANCZOS)
canvas.paste(sym_light, (57, 535), sym_light)

# Login card mockup in light theme
draw.rounded_rectangle([(230, 200), (550, 550)], radius=12, fill=(255, 255, 255, 255), outline=(226, 232, 240, 255), width=1)
l_login = logo_light.copy()
l_login.thumbnail((180, 48), Image.Resampling.LANCZOS)
canvas.paste(l_login, (230 + (320 - l_login.width)//2, 230), l_login)


# Panel 2: Dark Theme (Right: x=620 to 1160)
# Background slate (#0f172a)
draw.rectangle([(620, 90), (1160, 900)], fill=(15, 23, 42, 255), outline=(51, 65, 85, 255), width=2)
# Header bar inside dark theme (#1e293b)
draw.rectangle([(620, 90), (1160, 155)], fill=(30, 41, 59, 255), outline=(51, 65, 85, 255), width=1)
# Draw Dark Header Logo
d_header = logo_dark.copy()
d_header.thumbnail((160, 32), Image.Resampling.LANCZOS)
canvas.paste(d_header, (640, 105), d_header)

# CRM Badge in dark
draw.rounded_rectangle([(640 + d_header.width + 8, 108), (640 + d_header.width + 48, 132)], radius=4, fill=(43, 179, 75, 40), outline=(43, 179, 75, 120), width=1)

# Sidebar mockup in dark theme (#111827)
draw.rectangle([(620, 155), (780, 500)], fill=(17, 24, 39, 255), outline=(51, 65, 85, 255), width=1)
# Sidebar dark logo
d_sidebar = logo_dark.copy()
d_sidebar.thumbnail((120, 26), Image.Resampling.LANCZOS)
canvas.paste(d_sidebar, (635, 175), d_sidebar)

# Collapsed sidebar with symbol in dark theme
draw.rectangle([(620, 520), (690, 880)], fill=(17, 24, 39, 255), outline=(51, 65, 85, 255), width=1)
sym_dark = symbol.copy()
sym_dark.thumbnail((36, 36), Image.Resampling.LANCZOS)
canvas.paste(sym_dark, (637, 535), sym_dark)

# Login card mockup in dark theme (#1e293b)
draw.rounded_rectangle([(810, 200), (1130, 550)], radius=12, fill=(30, 41, 59, 255), outline=(51, 65, 85, 255), width=1)
d_login = logo_dark.copy()
d_login.thumbnail((180, 48), Image.Resampling.LANCZOS)
canvas.paste(d_login, (810 + (320 - d_login.width)//2, 230), d_login)

out_preview_path = os.path.join(out_dir, "digipanda_theme_comparison_matrix.png")
canvas.save(out_preview_path)
print(f"Saved visual verification matrix to: {out_preview_path}")
