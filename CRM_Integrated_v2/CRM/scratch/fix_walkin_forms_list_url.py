path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\admin\walkin_forms_list.html"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace escaped \' with '
new_content = content.replace(r"{% url \'public_student_enquiry_form\' %}", "{% url 'public_student_enquiry_form' %}")

with open(path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Fixed walkin_forms_list.html url tag quotes successfully!")
