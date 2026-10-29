import os
from PIL import Image

path = r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\.user_uploaded\media_1793265481842_c385788b.png"

img = Image.open(path)
print("Dimensions:", img.size)
print("Mode:", img.mode)

# Check corner pixels to see background color
corners = [
    img.getpixel((0, 0)),
    img.getpixel((img.size[0] - 1, 0)),
    img.getpixel((0, img.size[1] - 1)),
    img.getpixel((img.size[0] - 1, img.size[1] - 1))
]
print("Corners:", corners)
