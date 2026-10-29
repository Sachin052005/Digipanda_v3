import os, sys
sys.argv.append("check")
sys.path.append(r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from leads.models import WalkinEnquiryForm, Lead
from products.models import Product
from lead_channels.models import Channel
from branches.models import Branch

print('WalkinEnquiryForms count:', WalkinEnquiryForm.objects.count())
for f in WalkinEnquiryForm.objects.all():
    print(f' - ID: {f.id}, Title: {f.title}, Slug: {f.slug}, IsDefault: {f.is_default}, IsActive: {f.is_active}, Branch: {f.branch}')

print('Products count:', Product.objects.count())
for p in Product.objects.all()[:10]:
    print(f' - Product: {p.id}, Name: {p.name}, Status: {p.status}')

print('Branches count:', Branch.objects.count())
for b in Branch.objects.all()[:10]:
    print(f' - Branch: {b.id}, Name: {b.name}, Status: {b.status}')

os._exit(0)

