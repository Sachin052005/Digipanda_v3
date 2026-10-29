with open(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\base.html", "rb") as f:
    raw = f.read()

# Normalize CRLF to LF or search binary
needle = b"""        <div class="nav-section-title">Communication</div>\r\n        <a href="{% url 'inbox' %}" class="nav-item {% if request.resolver_match.url_name == 'inbox' %}active{% endif %}">\r\n          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>\r\n          <span class="nav-text">WhatsApp Chats</span>\r\n        </a>\r\n"""
replacement = b"""        <div class="nav-section-title">Communication</div>\r\n"""

if needle in raw:
    raw = raw.replace(needle, replacement)
    print("Replaced CRLF version!")
else:
    needle_lf = needle.replace(b"\r\n", b"\n")
    replacement_lf = replacement.replace(b"\r\n", b"\n")
    if needle_lf in raw:
        raw = raw.replace(needle_lf, replacement_lf)
        print("Replaced LF version!")
    else:
        print("Could not match needle directly.")

with open(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\base.html", "wb") as f:
    f.write(raw)
