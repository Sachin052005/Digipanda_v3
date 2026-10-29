from xhtml2pdf.xhtml2pdf_reportlab import PmlImage, PmlImageReader
from io import BytesIO

im1 = PmlImageReader(BytesIO(b"fake1"))
im2 = PmlImageReader(BytesIO(b"fake2"))

print("str(im1):", str(im1))
print("str(im2):", str(im2))
print("repr(im1):", repr(im1))
print("repr(im2):", repr(im2))
print("isinstance(im1, ImageReader):", hasattr(im1, 'getRGBData'))
from reportlab.lib.utils import ImageReader
print("isinstance ImageReader:", isinstance(im1, ImageReader))
