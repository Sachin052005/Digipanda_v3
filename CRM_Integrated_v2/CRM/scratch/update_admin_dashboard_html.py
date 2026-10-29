import os

BASE_DIR = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM"
dash_path = os.path.join(BASE_DIR, "templates", "admin_dashboard", "dashboard.html")

with open(dash_path, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Update page header
old_page_header = """<div class="page-header" style="margin-bottom: 24px; display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;">
  <div class="page-title-group">
    <h1 style="font-size: 1.6rem; font-weight: 800; letter-spacing: -0.02em; color: var(--tp-text-primary); margin: 0 0 6px 0;">Organization Overview</h1>
    <p style="font-size: 0.9rem; color: var(--tp-text-muted); margin: 0;">Real-time analytics and management control center for DIGIPANDA CRM</p>
  </div>
  <div class="page-actions" style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
    <button type="button" class="btn btn-warning btn-sm tp-btn-warning tp-btn-sm" id="btn-trigger-sla-escalation" style="font-weight: 700; display: inline-flex; align-items: center; gap: 5px;">
      <span>⚡ Enforce SLAs Now</span>
    </button>
    <a href="{% url 'admin_enrolled_students' %}" class="btn btn-primary btn-sm tp-btn-primary tp-btn-sm" style="display: inline-flex; align-items: center; gap: 5px;">
      <span>🎓 Enrolled Students</span>
    </a>
    <a href="{% url 'admin_lead_create' %}" class="btn btn-secondary btn-sm tp-btn-secondary tp-btn-sm">
      + Add Lead
    </a>
  </div>
</div>"""

new_page_header = """<div class="page-header" style="margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px;">
  <div class="page-title-group">
    <h1 style="font-size: 1.45rem; font-weight: 800; letter-spacing: -0.02em; color: var(--tp-text-primary); margin: 0 0 3px 0;">Organization Overview</h1>
    <p style="font-size: 0.835rem; color: var(--tp-text-muted); margin: 0;">Real-time analytics and management control center for DigipandaCRM</p>
  </div>
  <div class="page-actions" style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
    <button type="button" class="btn btn-warning btn-sm tp-btn-warning tp-btn-sm" id="btn-trigger-sla-escalation" style="font-weight: 700; display: inline-flex; align-items: center; gap: 5px; height: 32px; padding: 0 12px;">
      <span>⚡ Enforce SLAs Now</span>
    </button>
    <a href="{% url 'admin_enrolled_students' %}" class="btn btn-primary btn-sm tp-btn-primary tp-btn-sm" style="display: inline-flex; align-items: center; gap: 5px; height: 32px; padding: 0 12px;">
      <span>🎓 Enrolled Students</span>
    </a>
    <a href="{% url 'admin_lead_create' %}" class="btn btn-secondary btn-sm tp-btn-secondary tp-btn-sm" style="display: inline-flex; align-items: center; gap: 4px; height: 32px; padding: 0 12px;">
      <span>+ Add Lead</span>
    </a>
  </div>
</div>"""

if old_page_header in html:
    html = html.replace(old_page_header, new_page_header)
else:
    print("Warning: old_page_header not found directly")

# 2. Update filter card to tp-filter-bar
old_filter_card = """<!-- Admin Dashboard Filters (Section 15) -->
<div class="filter-card tp-card" style="padding: 16px 20px; margin-bottom: 24px;">
  <!-- Preset Period Buttons -->
  <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 14px; padding-bottom: 12px; border-bottom: 1px solid var(--tp-surface-border, #e5e7eb);">
    <span style="font-size: 0.8rem; font-weight: 700; color: var(--tp-text-muted); text-transform: uppercase; margin-right: 4px;">Quick Period:</span>
    <a href="?period=all" class="btn {% if period == 'all' or not period and not from_date and not to_date %}btn-primary tp-btn-primary{% else %}btn-secondary tp-btn-secondary{% endif %}" style="font-size: 0.8rem; padding: 4px 12px;">All Time</a>
    <a href="?period=today" class="btn {% if period == 'today' %}btn-primary tp-btn-primary{% else %}btn-secondary tp-btn-secondary{% endif %}" style="font-size: 0.8rem; padding: 4px 12px;">Today</a>
    <a href="?period=week" class="btn {% if period == 'week' %}btn-primary tp-btn-primary{% else %}btn-secondary tp-btn-secondary{% endif %}" style="font-size: 0.8rem; padding: 4px 12px;">This Week</a>
    <a href="?period=month" class="btn {% if period == 'month' %}btn-primary tp-btn-primary{% else %}btn-secondary tp-btn-secondary{% endif %}" style="font-size: 0.8rem; padding: 4px 12px;">This Month</a>
  </div>

  <form method="GET" class="filter-form" style="display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-end;">
    <div class="filter-col" style="flex: 1; min-width: 130px;">
      <label class="tp-label">From Date</label>
      <input type="date" name="from_date" class="form-control tp-input" value="{{ from_date }}">
    </div>
    <div class="filter-col" style="flex: 1; min-width: 130px;">
      <label class="tp-label">To Date</label>
      <input type="date" name="to_date" class="form-control tp-input" value="{{ to_date }}">
    </div>
    <div class="filter-col" style="flex: 1; min-width: 140px;">
      <label class="tp-label">Sales Head</label>
      <select name="manager" class="form-select tp-select">
        <option value="">All Sales Heads</option>
        {% for m in managers %}
        <option value="{{ m.id }}" {% if manager_filter == m.id|stringformat:"i" %}selected{% endif %}>{{ m.get_full_name|default:m.username }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="filter-col" style="flex: 1; min-width: 140px;">
      <label class="tp-label">Telecaller</label>
      <select name="telecaller" class="form-select tp-select">
        <option value="">All Telecallers</option>
        {% for t in telecallers %}
        <option value="{{ t.id }}" {% if telecaller_filter == t.id|stringformat:"i" %}selected{% endif %}>{{ t.get_full_name|default:t.username }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="filter-col" style="flex: 1; min-width: 130px;">
      <label class="tp-label">Branch</label>
      <select name="branch" class="form-select tp-select">
        <option value="">All Branches</option>
        {% for b in branches %}
        <option value="{{ b.id }}" {% if branch_filter == b.id|stringformat:"i" %}selected{% endif %}>{{ b.name }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="filter-col" style="flex: 1; min-width: 130px;">
      <label class="tp-label">Channel</label>
      <select name="channel" class="form-select tp-select">
        <option value="">All Channels</option>
        {% for c in channels %}
        <option value="{{ c.id }}" {% if channel_filter == c.id|stringformat:"i" %}selected{% endif %}>{{ c.name }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="filter-col" style="flex: 1; min-width: 130px;">
      <label class="tp-label">Status</label>
      <select name="status" class="form-select tp-select">
        <option value="">All Statuses</option>
        {% for code, label in statuses %}
        <option value="{{ code }}" {% if status_filter == code %}selected{% endif %}>{{ label }}</option>
        {% endfor %}
      </select>
    </div>
    <div style="display: flex; gap: 8px;">
      <a href="{% url 'admin_dashboard' %}" class="btn btn-secondary tp-btn-secondary">Reset</a>
    </div>
  </form>
</div>"""

new_filter_card = """<!-- Admin Dashboard Command Filter Bar (Compact & Sleek) -->
<div class="tp-filter-bar tp-card">
  <!-- Top Quick Period Row -->
  <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--tp-surface-border, rgba(226, 232, 240, 0.8));">
    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
      <span style="font-size: 0.75rem; font-weight: 700; color: var(--tp-text-muted); text-transform: uppercase; letter-spacing: 0.04em;">Quick Period:</span>
      <div style="display: inline-flex; gap: 6px; flex-wrap: wrap;">
        <a href="?period=all" class="btn btn-sm {% if period == 'all' or not period and not from_date and not to_date %}btn-primary tp-btn-primary{% else %}btn-secondary tp-btn-secondary{% endif %}" style="font-size: 0.775rem; padding: 3px 10px; border-radius: 6px;">All Time</a>
        <a href="?period=today" class="btn btn-sm {% if period == 'today' %}btn-primary tp-btn-primary{% else %}btn-secondary tp-btn-secondary{% endif %}" style="font-size: 0.775rem; padding: 3px 10px; border-radius: 6px;">Today</a>
        <a href="?period=week" class="btn btn-sm {% if period == 'week' %}btn-primary tp-btn-primary{% else %}btn-secondary tp-btn-secondary{% endif %}" style="font-size: 0.775rem; padding: 3px 10px; border-radius: 6px;">This Week</a>
        <a href="?period=month" class="btn btn-sm {% if period == 'month' %}btn-primary tp-btn-primary{% else %}btn-secondary tp-btn-secondary{% endif %}" style="font-size: 0.775rem; padding: 3px 10px; border-radius: 6px;">This Month</a>
      </div>
    </div>
    {% if from_date or to_date or manager_filter or telecaller_filter or branch_filter or channel_filter or status_filter or period and period != 'all' %}
    <a href="{% url 'admin_dashboard' %}" style="font-size: 0.775rem; font-weight: 600; color: #ef4444; text-decoration: none; display: inline-flex; align-items: center; gap: 4px;">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
      Reset Filters
    </a>
    {% endif %}
  </div>

  <form method="GET" class="tp-compact-filter-grid">
    <div class="tp-filter-field">
      <label class="tp-field-label">From Date</label>
      <input type="date" name="from_date" class="form-control tp-input-compact" value="{{ from_date }}">
    </div>
    <div class="tp-filter-field">
      <label class="tp-field-label">To Date</label>
      <input type="date" name="to_date" class="form-control tp-input-compact" value="{{ to_date }}">
    </div>
    <div class="tp-filter-field">
      <label class="tp-field-label">Sales Head</label>
      <select name="manager" class="form-select tp-select-compact" onchange="this.form.submit()">
        <option value="">All Sales Heads</option>
        {% for m in managers %}
        <option value="{{ m.id }}" {% if manager_filter == m.id|stringformat:"i" %}selected{% endif %}>{{ m.get_full_name|default:m.username }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="tp-filter-field">
      <label class="tp-field-label">Telecaller</label>
      <select name="telecaller" class="form-select tp-select-compact" onchange="this.form.submit()">
        <option value="">All Telecallers</option>
        {% for t in telecallers %}
        <option value="{{ t.id }}" {% if telecaller_filter == t.id|stringformat:"i" %}selected{% endif %}>{{ t.get_full_name|default:t.username }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="tp-filter-field">
      <label class="tp-field-label">Branch</label>
      <select name="branch" class="form-select tp-select-compact" onchange="this.form.submit()">
        <option value="">All Branches</option>
        {% for b in branches %}
        <option value="{{ b.id }}" {% if branch_filter == b.id|stringformat:"i" %}selected{% endif %}>{{ b.name }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="tp-filter-field">
      <label class="tp-field-label">Channel</label>
      <select name="channel" class="form-select tp-select-compact" onchange="this.form.submit()">
        <option value="">All Channels</option>
        {% for c in channels %}
        <option value="{{ c.id }}" {% if channel_filter == c.id|stringformat:"i" %}selected{% endif %}>{{ c.name }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="tp-filter-field">
      <label class="tp-field-label">Status</label>
      <select name="status" class="form-select tp-select-compact" onchange="this.form.submit()">
        <option value="">All Statuses</option>
        {% for code, label in statuses %}
        <option value="{{ code }}" {% if status_filter == code %}selected{% endif %}>{{ label }}</option>
        {% endfor %}
      </select>
    </div>
    <div style="display: flex; gap: 6px; align-items: flex-end;">
      <button type="submit" class="btn btn-primary tp-btn-primary btn-sm" style="font-size: 0.775rem; height: 33px; padding: 0 12px; display: inline-flex; align-items: center; gap: 4px;">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon></svg>
        Filter
      </button>
      <a href="{% url 'admin_dashboard' %}" class="btn btn-secondary tp-btn-secondary btn-sm" style="font-size: 0.775rem; height: 33px; padding: 0 10px; display: inline-flex; align-items: center;" title="Reset Filters">
        Reset
      </a>
    </div>
  </form>
</div>"""

if old_filter_card in html:
    html = html.replace(old_filter_card, new_filter_card)
else:
    print("Warning: old_filter_card not found directly")

# 3. Update Section 1 KPI grid container
old_sec1_grid = """  <div class="kpi-grid tp-stagger-container" style="grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px;">"""
new_sec1_grid = """  <div class="kpi-grid tp-kpi-grid-7 tp-stagger-container" style="gap: 12px;">"""
html = html.replace(old_sec1_grid, new_sec1_grid)

# 4. Update Section 2 KPI grid container
old_sec2_grid = """  <div class="kpi-grid" style="grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 16px;">"""
new_sec2_grid = """  <div class="kpi-grid tp-kpi-grid-5" style="gap: 12px;">"""
html = html.replace(old_sec2_grid, new_sec2_grid)

# 5. Update Section 3 Chart Cards
old_charts = """<!-- SECTION 2: Visual Pipeline & Telecaller Performance Charts -->
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 20px; margin-bottom: 24px;">
  <!-- Pipeline Status Distribution Chart -->
  <div class="tp-chart-card">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
      <div>
        <h4 style="font-size: 1.05rem; font-weight: 700; color: var(--tp-text-primary); margin: 0 0 4px 0;">Lead Pipeline Distribution</h4>
        <p style="font-size: 0.8rem; color: var(--tp-text-muted); margin: 0;">Breakdown by operational lead stages</p>
      </div>
      <a href="{% url 'leads_kanban' %}" class="btn btn-secondary btn-sm tp-btn-secondary tp-btn-sm" style="font-size: 0.8rem;">View Kanban</a>
    </div>
    <div style="height: 260px; position: relative;">
      <canvas id="adminStatusChart"></canvas>
    </div>
  </div>

  <!-- Telecaller Activity & RNR Chart -->
  <div class="tp-chart-card">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
      <div>
        <h4 style="font-size: 1.05rem; font-weight: 700; color: var(--tp-text-primary); margin: 0 0 4px 0;">Telecaller Call Outcomes</h4>
        <p style="font-size: 0.8rem; color: var(--tp-text-muted); margin: 0;">Connected vs. Ringing No Response (RNR)</p>
      </div>
      <a href="{% url 'telecaller_rnr_report' %}" class="btn btn-secondary btn-sm tp-btn-secondary tp-btn-sm" style="font-size: 0.8rem;">Full Report</a>
    </div>
    <div style="height: 260px; position: relative;">
      <canvas id="adminTelecallerChart"></canvas>
    </div>
  </div>
</div>"""

new_charts = """<!-- SECTION 2: Visual Pipeline & Telecaller Performance Charts -->
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 16px; margin-bottom: 20px;">
  <!-- Pipeline Status Distribution Chart -->
  <div class="tp-chart-card tp-card" style="padding: 16px 20px; border-radius: var(--tp-radius-lg, 12px); min-width: 0;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
      <div>
        <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--tp-text-primary); margin: 0 0 2px 0;">Lead Pipeline Distribution</h4>
        <p style="font-size: 0.775rem; color: var(--tp-text-muted); margin: 0;">Breakdown by operational lead stages</p>
      </div>
      <a href="{% url 'leads_kanban' %}" class="btn btn-secondary btn-sm tp-btn-secondary tp-btn-sm" style="font-size: 0.775rem; padding: 3px 10px;">View Kanban</a>
    </div>
    <div style="height: 240px; position: relative; width: 100%; min-width: 0;">
      <canvas id="adminStatusChart"></canvas>
    </div>
  </div>

  <!-- Telecaller Activity & RNR Chart -->
  <div class="tp-chart-card tp-card" style="padding: 16px 20px; border-radius: var(--tp-radius-lg, 12px); min-width: 0;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
      <div>
        <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--tp-text-primary); margin: 0 0 2px 0;">Telecaller Call Outcomes</h4>
        <p style="font-size: 0.775rem; color: var(--tp-text-muted); margin: 0;">Connected vs. Ringing No Response (RNR)</p>
      </div>
      <a href="{% url 'telecaller_rnr_report' %}" class="btn btn-secondary btn-sm tp-btn-secondary tp-btn-sm" style="font-size: 0.775rem; padding: 3px 10px;">Full Report</a>
    </div>
    <div style="height: 240px; position: relative; width: 100%; min-width: 0;">
      <canvas id="adminTelecallerChart"></canvas>
    </div>
  </div>
</div>"""

if old_charts in html:
    html = html.replace(old_charts, new_charts)
else:
    print("Warning: old_charts not found directly")

# 6. Performance Tables container
html = html.replace(
    """<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 24px; margin-bottom: 24px;">""",
    """<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(440px, 1fr)); gap: 16px; margin-bottom: 20px;">"""
)

# 7. Recent Leads & Recent Calls grid
html = html.replace(
    """<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px;">""",
    """<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(440px, 1fr)); gap: 16px; margin-bottom: 20px;">"""
)

# 8. Margins on sections
html = html.replace("""<div style="margin-bottom: 24px;">\n  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">\n    <h3 style="font-size: 1.1rem;""",
                    """<div style="margin-bottom: 20px;">\n  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">\n    <h3 style="font-size: 1.05rem;""")

with open(dash_path, "w", encoding="utf-8") as f:
    f.write(html)

print("SUCCESS: Updated admin dashboard.html")
