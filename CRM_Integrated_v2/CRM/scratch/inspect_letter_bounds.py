from PIL import Image

im = Image.open(r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\.user_uploaded\media_1792832948629_962b5816.png").convert("RGBA")
w, h = im.size

# Let's inspect column by column at the right end (x from 150 to 261) to find where the last letter 'a' is
# and find its top and bottom Y coordinates
last_letter_cols = []
for x in range(150, w):
    col_pixels = []
    for y in range(h):
        r, g, b, a = im.getpixel((x, y))
        # if pixel is dark (r<100, g<100, b<100)
        if r < 100 and g < 100 and b < 100:
            col_pixels.append(y)
    if col_pixels:
        last_letter_cols.append((x, min(col_pixels), max(col_pixels)))

if last_letter_cols:
    last_x = last_letter_cols[-1][0]
    min_y_letter = min(c[1] for c in last_letter_cols)
    max_y_letter = max(c[2] for c in last_letter_cols)
    print(f"Last letter ends at x={last_x}, y range: [{min_y_letter}, {max_y_letter}] (height={max_y_letter-min_y_letter+1})")

# Let's inspect the 'p' letter to see its colors and coordinates
green_pixels = []
for x in range(w):
    for y in range(h):
        r, g, b, a = im.getpixel((x, y))
        # green letter p has g > 150, r < 100, b < 100
        if g > 150 and r < 100 and b < 120:
            green_pixels.append((x, y, (r, g, b)))

if green_pixels:
    gx_min = min(p[0] for p in green_pixels)
    gx_max = max(p[0] for p in green_pixels)
    gy_min = min(p[1] for p in green_pixels)
    gy_max = max(p[1] for p in green_pixels)
    print(f"Green 'p' range: x=[{gx_min}, {gx_max}], y=[{gy_min}, {gy_max}]")
