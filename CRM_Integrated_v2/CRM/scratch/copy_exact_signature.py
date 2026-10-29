import os
import shutil
from PIL import Image

src_path = r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\.user_uploaded\media_1793262562651_161531a5.png"
dest_dir = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\static\images"
dest_file1 = os.path.join(dest_dir, "shashi_sign.png")
dest_file2 = os.path.join(dest_dir, "Shashi_Sign.png")

# Byte-for-byte exact copy
shutil.copyfile(src_path, dest_file1)
shutil.copyfile(src_path, dest_file2)

img1 = Image.open(dest_file1)
print(f"Copied exact signature without alterations:")
print(f"Destination: {dest_file1}")
print(f"Size: {img1.size}, Format: {img1.format}, Mode: {img1.mode}, Bytes: {os.path.getsize(dest_file1)}")
