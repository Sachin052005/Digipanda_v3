path = r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\leads\detail_service.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

target = """    # 5. Field values mapping
    val_degree = find_val(['degree', 'qualification', 'education'])
    val_passed_out = find_val(['passedout', 'passed out', 'year of pass', 'passing year', 'yop'])
    val_purpose = find_val(['purpose', 'objective', 'reason', 'intent'])
    val_base_branch = lead.branch.name if lead.branch else find_val(['branch', 'base branch'])
    val_pref_branch = ", ".join(lead.get_all_branch_names()) if lead.secondary_branches.exists() else find_val(['preferred branch', 'pref branch'])
    val_working_status = find_val(['working status', 'employment status', 'working', 'job status', 'status of work'])
    val_total_exp = find_val(['total experience', 'experience', 'exp', 'work experience'])
    val_pref_exam_loc = find_val(['preferred exam location', 'exam location', 'exam city'])
    val_join_pref = find_val(['how would you like to join the course', 'joining preference', 'mode', 'course mode', 'batch mode'])"""

replacement = """    # 5. Field values mapping
    val_degree = find_val(['degree', 'qualification', 'education'])
    val_passed_out = find_val(['passed_out', 'passedout', 'passed out', 'year of pass', 'passing year', 'yop'])
    val_purpose = find_val(['purpose', 'objective', 'reason', 'intent'])
    val_base_branch = lead.branch.name if lead.branch else find_val(['branch', 'base branch'])
    val_pref_branch = ", ".join(lead.get_all_branch_names()) if lead.secondary_branches.exists() else find_val(['pref_branch', 'preferred branch', 'pref branch'])
    val_working_status = find_val(['working_status', 'working status', 'employment status', 'working', 'job status', 'status of work'])
    val_total_exp = find_val(['total_experience', 'total experience', 'experience', 'exp', 'work experience'])
    val_pref_exam_loc = find_val(['pref_exam_loc', 'preferred exam location', 'exam location', 'exam city'])
    val_join_pref = find_val(['join_preference', 'how would you like to join the course', 'joining preference', 'mode', 'course mode', 'batch mode'])"""

text_norm = text.replace('\r\n', '\n')
target_norm = target.replace('\r\n', '\n')
assert target_norm in text_norm, "Target not found"

text_norm = text_norm.replace(target_norm, replacement.replace('\r\n', '\n'), 1)

with open(path, 'w', encoding='utf-8', newline='\r\n') as f:
    f.write(text_norm)

print("Updated detail_service.py field mappings")
