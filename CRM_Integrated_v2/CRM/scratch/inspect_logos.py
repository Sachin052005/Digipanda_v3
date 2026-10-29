from PIL import Image

for name, path in [
    ("Symbol", r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\.user_uploaded\media_1792828071349_adb7f9cb.png"),
    ("Full Logo", r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\.user_uploaded\media_1792828076643_f22ca642.png")
]:
    im = Image.open(path)
    print(f"=== {name} ===")
    print(f"Size: {im.size}, Mode: {im.mode}")
    corners = [im.getpixel((0, 0)), im.getpixel((im.width-1, 0)), im.getpixel((0, im.height-1)), im.getpixel((im.width-1, im.height-1))]
    print("Corners:", corners)

