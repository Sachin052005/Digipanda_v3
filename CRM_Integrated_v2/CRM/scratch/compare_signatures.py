from PIL import Image

p = r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\.user_uploaded\media_1793262562651_161531a5.png"
im = Image.open(p)
print("media_1793262562651_161531a5.png size:", im.size)

p2 = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\static\images\shashi_sign.png"
im2 = Image.open(p2)
print("shashi_sign.png size:", im2.size)
