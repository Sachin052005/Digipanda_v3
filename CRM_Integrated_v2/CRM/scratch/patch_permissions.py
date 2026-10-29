path = r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\accounts\permissions.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read()

target = """    if user.role == UserRole.SALES_HEAD:
        return lead.branch_id in get_accessible_branch_ids(user)"""

replacement = """    if user.role == UserRole.SALES_HEAD:
        if lead.assigned_sales_head_id == user.id:
            return True
        return lead.branch_id in get_accessible_branch_ids(user)"""

if target.replace('\r\n', '\n') in code.replace('\r\n', '\n'):
    code = code.replace('\r\n', '\n').replace(target.replace('\r\n', '\n'), replacement.replace('\r\n', '\n'))
    with open(path, 'w', encoding='utf-8') as f:
        f.write(code)
    print("Updated can_access_lead for SALES_HEAD in permissions.py")
else:
    print("Target not found in permissions.py")
