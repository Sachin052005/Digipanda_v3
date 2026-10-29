from PIL import Image

im = Image.open(r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\.user_uploaded\media_1792832948629_962b5816.png").convert("RGBA")
w, h = im.size

# Look at 'd' in 'anda', which is between x=200 and 235
d_pixels = []
for x in range(200, 235):
    for y in range(h):
        r, g, b, a = im.getpixel((x, y))
        if r < 100 and g < 100 and b < 100:
            d_pixels.append((x, y))

if d_pixels:
    print(f"'d' in 'anda': x=[{min(p[0] for p in d_pixels)}, {max(p[0] for p in d_pixels)}], y=[{min(p[1] for p in d_pixels)}, {max(p[1] for p in d_pixels)}]")
