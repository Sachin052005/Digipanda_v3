from PIL import Image

img = Image.open(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\scratch\receipt_page0_visual.png")
w, h = img.size
print(f"Full page image size: {w}x{h}")

# Search for non-white pixels
# Crop bottom half: y from h//2 to h
bottom_half = img.crop((0, int(h * 0.4), w, h))
bottom_half.save(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\scratch\receipt_bottom_half.png")
print("Saved receipt_bottom_half.png")
