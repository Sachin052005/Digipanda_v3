from xhtml2pdf.xhtml2pdf_reportlab import PmlImage, PmlImageReader
from reportlab.lib.utils import ImageReader
from io import BytesIO

sig_path = r"D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/static/images/shashi_sign.png"
logo_path = r"D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/static/images/digipanda_logo.png"

with open(logo_path, "rb") as f:
    logo_data = f.read()
with open(sig_path, "rb") as f:
    sig_data = f.read()

im1 = PmlImageReader(BytesIO(logo_data))
im2 = PmlImageReader(BytesIO(sig_data))

print("str(im1):", str(im1))
print("str(im2):", str(im2))
print("isinstance ImageReader im1:", isinstance(im1, ImageReader))
print("isinstance ImageReader im2:", isinstance(im2, ImageReader))
