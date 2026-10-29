path = r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\leads\lead_detail_view.html'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Pre-call banner
target_banner = """    <!-- TAB 1: OVERVIEW & FIELDS -->
    <div id="tab-details" class="ldm-tab-pane active" role="tabpanel">
      <div class="lead-fields-grid">"""

repl_banner = """    <!-- TAB 1: OVERVIEW & FIELDS -->
    <div id="tab-details" class="ldm-tab-pane active" role="tabpanel">
      {% if smart_pitch %}
      <div class="ldm-precall-pitch-card" style="background: linear-gradient(135deg, rgba(37,99,235,0.06) 0%, rgba(99,102,241,0.04) 100%); border: 1px solid rgba(59,130,246,0.25); border-radius: 10px; padding: 12px 18px; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between; gap: 14px;">
        <div style="display: flex; align-items: center; gap: 12px;">
          <div style="width: 34px; height: 34px; border-radius: 8px; background: #2563eb; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 1rem; flex-shrink: 0; box-shadow: 0 2px 6px rgba(37,99,235,0.25);">
            ⚡
          </div>
          <div>
            <div style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #2563eb; margin-bottom: 2px;">
              Smart Pre-Call Pitch · Auto-Detected Lead Context
            </div>
            <div style="font-size: 0.88rem; color: #1e293b; font-weight: 500;">
              {{ smart_pitch|safe }}
            </div>
          </div>
        </div>
        <div style="display: flex; gap: 6px; flex-shrink: 0;">
          <span style="font-size: 0.72rem; font-weight: 600; padding: 3px 8px; border-radius: 6px; background: rgba(37,99,235,0.12); color: #1d4ed8;">⚡ Intake Auto-Filled</span>
        </div>
      </div>
      {% endif %}
      <div class="lead-fields-grid">"""

badge_snippet = """            <span>{{ f.label }}</span>
            {% if f.origin and f.origin != 'Manual' %}
              <span class="badge-autofill badge-autofill-{{ f.origin|slugify }}" title="Auto-filled from {{ f.origin }} intake answers" style="font-size: 0.65rem; font-weight: 700; padding: 1px 6px; border-radius: 4px; background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; margin-left: 5px;">
                {% if f.origin == 'Facebook' %}⚡ FB{% elif f.origin == 'WhatsApp' %}🤖 WA{% elif f.origin == 'Google Sheets' %}📄 Sheet{% else %}⚡ {{ f.origin }}{% endif %}
              </span>
            {% endif %}"""

text_norm = text.replace('\r\n', '\n')
target_banner_norm = target_banner.replace('\r\n', '\n')

assert target_banner_norm in text_norm, "Target banner not found"
text_norm = text_norm.replace(target_banner_norm, repl_banner.replace('\r\n', '\n'), 1)

# In the 4 loops, replace <span>{{ f.label }}</span>
# Loop 1: col1 primary
# Loop 2: col1 secondary
# Loop 3: col2 primary
# Loop 4: col2 secondary
# We can replace '<span>{{ f.label }}</span>' within the lead-field-label blocks
text_norm = text_norm.replace("<span>{{ f.label }}</span>", badge_snippet.replace('\r\n', '\n'))

with open(path, 'w', encoding='utf-8', newline='\r\n') as f:
    f.write(text_norm)

print("Successfully updated lead_detail_view.html")
