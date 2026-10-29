from PIL import Image, ImageDraw, ImageFont
import os

src_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\static\images\digipanda_logo.png"
orig = Image.open(src_path).convert("RGBA")
print("Original size:", orig.size)

# Find bounding box of non-transparent pixels
bbox = orig.getbbox()
print("BBox:", bbox)
# bbox is (left, upper, right, lower)
# Let's crop to bbox or keep original baseline
right_edge = bbox[2]
top_edge = bbox[1]
bottom_edge = bbox[3]
height = orig.size[1]
letter_height = bottom_edge - top_edge
print(f"Right edge: {right_edge}, Letter height: {letter_height}, Top: {top_edge}, Bottom: {bottom_edge}")

# We want to append "CRM" right after right_edge with appropriate spacing (~6px)
# Let's try to load a clean sans-serif font or draw CRM
try:
    font = ImageFont.truetype("arialbd.ttf", 52)
except Exception:
    try:
        font = ImageFont.truetype("calibrib.ttf", 54)
    except Exception:
        font = ImageFont.load_default()

# Measure "CRM"
test_img = Image.new("RGBA", (1, 1))
draw_test = ImageDraw.Draw(test_img)
crm_bbox = draw_test.textbbox((0, 0), "CRM", font=font)
crm_w = crm_bbox[2] - crm_bbox[0]
crm_h = crm_bbox[3] - crm_bbox[1]
print(f"CRM width: {crm_w}, height: {crm_h}")

new_width = right_edge + 8 + crm_w + 14
new_height = height

# Version 1: CRM in vibrant brand green (#2BB34B)
im_v1 = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
im_v1.paste(orig, (0, 0))
draw1 = ImageDraw.Draw(im_v1)
# Align baseline: bottom of 'anda' is around bottom_edge
text_y = bottom_edge - crm_h - 2
draw1.text((right_edge + 8, text_y), "CRM", fill=(43, 179, 75, 255), font=font)

# Version 2: CRM with C in blue (#124F91), R in green (#2BB34B), M in blue (#124F91) or with pill
# Let's also create SVG vector version
im_v1.save(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\static\images\digipanda_crm_logo.png")
print("Saved digipanda_crm_logo.png! Size:", im_v1.size)
