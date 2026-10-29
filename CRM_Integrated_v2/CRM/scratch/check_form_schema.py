import os, sys
sys.argv.append("check")
sys.path.insert(0, r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
os.environ['DB_ENGINE'] = 'django.db.backends.sqlite3'
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from leads.models import WalkinEnquiryForm
import json

forms = list(WalkinEnquiryForm.objects.all())
print(f"Total forms: {len(forms)}")
for f in forms:
    print(f"ID={f.id}, Title={f.title}, Slug={f.slug}, IsDefault={f.is_default}, Active={f.is_active}")
    print("Schema keys:", list(f.form_schema.keys()) if isinstance(f.form_schema, dict) else type(f.form_schema))
os._exit(0)
