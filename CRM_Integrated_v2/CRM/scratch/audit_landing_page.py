import os, sys
sys.path.insert(0, 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.test import RequestFactory
from accounts.views_public import landing_page_view

rf = RequestFactory()
req = rf.get('/')
req.user = type('Anon', (), {'is_authenticated': False})()
res = landing_page_view(req)
print(f"Status Code: {res.status_code}")
print(f"Content Length: {len(res.content)} bytes ({len(res.content)/1024:.1f} KB)")

# Analyze content structure
html = res.content.decode('utf-8')
import re
styles = re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL)
scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
script_srcs = re.findall(r'<script[^>]+src=[\'"]([^\'"]+)[\'"]', html)

print(f"Embedded <style> count: {len(styles)}, Total style length: {sum(len(s) for s in styles)} chars")
print(f"External <script src> files: {len(script_srcs)}")
for s in script_srcs:
    print(f"  - {s}")
print(f"Inline script length: {sum(len(s) for s in scripts)} chars")

sections = re.findall(r'<section[^>]*class=[\'"]([^\'"]*)[\'"][^>]*id=[\'"]?([^\'\"\s>]*)[\'"]?', html)
print(f"\nSections found ({len(sections)}):")
for c, sid in sections:
    print(f"  - id='{sid}' class='{c}'")
