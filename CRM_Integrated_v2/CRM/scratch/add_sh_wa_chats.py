with open(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\base.html", "r", encoding="utf-8") as f:
    content = f.read()

target = """        <a href="{% url 'whatsapp_campaigns_list' %}" class="nav-item {% if request.resolver_match.url_name in 'whatsapp_campaigns_list whatsapp_campaign_create whatsapp_campaign_detail' %}active{% endif %}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"></path><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
          <span class="nav-text">WhatsApp Campaigns</span>
        </a>"""

replacement = """        <a href="{% url 'inbox' %}" class="nav-item {% if request.resolver_match.url_name == 'inbox' %}active{% endif %}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
          <span class="nav-text">WhatsApp Chats</span>
        </a>
        <a href="{% url 'whatsapp_campaigns_list' %}" class="nav-item {% if request.resolver_match.url_name in 'whatsapp_campaigns_list whatsapp_campaign_create whatsapp_campaign_detail' %}active{% endif %}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"></path><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
          <span class="nav-text">WhatsApp Campaigns</span>
        </a>"""

if target in content:
    content = content.replace(target, replacement, 1)
    with open(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\base.html", "w", encoding="utf-8") as f:
        f.write(content)
    print("Added WhatsApp Chats to Sales Head!")
else:
    print("Target not found.")
