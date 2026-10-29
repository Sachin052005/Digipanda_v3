from PIL import Image, ImageDraw, ImageFont

im = Image.new("RGBA", (400, 100), (255, 255, 255, 0))
font = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 52)

draw = ImageDraw.Draw(im)
bbox = draw.textbbox((0, 0), "CRM", font=font)
print("textbbox:", bbox)
crm_h = bbox[3] - bbox[1]
print("crm_h:", crm_h)

# If bottom of text (bbox[3]) is at y=73, then text_y = 73 - bbox[3]
text_y = 73 - bbox[3]
print("Computed text_y:", text_y, "Top will be at:", text_y + bbox[1], "Bottom will be at:", text_y + bbox[3])
