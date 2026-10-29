# -*- coding: utf-8 -*-
p = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/leads/intake.py'
with open(p, 'r', encoding='utf-8') as f:
    text = f.read()

sub = 'action_taken="UPDATED_AFTER_10_DAYS"'
idx = text.find(sub)
if idx != -1:
    prev_rec = text.rfind("record_type='INCOMING_DUPLICATE'", 0, idx)
    if prev_rec != -1:
        text = text[:prev_rec] + "record_type='REENQUIRY_DUPLICATE'" + text[prev_rec + len("record_type='INCOMING_DUPLICATE'"):]
        with open(p, 'w', encoding='utf-8') as f:
            f.write(text)
        print('Updated Rule B to REENQUIRY_DUPLICATE!')
    else:
        print('prev_rec not found')
else:
    print('action_taken not found')
