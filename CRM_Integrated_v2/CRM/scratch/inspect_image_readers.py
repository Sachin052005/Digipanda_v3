from xhtml2pdf.xhtml2pdf_reportlab import PmlImage, PmlImageReader

sig_path = r"D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/static/images/shashi_sign.png"
logo_path = r"D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/static/images/digipanda_logo.png"

with open(logo_path, "rb") as f:
    logo_data = f.read()
with open(sig_path, "rb") as f:
    sig_data = f.read()

im1 = PmlImage(logo_data, src=logo_path)
im2 = PmlImage(sig_data, src=sig_path)

reader1 = im1.getImage()
reader2 = im2.getImage()

print("reader1 fileName:", getattr(reader1, 'fileName', None))
print("reader2 fileName:", getattr(reader2, 'fileName', None))
print("reader1 identity:", reader1.identity() if hasattr(reader1, 'identity') else None)
print("reader2 identity:", reader2.identity() if hasattr(reader2, 'identity') else None)
