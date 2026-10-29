import pypdf
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

pdf_path = r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\scratch\digipanda_verified_receipt.pdf'
reader = pypdf.PdfReader(pdf_path)
page = reader.pages[0]
text = page.extract_text()
print('=== EXTRACTED PDF TEXT ===')
for line in text.split('\n'):
    if any(k in line.lower() for k in ['sign', 'digipanda', 'techpanda', 'shashi', 'authorised']):
        print(line)

print('\n=== CHECK IMAGES IN PDF ===')
print(f"Number of images on page 0: {len(page.images)}")
for img in page.images:
    print(f"Image name: {img.name}, length: {len(img.data)} bytes")
