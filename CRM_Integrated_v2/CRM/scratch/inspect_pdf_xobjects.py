import pypdf
import sys

pdf_path = r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\scratch\digipanda_verified_receipt.pdf'
reader = pypdf.PdfReader(pdf_path)
page = reader.pages[0]

# Inspect resources
res = page.get('/Resources')
print("Resources keys:", res.keys())
xobjs = res.get('/XObject')
if xobjs:
    print("XObject keys:", xobjs.keys())
    for k in xobjs.keys():
        obj = xobjs[k]
        print(f"XObject {k}: Subtype={obj.get('/Subtype')}, Width={obj.get('/Width')}, Height={obj.get('/Height')}")
