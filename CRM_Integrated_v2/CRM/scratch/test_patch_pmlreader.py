from reportlab.lib.utils import ImageReader
from xhtml2pdf import xhtml2pdf_reportlab

# Monkey patch or subclass check
print("Base classes of PmlImageReader:", xhtml2pdf_reportlab.PmlImageReader.__bases__)

# If we patch PmlImageReader to inherit from ImageReader or provide getRGBData
print("Has getRGBData on PmlImageReader:", hasattr(xhtml2pdf_reportlab.PmlImageReader, 'getRGBData'))
