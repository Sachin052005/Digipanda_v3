import os

file_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\admin\branch_admin_create.html"
with open(file_path, "r", encoding="utf-8") as f:
    c = f.read()

target = """      <div class="form-group" style="margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
          <label class="form-label" style="display: block; font-weight: 600; font-size: 0.85rem; margin-bottom: 0;">Username / Login ID</label>
          <span class="badge" style="background: #e0f2fe; color: #0369a1; font-size: 0.72rem; font-weight: 600; padding: 2px 8px; border-radius: 9999px;">Auto-generated</span>
        </div>
        {{ form.username }}
        {% if form.username.errors %}<div class="form-error" style="color: #ef4444; font-size: 0.78rem; margin-top: 4px;">{{ form.username.errors.0 }}</div>{% endif %}
        <div class="form-text" id="username-preview-hint" style="color: var(--text-muted, #64748b); font-size: 0.775rem; margin-top: 4px;">Generated automatically from First &amp; Last Name</div>
      </div>"""

if target in c:
    c = c.replace(target, "{{ form.username.as_hidden }}")
    with open(file_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(c)
    print("Successfully patched branch_admin_create.html")
else:
    print("Target not found in branch_admin_create.html")
