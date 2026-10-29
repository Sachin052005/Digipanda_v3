import os

BASE_DIR = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM"

# 1. Update base.html
base_path = os.path.join(BASE_DIR, "templates", "base.html")
with open(base_path, "r", encoding="utf-8") as f:
    base_html = f.read()

# Replace header block in base.html
header_start = "<!-- Top Application Header -->"
header_end = "</header>"

if header_start in base_html and header_end in base_html:
    part_before = base_html.split(header_start)[0]
    part_after = base_html.split(header_end, 1)[1]

    new_header = """<!-- Top Application Header (Polished Responsive 3-Zone Architecture) -->
      <header class="app-header">
        <div class="header-left">
          <button type="button" class="btn-sidebar-toggle" id="sidebar-toggle" aria-label="Toggle navigation" title="Toggle Navigation">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
          </button>
          <a href="{% url 'login_redirect' %}" class="header-brand-link" style="text-decoration: none;">
            <span class="brand-wordmark-colored theme-light" style="font-size: 1.05rem;"><span class="part-digi">Digi</span><span class="part-p">p</span><span class="part-anda">anda</span><span class="part-crm">CRM</span></span>
          </a>
        </div>

        <div class="header-center">
          <!-- Global Quick Search Trigger (Phase 1) -->
          <button type="button" class="tp-search-trigger-btn" id="tp-search-trigger-btn" title="Global Quick Search (Ctrl + K)">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
            <span class="tp-search-trigger-text">Search leads, actions...</span>
            <span class="tp-kbd-shortcut">Ctrl K</span>
          </button>
        </div>

        <div class="header-right">
          {% if is_admin %}
          <!-- Global Admin Branch Selector (Section 2, 3) -->
          <form method="POST" action="{% url 'set_active_branch' %}" id="admin-branch-select-form" class="tp-header-branch-form">
            {% csrf_token %}
            <input type="hidden" name="next" value="{{ request.get_full_path }}">
            <div class="tp-nav-branch-picker">
              <span class="branch-label" style="font-size: 0.775rem; font-weight: 600; color: var(--text-muted); white-space: nowrap; flex-shrink: 0;">Branch:</span>
              <div style="min-width: 130px; max-width: 190px;">
                <select name="branch_id" class="form-select tp-custom-select" onchange="this.form.submit()" style="padding: 4px 10px; font-size: 0.8125rem; font-weight: 600; color: var(--text-main); background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-sm); cursor: pointer; height: 32px;">
                  <option value="all" {% if not selected_branch %}selected{% endif %}>All Branches</option>
                  {% for b in admin_branches %}
                  <option value="{{ b.id }}" {% if selected_branch and selected_branch.id == b.id %}selected{% endif %}>{{ b.name }}</option>
                  {% endfor %}
                </select>
              </div>
            </div>
          </form>
          {% endif %}

          <!-- 3D Isometric Theme Toggle Coin -->
          <button type="button" class="theme-toggle-btn tp-3d-theme-toggle" id="theme-toggle" aria-label="Switch Theme" title="Toggle Light / Dark theme">
            <div class="tp-3d-coin">
              <div class="tp-coin-face tp-coin-front icon-moon">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
              </div>
              <div class="tp-coin-face tp-coin-back icon-sun">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>
              </div>
            </div>
          </button>

          <!-- Database-Backed Notifications (Section 9) -->
          <div class="notification-dropdown-wrapper" style="position: relative;">
            <button type="button" class="notification-badge" id="notification-bell-btn" title="Notifications" aria-expanded="false" style="background: none; border: none; cursor: pointer; padding: 0; display: flex; align-items: center; position: relative;">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>
              <span class="badge-count" id="notif-badge-count" {% if unread_notifications_count == 0 %}style="display: none;"{% endif %}>{{ unread_notifications_count }}</span>
            </button>

            <!-- Interactive Notification Dropdown Panel -->
            <div id="notification-panel" style="display: none; position: absolute; right: 0; top: calc(100% + 12px); width: 340px; max-height: 440px; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-md); box-shadow: var(--shadow-lg); z-index: 1050; flex-direction: column; overflow: hidden;">
              <div style="padding: 12px 16px; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center;">
                <strong style="font-size: 0.9rem; color: var(--text-main);">Notifications</strong>
                <button type="button" id="mark-all-read-btn" style="background: none; border: none; font-size: 0.75rem; color: var(--primary); cursor: pointer; font-weight: 600; padding: 0;">Mark all read</button>
              </div>
              <div id="notification-items-container" style="overflow-y: auto; max-height: 350px; padding: 0; margin: 0;">
                <div style="padding: 24px; text-align: center; color: var(--text-muted); font-size: 0.85rem;">Loading notifications...</div>
              </div>
            </div>
          </div>

          <!-- User Profile Chip (Navigates to Profile & Security) -->
          <a href="{% url 'user_profile' %}" class="user-profile-pill" style="text-decoration: none; color: inherit; cursor: pointer;" title="View Profile & Change Password">
            <div class="user-avatar">{{ user.username|slice:":1"|upper }}</div>
            <div class="user-info-text">
              <strong>{{ user.get_full_name|default:user.username }}</strong>
              <span class="badge {% if is_superadmin or is_admin or is_branch_admin %}badge-admin{% elif is_manager or is_branch_head or is_counselor %}badge-manager{% elif is_accountant %}badge-success{% elif is_receptionist %}badge-running{% else %}badge-telecaller{% endif %}" style="margin-left: 4px;">
                {{ user_role }}
              </span>
            </div>
          </a>

          <!-- Logout Button with Dedicated Exit Animation -->
          <a href="{% url 'logout' %}" class="btn btn-secondary btn-sm tp-logout-trigger" title="Log out" style="display: inline-flex; align-items: center; gap: 5px; height: 32px; padding: 0 10px;">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
            <span>Logout</span>
          </a>
        </div>
      </header>"""
    
    base_html = part_before + new_header + part_after
    with open(base_path, "w", encoding="utf-8") as f:
        f.write(base_html)
    print("✅ Successfully updated base.html header")
else:
    print("❌ Could not locate header in base.html")
