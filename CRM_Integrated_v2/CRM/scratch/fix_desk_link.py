desk_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\admin\walkin_desk.html"
with open(desk_path, "r", encoding="utf-8") as f:
    c = f.read()

c = c.replace(
    '<a href="{% url \'public_student_enquiry_form\' %}" target="_blank" class="btn btn-secondary"',
    '<a href="{% if selected_branch %}{% url \'public_student_enquiry_branch\' selected_branch.id %}{% else %}{% url \'public_student_enquiry_form\' %}{% endif %}" target="_blank" class="btn btn-secondary"'
)

with open(desk_path, "w", encoding="utf-8") as f:
    f.write(c)
print("Updated walkin_desk branch link")
