from PIL import Image
import numpy as np

src_path = r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\.user_uploaded\media_1793265481842_c385788b.png"
img = Image.open(src_path).convert("RGBA")

# Let's find the bounding box of the whole image
bbox = img.getbbox()
print("Whole logo bbox:", bbox)

# The first letter 'd' mark with the inner circle
# Let's inspect columns from x=0 to find where 'd' ends before the first 'i'
arr = np.array(img)
alpha = arr[:, :, 3]

# Column density
col_sum = np.sum(alpha > 0, axis=0)

# Find first non-zero column
first_col = np.where(col_sum > 0)[0][0]
print("First non-zero col:", first_col)

# Look for the gap between the initial 'd' and the first 'i'
for col in range(first_col + 150, first_col + 350):
    if col_sum[col] == 0:
        print(f"Gap found at col {col}!")
        break
