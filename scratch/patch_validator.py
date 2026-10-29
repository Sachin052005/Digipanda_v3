path_val = r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\chat\automation\validator.py'
with open(path_val, 'r', encoding='utf-8') as f:
    text_val = f.read()

target_val = """        elif ntype == "assign_telecaller":
            mode = node.get("mode") or node.get("data", {}).get("mode", "auto")
            tc_id = node.get("telecaller_id") or node.get("data", {}).get("telecaller_id")
            if mode == "specific":
                from accounts.models import User
                if not tc_id or not User.get_telecallers_queryset().filter(pk=tc_id, is_active=True).exists():
                    errors.append({"node_id": nid, "message": "Assign Telecaller step must select an active telecaller."})"""

repl_val = """        elif ntype == "assign_telecaller":
            mode = node.get("mode") or node.get("data", {}).get("mode", "auto")
            tc_id = node.get("telecaller_id") or node.get("data", {}).get("telecaller_id")
            if mode == "specific":
                from accounts.models import User
                if not tc_id or not User.get_telecallers_queryset().filter(pk=tc_id, is_active=True).exists():
                    errors.append({"node_id": nid, "message": "Assign Telecaller step must select an active telecaller."})

        elif ntype == "buttons":
            options = node.get("options") or node.get("data", {}).get("options", [])
            if len(options) == 0:
                errors.append({"node_id": nid, "message": "Buttons step must have at least 1 option."})
            elif len(options) > 3:
                errors.append({"node_id": nid, "message": f"Buttons step has {len(options)} options. Meta WhatsApp Cloud API allows a maximum of 3 buttons. Use a List Menu for 4 to 10 choices."})

        elif ntype == "list":
            source = node.get("source") or node.get("data", {}).get("source", "custom")
            if source != "database":
                sections = node.get("sections") or node.get("data", {}).get("sections", [])
                total_rows = 0
                for s in sections:
                    for r in s.get("rows", []):
                        total_rows += 1
                        rtitle = str(r.get("title", "")).strip()
                        if len(rtitle) > 24:
                            errors.append({"node_id": nid, "message": f"List option '{rtitle}' has {len(rtitle)} characters. WhatsApp limits list options to 24 characters maximum."})
                if total_rows == 0:
                    errors.append({"node_id": nid, "message": "List Menu step must have at least 1 menu option."})
                elif total_rows > 10:
                    errors.append({"node_id": nid, "message": f"List Menu has {total_rows} options. WhatsApp limits list menus to 10 options maximum."})"""

text_val_norm = text_val.replace('\r\n', '\n')
target_val_norm = target_val.replace('\r\n', '\n')
assert target_val_norm in text_val_norm, "Target validator not found"
text_val_norm = text_val_norm.replace(target_val_norm, repl_val.replace('\r\n', '\n'), 1)

with open(path_val, 'w', encoding='utf-8', newline='\r\n') as f:
    f.write(text_val_norm)

print("Successfully updated validator.py")
