from PIL import Image
from collections import Counter

img = Image.open(r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\.user_uploaded\media_1793265481842_c385788b.png")
print("Size:", img.size)

# Sample non-transparent pixels
pixels = list(img.getdata())
opaque_pixels = [p for p in pixels if p[3] > 50]

print("Total opaque pixels:", len(opaque_pixels))

# Let's cluster or find dominant colors
def color_desc(p):
    r, g, b, a = p
    if r < 50 and g > 120 and b < 80:
        return "GREEN"
    elif r < 50 and g < 100 and b > 140:
        return "BLUE"
    elif r < 60 and g < 60 and b < 60:
        return "BLACK/DARK"
    elif r > 200 and g > 200 and b > 200:
        return "WHITE"
    else:
        return f"OTHER({r},{g},{b})"

desc_counts = Counter(color_desc(p) for p in opaque_pixels)
print("Color distribution:")
for k, v in desc_counts.most_common(10):
    print(f"  {k}: {v} ({v*100/len(opaque_pixels):.1f}%)")
