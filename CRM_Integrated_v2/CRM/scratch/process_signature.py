import os
from PIL import Image

src_path = r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\.user_uploaded\media_1793260532880_e7819fb5.png"
dest_dir = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\static\images"
dest_path1 = os.path.join(dest_dir, "shashi_sign.png")
dest_path2 = os.path.join(dest_dir, "Shashi_Sign.png")

img = Image.open(src_path).convert("RGBA")
print(f"Original size: {img.size}")

# Find bounding box of non-white pixels
# Convert to grayscale to detect dark signature ink
gray = img.convert("L")
# Ink is dark (low values, e.g. < 200)
bbox = None
width, height = img.size

min_x, min_y, max_x, max_y = width, height, 0, 0
has_ink = False

for y in range(height):
    for x in range(width):
        r, g, b, a = img.getpixel((x, y))
        # Check if pixel is ink (not pure white and alpha > 0)
        if a > 30 and (r < 230 or g < 230 or b < 230):
            has_ink = True
            if x < min_x: min_x = x
            if x > max_x: max_x = x
            if y < min_y: min_y = y
            if y > max_y: max_y = y

if has_ink:
    # Add a comfortable 15px padding
    pad = 15
    crop_box = (
        max(0, min_x - pad),
        max(0, min_y - pad),
        min(width, max_x + pad),
        min(height, max_y + pad)
    )
    print(f"Detected ink bounding box with padding: {crop_box}")
    cropped = img.crop(crop_box)
else:
    print("Could not find ink, using original image")
    cropped = img

# Save cropped version with high quality
cropped.save(dest_path1, format="PNG")
cropped.save(dest_path2, format="PNG")
print(f"Saved cropped signature ({cropped.size}) to:\n - {dest_path1}\n - {dest_path2}")
