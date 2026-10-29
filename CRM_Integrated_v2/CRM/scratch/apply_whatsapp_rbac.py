import re

BASE_HTML = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\base.html"

with open(BASE_HTML, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add WhatsApp items to Sales Head (Manager) Navigation
# Find Sales Head section
manager_needle = """        <a href="{% url 'missed_calls_list' %}" class="nav-item {% if request.resolver_match.url_name == 'missed_calls_list' %}active{% endif %}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.79 19.79 0 0 1 2.12 4.18 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"></path><line x1="23" y1="1" x2="17" y2="7"></line><line x1="17" y1="1" x2="23" y2="7"></line></svg>
          <span class="nav-text">Missed Calls{% missed_callbacks_count as missed_cb %}{% if missed_cb %} <span class="badge" style="background:#dc2626;color:#fff;font-size:0.7rem;padding:1px 6px;border-radius:10px;">{{ missed_cb }}</span>{% endif %}</span>
        </a>"""

manager_whatsapp_block = """        <a href="{% url 'missed_calls_list' %}" class="nav-item {% if request.resolver_match.url_name == 'missed_calls_list' %}active{% endif %}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.79 19.79 0 0 1 2.12 4.18 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"></path><line x1="23" y1="1" x2="17" y2="7"></line><line x1="17" y1="1" x2="23" y2="7"></line></svg>
          <span class="nav-text">Missed Calls{% missed_callbacks_count as missed_cb %}{% if missed_cb %} <span class="badge" style="background:#dc2626;color:#fff;font-size:0.7rem;padding:1px 6px;border-radius:10px;">{{ missed_cb }}</span>{% endif %}</span>
        </a>
        <a href="{% url 'inbox' %}" class="nav-item {% if request.resolver_match.url_name == 'inbox' %}active{% endif %}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
          <span class="nav-text">WhatsApp Chats</span>
        </a>
        <a href="{% url 'whatsapp_campaigns_list' %}" class="nav-item {% if request.resolver_match.url_name in 'whatsapp_campaigns_list whatsapp_campaign_create whatsapp_campaign_detail' %}active{% endif %}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"></path><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
          <span class="nav-text">WhatsApp Campaigns</span>
        </a>
        <a href="{% url 'automation-list' %}" class="nav-item {% if request.resolver_match.url_name in 'automation-list flow-builder flow-builder-detail' %}active{% endif %}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
          <span class="nav-text">WhatsApp Automations</span>
        </a>"""

if manager_needle in content:
    content = content.replace(manager_needle, manager_whatsapp_block, 1)
    print("Added WhatsApp Chats, Campaigns, and Automations to Sales Head (Manager) Navigation!")
else:
    print("WARNING: manager_needle not found in base.html!")

# 2. Remove WhatsApp Chats from Counselor navigation
counselor_wa_link = """        <a href="{% url 'inbox' %}" class="nav-item {% if request.resolver_match.url_name == 'inbox' %}active{% endif %}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
          <span class="nav-text">WhatsApp Chats</span>
        </a>"""

# Replace first occurrence in Counselor
if counselor_wa_link in content:
    content = content.replace(counselor_wa_link, "", 1)
    print("Removed WhatsApp Chats from Counselor Navigation!")
else:
    print("WARNING: counselor_wa_link not found!")

# 3. Remove WhatsApp Chats from Telecaller navigation
# After removing counselor link, if telecaller link is still there:
if counselor_wa_link in content:
    content = content.replace(counselor_wa_link, "", 1)
    print("Removed WhatsApp Chats from Telecaller Navigation!")
else:
    print("WARNING: telecaller_wa_link not found!")

with open(BASE_HTML, "w", encoding="utf-8") as f:
    f.write(content)
print("Saved base.html successfully!")
