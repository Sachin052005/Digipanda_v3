import os
from PIL import Image

p = r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\.user_uploaded\media_1793262562651_161531a5.png"
print(f"File exists: {os.path.exists(p)}")
img = Image.open(p)
print(f"Size: {img.size}, format: {img.format}, mode: {img.mode}")
