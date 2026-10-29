path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\static\js\smart-calendar.js"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

# 1. Replace arrow
old_arrow = "'        <span class=\"tp-smart-date-arrow\">&rarr;</span>',"
new_arrow = "'        <span class=\"tp-smart-date-arrow\"><svg width=\"14\" height=\"14\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2.5\"><line x1=\"5\" y1=\"12\" x2=\"19\" y2=\"12\"></line><polyline points=\"12 5 19 12 12 19\"></polyline></svg></span>',"

if old_arrow in text:
    text = text.replace(old_arrow, new_arrow, 1)
    print("Arrow replaced!")

# 2. Replace prev/next nav buttons with clean SVGs
old_nav = """      var prevBtnHtml = isLeft ? '<button type="button" class="tp-month-nav-btn tp-nav-prev" title="Previous month">&lsaquo;</button>' : '<span class="tp-nav-spacer"></span>';
      var nextBtnHtml = !isLeft ? '<button type="button" class="tp-month-nav-btn tp-nav-next" title="Next month">&rsaquo;</button>' : '<span class="tp-nav-spacer"></span>';"""

new_nav = """      var prevBtnHtml = isLeft ? '<button type="button" class="tp-month-nav-btn tp-nav-prev" title="Previous month"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15 18 9 12 15 6"></polyline></svg></button>' : '<span class="tp-nav-spacer"></span>';
      var nextBtnHtml = !isLeft ? '<button type="button" class="tp-month-nav-btn tp-nav-next" title="Next month"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"></polyline></svg></button>' : '<span class="tp-nav-spacer"></span>';"""

if old_nav in text:
    text = text.replace(old_nav, new_nav, 1)
    print("Nav buttons replaced with clean SVGs!")

with open(path, "w", encoding="utf-8") as f:
    f.write(text)

print("Updated smart-calendar.js successfully!")
