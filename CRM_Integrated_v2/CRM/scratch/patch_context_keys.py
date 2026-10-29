file_path = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/leads/views_enrollment.py'
with open(file_path, 'r', encoding='utf-8') as f:
    c = f.read()

target = "'invoice_number': invoice_number,"
replacement = "'invoice_number': invoice_number,\n        'receipt_number': invoice_number,\n        'payment_date': invoice_date,"

if target in c:
    c = c.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(c)
    print("Successfully patched context keys!")
else:
    print("Target not found!")
