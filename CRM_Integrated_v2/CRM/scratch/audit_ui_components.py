import os
import re
import glob
from collections import Counter

CRM_DIR = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM'

template_files = glob.glob(os.path.join(CRM_DIR, 'templates', '**', '*.html'), recursive=True)
template_files += glob.glob(os.path.join(CRM_DIR, 'fb_leads', 'templates', '**', '*.html'), recursive=True)
template_files += glob.glob(os.path.join(CRM_DIR, 'chat', 'templates', '**', '*.html'), recursive=True)

button_classes = Counter()
badge_classes = Counter()
table_classes = Counter()
modal_ids = []
aria_attributes = Counter()
inline_styles_count = 0
total_forms = 0
role_templates = Counter()

for tf in template_files:
    rel = os.path.relpath(tf, CRM_DIR)
    folder = rel.split(os.sep)[1] if len(rel.split(os.sep)) > 1 else 'root'
    role_templates[folder] += 1
    
    with open(tf, 'r', encoding='utf-8', errors='ignore') as f:
        html = f.read()
    
    # Buttons
    btn_matches = re.findall(r'class=[\'"]([^\'"]*btn[^\'"]*)[\'"]', html)
    for bm in btn_matches:
        for c in bm.split():
            if 'btn' in c:
                button_classes[c] += 1
                
    # Badges
    badge_matches = re.findall(r'class=[\'"]([^\'"]*badge[^\'"]*)[\'"]', html)
    for bdm in badge_matches:
        for c in bdm.split():
            if 'badge' in c:
                badge_classes[c] += 1
                
    # Tables
    tbl_matches = re.findall(r'<table[^>]*class=[\'"]([^\'"]*)[\'"]', html)
    for tm in tbl_matches:
        for c in tm.split():
            table_classes[c] += 1
            
    # Modals
    m_matches = re.findall(r'<div[^>]+id=[\'"]([^\'"]*modal[^\'"]*)[\'"]', html, re.I)
    modal_ids.extend(m_matches)
    
    # ARIA
    arias = re.findall(r'(aria-[a-z]+)=', html)
    for a in arias:
        aria_attributes[a] += 1
        
    # Inline styles
    inline_styles_count += len(re.findall(r'style=[\'"][^\'"]*[\'"]', html))
    
    # Forms
    total_forms += len(re.findall(r'<form\b', html))

print(f"Total templates scanned: {len(template_files)}")
print(f"Role template distribution: {role_templates.most_common()}")
print(f"\nTop Button classes ({len(button_classes)} distinct): {button_classes.most_common(12)}")
print(f"\nTop Badge classes ({len(badge_classes)} distinct): {badge_classes.most_common(12)}")
print(f"\nTop Table classes ({len(table_classes)} distinct): {table_classes.most_common(10)}")
print(f"\nDistinct modal IDs discovered: {len(set(modal_ids))}")
print(f"Total forms across templates: {total_forms}")
print(f"Total inline style attributes: {inline_styles_count}")
print(f"ARIA attributes usage: {aria_attributes.most_common(10)}")
