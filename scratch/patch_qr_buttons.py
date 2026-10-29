import os

BASE_DIR = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM"

# 1. Update branches_list.html
p1 = os.path.join(BASE_DIR, "templates", "admin", "branches_list.html")
with open(p1, "r", encoding="utf-8") as f:
    c1 = f.read()

old_b_actions = '<a href="{% url \'admin_branch_edit\' br.pk %}" class="btn btn-secondary btn-sm">Edit</a>'
new_b_actions = '<a href="{% url \'branch_qr_standee\' br.pk %}" target="_blank" class="btn btn-secondary btn-sm" title="Print Student Walk-in QR Standee" style="display: inline-flex; align-items: center; gap: 4px;"><span>📷 QR Standee</span></a>\n                ' + old_b_actions

if "branch_qr_standee" not in c1 and old_b_actions in c1:
    c1 = c1.replace(old_b_actions, new_b_actions)
    with open(p1, "w", encoding="utf-8") as f:
        f.write(c1)
    print("Patched branches_list.html with QR Standee button")

# 2. Update receptionist dashboard
p2 = os.path.join(BASE_DIR, "templates", "receptionist", "dashboard.html")
with open(p2, "r", encoding="utf-8") as f:
    c2 = f.read()

old_rec_actions = '<button type="button" class="btn btn-primary" onclick="openRegisterStudentModal()"'
new_rec_actions = """<a href="{% url 'receptionist_qr_standee' %}" target="_blank" class="btn btn-secondary" style="display: inline-flex; align-items: center; gap: 6px; font-weight: 600;">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
      <span>Reception QR Standee</span>
    </a>
    """ + old_rec_actions

if "receptionist_qr_standee" not in c2 and old_rec_actions in c2:
    c2 = c2.replace(old_rec_actions, new_rec_actions)
    with open(p2, "w", encoding="utf-8") as f:
        f.write(c2)
    print("Patched receptionist/dashboard.html with QR Standee button")

# 3. Update admin walkin_desk.html
p3 = os.path.join(BASE_DIR, "templates", "admin", "walkin_desk.html")
with open(p3, "r", encoding="utf-8") as f:
    c3 = f.read()

old_desk_actions = '<button type="button" class="btn btn-primary" onclick="openNewVisitorModal()">'
new_desk_actions = """{% if selected_branch %}
    <a href="{% url 'branch_qr_standee' selected_branch.id %}" target="_blank" class="btn btn-secondary" style="display: inline-flex; align-items: center; gap: 6px;">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
      <span>QR Standee</span>
    </a>
    {% endif %}
    """ + old_desk_actions

if "branch_qr_standee" not in c3 and old_desk_actions in c3:
    c3 = c3.replace(old_desk_actions, new_desk_actions)
    with open(p3, "w", encoding="utf-8") as f:
        f.write(c3)
    print("Patched admin/walkin_desk.html with QR Standee button")

print("Templates updated successfully.")
