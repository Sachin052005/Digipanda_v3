from PIL import Image

path = r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\.user_uploaded\media_1792832948629_962b5816.png"
im = Image.open(path)
print("Image size:", im.size, "Mode:", im.mode)
