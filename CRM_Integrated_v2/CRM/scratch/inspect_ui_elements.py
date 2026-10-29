import os
import re
import glob

CRM_DIR = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM'

print("=== 1. CHECKING TEMPLATE BLOCK STRUCTURES ===")
template_files = glob.glob(os.path.join(CRM_DIR, 'templates', '**', '*.html'), recursive=True)
template_files += glob.glob(os.path.join(CRM_DIR, 'fb_leads', 'templates', '**', '*.html'), recursive=True)
template_files += glob.glob(os.path.join(CRM_DIR, 'chat', 'templates', '**', '*.html'), recursive=True)

block_issues = []
for tf in template_files:
    with open(tf, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Check if block title has missing endblock before block content
    if '{% block title %}' in content:
        title_part = content.split('{% block title %}', 1)[1]
        if '{% block content %}' in title_part:
            # Check if endblock is before block content
            endblock_idx = title_part.find('{% endblock %}')
            content_idx = title_part.find('{% block content %}')
            if endblock_idx > content_idx or endblock_idx == -1:
                block_issues.append((tf, "block content is inside or after unclosed block title!"))
            elif content_idx - endblock_idx > 500:
                # Content between endblock title and block content
                inter_content = title_part[endblock_idx+len('{% endblock %}'):content_idx].strip()
                if len(inter_content) > 100:
                    block_issues.append((tf, f"Large content ({len(inter_content)} chars) between block title and block content!"))

print(f"Total templates checked: {len(template_files)}")
print(f"Block structural issues found: {len(block_issues)}")
for path, issue in block_issues:
    print(f"  - {os.path.relpath(path, CRM_DIR)}: {issue}")

print("\n=== 2. CSS DESIGN TOKENS & SYSTEM INSPECTION ===")
css_dir = os.path.join(CRM_DIR, 'static', 'css')
css_files = glob.glob(os.path.join(css_dir, '*.css'))

for cf in css_files:
    fname = os.path.basename(cf)
    with open(cf, 'r', encoding='utf-8', errors='ignore') as f:
        css = f.read()
    
    # Find CSS custom properties
    custom_props = set(re.findall(r'--[a-zA-Z0-9_-]+', css))
    media_queries = re.findall(r'@media\s*([^{]+)\{', css)
    important_count = len(re.findall(r'!important', css))
    hardcoded_hex = len(re.findall(r'#[0-9a-fA-F]{3,8}\b', css))
    print(f"\nFile: {fname} ({len(css)} bytes)")
    print(f"  Custom properties: {len(custom_props)}")
    print(f"  Media queries: {len(media_queries)}")
    print(f"  !important usages: {important_count}")
    print(f"  Hardcoded HEX colors: {hardcoded_hex}")
    # Sample media queries
    unique_mq = sorted(list(set([m.strip() for m in media_queries])))
    print(f"  Distinct Breakpoints/Media: {unique_mq[:6]}")

print("\n=== 3. JS ASSETS & COMPONENT ENGINE AUDIT ===")
js_dir = os.path.join(CRM_DIR, 'static', 'js')
js_files = glob.glob(os.path.join(js_dir, '*.js'))

for jf in js_files:
    fname = os.path.basename(jf)
    with open(jf, 'r', encoding='utf-8', errors='ignore') as f:
        js = f.read()
    event_listeners = len(re.findall(r'\.addEventListener\(', js))
    console_logs = len(re.findall(r'console\.(log|warn|error)', js))
    print(f"  {fname}: {len(js)} bytes | {event_listeners} event listeners | {console_logs} console calls")
