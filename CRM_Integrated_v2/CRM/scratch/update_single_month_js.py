import re

js_path = r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\static\js\smart-calendar.js'

with open(js_path, 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Update HTML snippet in popover
old_html_pattern = re.compile(
    r"""\s*'<div class="tp-smart-date-dual-view">',\s*"""
    r"""'      <!-- Month 1 -->',\s*"""
    r"""'      <div class="tp-smart-month" id="month1"></div>',\s*"""
    r"""'      <!-- Month 2 -->',\s*"""
    r"""'      <div class="tp-smart-month" id="month2"></div>',\s*"""
    r"""'    </div>',""",
    re.MULTILINE
)

new_html_snippet = (
    "      '<div class=\"tp-smart-date-single-view\">',\n"
    "      '  <div class=\"tp-smart-month\" id=\"singleMonth\"></div>',\n"
    "      '</div>',"
)

if old_html_pattern.search(code):
    code = old_html_pattern.sub(new_html_snippet, code)
    print("Replaced popover HTML snippet with single view!")
else:
    print("WARNING: popover HTML snippet pattern not found directly, checking manual replace...")
    old_str = ("      '    <div class=\"tp-smart-date-dual-view\">',\n"
               "      '      <!-- Month 1 -->',\n"
               "      '      <div class=\"tp-smart-month\" id=\"month1\"></div>',\n"
               "      '      <!-- Month 2 -->',\n"
               "      '      <div class=\"tp-smart-month\" id=\"month2\"></div>',\n"
               "      '    </div>',")
    if old_str in code:
        code = code.replace(old_str, new_html_snippet)
        print("Replaced via exact string!")

# 2. Update element references
old_refs = ("    var month1El = popover.querySelector('#month1');\n"
            "    var month2El = popover.querySelector('#month2');")
new_refs = "    var monthEl = popover.querySelector('#singleMonth');"

if old_refs in code:
    code = code.replace(old_refs, new_refs)
    print("Replaced month element references!")

# 3. Update renderMonth signature and navigation header
old_render_month = """    // 8. Render a single calendar month
    function renderMonth(containerEl, year, month, isLeft) {
      containerEl.innerHTML = '';

      var monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
      var dayNames = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

      // Month Navigation Header
      var header = document.createElement('div');
      header.className = 'tp-smart-month-header';

      var prevBtnHtml = isLeft ? '<button type="button" class="tp-month-nav-btn tp-nav-prev" title="Previous month"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15 18 9 12 15 6"></polyline></svg></button>' : '<span class="tp-nav-spacer"></span>';
      var nextBtnHtml = !isLeft ? '<button type="button" class="tp-month-nav-btn tp-nav-next" title="Next month"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"></polyline></svg></button>' : '<span class="tp-nav-spacer"></span>';

      header.innerHTML = [
        prevBtnHtml,
        '<span class="tp-month-title">' + monthNames[month] + ' ' + year + '</span>',
        nextBtnHtml
      ].join('');

      containerEl.appendChild(header);

      // Month nav button clicks
      if (isLeft) {
        var prevBtn = header.querySelector('.tp-nav-prev');
        if (prevBtn) {
          prevBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            currentViewDate.setMonth(currentViewDate.getMonth() - 1);
            renderDualMonths();
          });
        }
      } else {
        var nextBtn = header.querySelector('.tp-nav-next');
        if (nextBtn) {
          nextBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            currentViewDate.setMonth(currentViewDate.getMonth() + 1);
            renderDualMonths();
          });
        }
      }"""

new_render_month = """    // 8. Render a single calendar month with bidirectional navigation
    function renderMonth(containerEl, year, month) {
      containerEl.innerHTML = '';

      var monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
      var dayNames = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

      // Month Navigation Header (Both Prev & Next buttons for single month view)
      var header = document.createElement('div');
      header.className = 'tp-smart-month-header';

      var prevBtnHtml = '<button type="button" class="tp-month-nav-btn tp-nav-prev" title="Previous month"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15 18 9 12 15 6"></polyline></svg></button>';
      var nextBtnHtml = '<button type="button" class="tp-month-nav-btn tp-nav-next" title="Next month"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"></polyline></svg></button>';

      header.innerHTML = [
        prevBtnHtml,
        '<span class="tp-month-title">' + monthNames[month] + ' ' + year + '</span>',
        nextBtnHtml
      ].join('');

      containerEl.appendChild(header);

      // Month nav button clicks
      var prevBtn = header.querySelector('.tp-nav-prev');
      if (prevBtn) {
        prevBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          currentViewDate.setMonth(currentViewDate.getMonth() - 1);
          renderCalendarMonth();
        });
      }

      var nextBtn = header.querySelector('.tp-nav-next');
      if (nextBtn) {
        nextBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          currentViewDate.setMonth(currentViewDate.getMonth() + 1);
          renderCalendarMonth();
        });
      }"""

if old_render_month.replace('\r\n', '\n') in code.replace('\r\n', '\n'):
    code = code.replace('\r\n', '\n').replace(old_render_month.replace('\r\n', '\n'), new_render_month.replace('\r\n', '\n'))
    print("Replaced renderMonth navigation!")
else:
    print("WARNING: renderMonth pattern mismatch!")

# 4. Update renderDualMonths definition
old_dual = """    // 9. Render both months side-by-side
    function renderDualMonths() {
      var y1 = currentViewDate.getFullYear();
      var m1 = currentViewDate.getMonth();

      var nextMonthDate = new Date(y1, m1 + 1, 1);
      var y2 = nextMonthDate.getFullYear();
      var m2 = nextMonthDate.getMonth();

      renderMonth(month1El, y1, m1, true);
      renderMonth(month2El, y2, m2, false);
    }"""

new_single = """    // 9. Render single calendar month
    function renderCalendarMonth() {
      var y = currentViewDate.getFullYear();
      var m = currentViewDate.getMonth();
      renderMonth(monthEl, y, m);
    }"""

if old_dual.replace('\r\n', '\n') in code.replace('\r\n', '\n'):
    code = code.replace('\r\n', '\n').replace(old_dual.replace('\r\n', '\n'), new_single.replace('\r\n', '\n'))
    print("Replaced renderDualMonths with renderCalendarMonth definition!")
else:
    print("WARNING: renderDualMonths pattern mismatch!")

# 5. Replace all remaining renderDualMonths() calls with renderCalendarMonth()
code = code.replace('renderDualMonths()', 'renderCalendarMonth()')

with open(js_path, 'w', encoding='utf-8') as f:
    f.write(code)

print("Finished updating smart-calendar.js successfully!")
