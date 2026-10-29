with open(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\chat\views.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace(
    'message = "Only Admin and Superadmin can manage WhatsApp automations and numbers."',
    'message = "Only Admin, Superadmin, and Sales Head can manage WhatsApp automations and numbers."'
)
text = text.replace(
    'raise PermissionDenied("Only Admin and Superadmin can manage WhatsApp automations.")',
    'raise PermissionDenied("Only Admin, Superadmin, and Sales Head can manage WhatsApp automations.")'
)

with open(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\chat\views.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Updated chat/views.py permission messages!")
