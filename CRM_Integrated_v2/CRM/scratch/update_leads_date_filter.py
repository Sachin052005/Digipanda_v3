path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\admin\leads_list.html"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

target = """    <div class="filter-col" style="min-width: 180px;">
      <label>Date Range</label>
      <div class="tp-smart-date-container w-100">
        <input type="date" name="date_from" value="{{ date_from }}" style="display: none;">
        <input type="date" name="date_to" value="{{ date_to }}" style="display: none;">
      </div>
    </div>"""

replacement = """    <div class="filter-col" style="flex: 0 0 auto; width: 220px;">
      <label>Date Range</label>
      <div class="tp-smart-date-container">
        <input type="date" name="date_from" value="{{ date_from }}" style="display: none;">
        <input type="date" name="date_to" value="{{ date_to }}" style="display: none;">
      </div>
    </div>"""

if target in text:
    text = text.replace(target, replacement, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("Replaced with LF!")
elif target.replace("\n", "\r\n") in text:
    text = text.replace(target.replace("\n", "\r\n"), replacement.replace("\n", "\r\n"), 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("Replaced with CRLF!")
else:
    print("Not found!")
