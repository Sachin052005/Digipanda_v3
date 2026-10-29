import os

templates = [
    r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\admin\lead_create.html',
    r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\admin\lead_edit.html',
    r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\manager\lead_create.html',
    r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\manager\lead_edit.html',
    r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\telecaller\lead_create.html',
    r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\telecaller\lead_edit.html',
]

error_banner = """        {% if form.errors %}
        <div class="alert alert-danger" style="margin-bottom: 20px; border-radius: 8px;">
          <strong style="display: block; margin-bottom: 6px;">Please fix the following validation errors:</strong>
          <ul style="margin: 0 0 0 20px; padding: 0;">
            {% for field, errors in form.errors.items %}
              {% for error in errors %}
                <li><strong>{% if field != '__all__' %}{{ field|title }}{% else %}General{% endif %}:</strong> {{ error }}</li>
              {% endfor %}
            {% endfor %}
          </ul>
        </div>
        {% endif %}"""

category_branch_block = """        <div class="tp-form-grid-2col" style="gap: 16px;">
          <div class="form-group">
            <label class="form-label">Category</label>
            {{ form.category }}
            {% if form.category.errors %}<div class="form-error text-danger small mt-1">{{ form.category.errors.0 }}</div>{% endif %}
          </div>
          {% if form.branch %}
          <div class="form-group">
            <label class="form-label">Branch Center</label>
            {{ form.branch }}
            {% if form.branch.errors %}<div class="form-error text-danger small mt-1">{{ form.branch.errors.0 }}</div>{% endif %}
          </div>
          {% else %}
          <div></div>
          {% endif %}
        </div>"""

for p in templates:
    if not os.path.exists(p):
        print(f"Skipping {p} - does not exist")
        continue

    with open(p, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Add error banner if not already present
    if "Please fix the following validation errors" not in content:
        if "{% if form.non_field_errors %}" in content:
            # Replace non_field_errors block with comprehensive error banner
            old_err = """        {% if form.non_field_errors %}
        <div class="alert alert-danger">{{ form.non_field_errors.0 }}</div>
        {% endif %}"""
            if old_err.replace('\r\n', '\n') in content.replace('\r\n', '\n'):
                content = content.replace('\r\n', '\n').replace(old_err.replace('\r\n', '\n'), error_banner)
            else:
                content = content.replace("{% csrf_token %}", "{% csrf_token %}\n" + error_banner)
        else:
            content = content.replace("{% csrf_token %}", "{% csrf_token %}\n" + error_banner)

    # 2. Add Category & Branch block if form.category is not in template
    if "{{ form.category }}" not in content:
        # Insert before Status field or notes field
        if "{{ form.status }}" in content:
            # Find status form-group
            status_marker = '<div class="form-group">\n          <label class="form-label">Status'
            status_marker_alt = '<div class="form-group">\r\n          <label class="form-label">Status'
            if status_marker in content:
                content = content.replace(status_marker, category_branch_block + "\n\n        " + status_marker)
            elif status_marker_alt in content:
                content = content.replace(status_marker_alt, category_branch_block.replace('\n', '\r\n') + "\r\n\r\n        " + status_marker_alt)
            else:
                # Find generic status
                idx = content.find("{{ form.status }}")
                if idx != -1:
                    fg_idx = content.rfind('<div class="form-group"', 0, idx)
                    if fg_idx != -1:
                        content = content[:fg_idx] + category_branch_block + "\n\n        " + content[fg_idx:]
        elif "{{ form.notes }}" in content:
            idx = content.find("{{ form.notes }}")
            fg_idx = content.rfind('<div class="form-group"', 0, idx)
            if fg_idx != -1:
                content = content[:fg_idx] + category_branch_block + "\n\n        " + content[fg_idx:]

    with open(p, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Updated template: {p}")
