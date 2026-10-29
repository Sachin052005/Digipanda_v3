# -*- coding: utf-8 -*-
p = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/leads/duplicates.py'
with open(p, 'r', encoding='utf-8') as f:
    text = f.read()

target = """                dup_rec = DuplicateLeadRecord.objects.create(
                    original_lead=existing_lead,
                    name=name or existing_lead.name,"""

replacement = """                dup_rec = DuplicateLeadRecord.objects.create(
                    original_lead=existing_lead,
                    record_type='REENQUIRY_DUPLICATE',
                    name=name or existing_lead.name,"""

if target in text:
    text = text.replace(target, replacement)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(text)
    print("Updated line 672 in duplicates.py!")
else:
    print("Target not found in duplicates.py")
