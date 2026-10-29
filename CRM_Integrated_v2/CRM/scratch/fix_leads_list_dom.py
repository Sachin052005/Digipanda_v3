import os

file_path = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/templates/admin/leads_list.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace block title defect
target_top = "{% block title %}Leads - DigipandaCRM\n<!-- LEFT FILTER DRAWER"
target_top_crlf = "{% block title %}Leads - DigipandaCRM\r\n<!-- LEFT FILTER DRAWER"

replacement_top = "{% block title %}Leads - DigipandaCRM{% endblock %}\n\n{% block content %}\n<!-- LEFT FILTER DRAWER"
replacement_top_crlf = "{% block title %}Leads - DigipandaCRM{% endblock %}\r\n\r\n{% block content %}\r\n<!-- LEFT FILTER DRAWER"

if target_top_crlf in content:
    content = content.replace(target_top_crlf, replacement_top_crlf, 1)
    print("Replaced top with CRLF")
elif target_top in content:
    content = content.replace(target_top, replacement_top, 1)
    print("Replaced top with LF")
else:
    print("Target top not found!")

# Replace redundant endblock/block content at lines 244-249
target_mid_crlf = "</script>\r\n\r\n{% endblock %}\r\n\r\n{% block content %}\r\n<div class=\"page-header\""
target_mid_lf = "</script>\n\n{% endblock %}\n\n{% block content %}\n<div class=\"page-header\""

replacement_mid_crlf = "</script>\r\n\r\n<div class=\"page-header\""
replacement_mid_lf = "</script>\n\n<div class=\"page-header\""

if target_mid_crlf in content:
    content = content.replace(target_mid_crlf, replacement_mid_crlf, 1)
    print("Replaced mid with CRLF")
elif target_mid_lf in content:
    content = content.replace(target_mid_lf, replacement_mid_lf, 1)
    print("Replaced mid with LF")
else:
    print("Target mid not found!")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated leads_list.html successfully.")
