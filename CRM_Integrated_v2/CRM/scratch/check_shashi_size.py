import os
from PIL import Image

p = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\static\images\shashi_sign.png"
if os.path.exists(p):
    im = Image.open(p)
    print("shashi_sign.png size:", im.size)
