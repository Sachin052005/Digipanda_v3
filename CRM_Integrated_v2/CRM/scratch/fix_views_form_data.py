views_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\leads\views_walkin.py"
with open(views_path, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    "'form_data': request.POST,",
    "'form_data': form_data_dict,\n                'token_preview': token_preview,"
)

with open(views_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated form_data in views_walkin.py")
