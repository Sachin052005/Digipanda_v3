import os
import re

BASE_DIR = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM"

def patch_base_html():
    path = os.path.join(BASE_DIR, "templates", "base.html")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 1. Add color-scheme meta tag if not present
    if '<meta name="color-scheme"' not in content:
        content = content.replace(
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n  <meta name="color-scheme" content="light dark">'
        )
        print("Patched base.html: Added color-scheme meta tag")
    
    # 2. Add class="form-select" to header branch selector
    old_branch_select = '<select name="branch_id" onchange="this.form.submit()"'
    new_branch_select = '<select name="branch_id" class="form-select" onchange="this.form.submit()"'
    if old_branch_select in content:
        content = content.replace(old_branch_select, new_branch_select)
        print("Patched base.html: Added class='form-select' to header branch select")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def patch_theme_manager():
    path = os.path.join(BASE_DIR, "static", "js", "theme-manager.js")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if "document.documentElement.style.colorScheme" not in content:
        content = content.replace(
            "document.documentElement.setAttribute('data-theme', savedTheme);",
            "document.documentElement.setAttribute('data-theme', savedTheme);\n    document.documentElement.style.colorScheme = savedTheme;"
        )
        print("Patched theme-manager.js: Added colorScheme attribute to documentElement")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def patch_crm_js():
    path = os.path.join(BASE_DIR, "static", "js", "crm.js")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # In applyTheme:
    if "document.documentElement.style.colorScheme = theme;" not in content:
        content = content.replace(
            "document.documentElement.setAttribute('data-theme', theme);",
            "document.documentElement.setAttribute('data-theme', theme);\n    document.documentElement.style.colorScheme = theme;"
        )
        print("Patched crm.js: Added colorScheme in applyTheme()")

    # In themeToggleBtn click listener:
    old_toggle = """    themeToggleBtn.addEventListener('click', function () {
      const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
      applyTheme(newTheme);
    });"""

    new_toggle = """    themeToggleBtn.addEventListener('click', function () {
      document.documentElement.classList.add('theme-transitioning');
      const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
      applyTheme(newTheme);
      setTimeout(function () {
        document.documentElement.classList.remove('theme-transitioning');
      }, 350);
    });"""

    if old_toggle in content:
        content = content.replace(old_toggle, new_toggle)
        print("Patched crm.js: Scoped theme transitions to active toggle event")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def patch_crm_css():
    path = os.path.join(BASE_DIR, "static", "css", "crm.css")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Add color-scheme to :root
    if "color-scheme: light;" not in content:
        content = content.replace(
            ":root {\n",
            ":root, html {\n  color-scheme: light;\n"
        )
        content = content.replace(
            '[data-theme="dark"] {\n',
            '[data-theme="dark"], html[data-theme="dark"] {\n  color-scheme: dark;\n'
        )
        print("Patched crm.css: Added color-scheme to :root and [data-theme='dark']")

    # 2. Fix .content-wrapper animation flicker
    content = re.sub(
        r'\.content-wrapper\s*\{([^}]+)\}',
        lambda m: re.sub(r'animation:[^;]+;', 'animation: none;', m.group(0)),
        content
    )
    print("Patched crm.css: Disabled .content-wrapper entrance animation to eliminate page flicker")

    # 3. Remove background-color transition from .form-control, .form-select
    content = content.replace(
        "transition: border-color 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s cubic-bezier(0.16, 1, 0.3, 1), background-color 0.2s ease;",
        "transition: border-color 0.15s ease, box-shadow 0.15s ease;"
    )

    # 4. Append Universal Dropdown & Select Anti-Black-Flash rules
    dropdown_rules = """
/* ==========================================================================
   ENTERPRISE INSTANT DROPDOWN & SELECT OPTIMIZATION (ZERO BLACK FLASH / ZERO LAG)
   Directly resolves Windows Chromium native DirectComposition popup latency.
   ========================================================================== */
select,
.form-select,
.tp-select,
select.form-control,
.tp-pill-select-overlay {
  color-scheme: light !important;
  background-color: #ffffff !important;
  color: #0f172a !important;
  appearance: none !important;
  -webkit-appearance: none !important;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%23475569' stroke-width='2.2'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' d='M19 9l-7 7-7-7'%3E%3C/path%3E%3C/svg%3E") !important;
  background-repeat: no-repeat !important;
  background-position: right 10px center !important;
  background-size: 14px !important;
  padding-right: 30px !important;
  transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
}

/* Ensure active/click/focus NEVER flashes black or shifts to dark background */
select:focus, select:active,
.form-select:focus, .form-select:active,
.tp-select:focus, .tp-select:active,
select.form-control:focus, select.form-control:active,
.tp-pill-select-overlay:focus, .tp-pill-select-overlay:active {
  color-scheme: light !important;
  background-color: #ffffff !important;
  color: #0f172a !important;
  outline: none !important;
  border-color: #4f46e5 !important;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.22) !important;
}

/* Literal hex styling for options prevents DirectComposition variable stall */
select option,
.form-select option,
.tp-select option,
select.form-control option,
optgroup {
  color-scheme: light !important;
  background-color: #ffffff !important;
  color: #0f172a !important;
  font-size: 0.875rem;
  padding: 6px 12px;
}

/* Dark Mode Overrides */
[data-theme="dark"] select,
[data-theme="dark"] .form-select,
[data-theme="dark"] .tp-select,
[data-theme="dark"] select.form-control,
[data-theme="dark"] .tp-pill-select-overlay {
  color-scheme: dark !important;
  background-color: #131b2e !important;
  color: #f8fafc !important;
  border-color: #1e2c47 !important;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%2394a3b8' stroke-width='2.2'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' d='M19 9l-7 7-7-7'%3E%3C/path%3E%3C/svg%3E") !important;
}

[data-theme="dark"] select:focus, [data-theme="dark"] select:active,
[data-theme="dark"] .form-select:focus, [data-theme="dark"] .form-select:active,
[data-theme="dark"] .tp-select:focus, [data-theme="dark"] .tp-select:active,
[data-theme="dark"] select.form-control:focus, [data-theme="dark"] select.form-control:active,
[data-theme="dark"] .tp-pill-select-overlay:focus, [data-theme="dark"] .tp-pill-select-overlay:active {
  color-scheme: dark !important;
  background-color: #131b2e !important;
  color: #f8fafc !important;
  border-color: #6366f1 !important;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.3) !important;
}

[data-theme="dark"] select option,
[data-theme="dark"] .form-select option,
[data-theme="dark"] .tp-select option,
[data-theme="dark"] select.form-control option,
[data-theme="dark"] optgroup {
  color-scheme: dark !important;
  background-color: #131b2e !important;
  color: #f8fafc !important;
}
"""
    if "ENTERPRISE INSTANT DROPDOWN & SELECT OPTIMIZATION" not in content:
        content += "\n" + dropdown_rules
        print("Patched crm.css: Added Enterprise Instant Dropdown rules")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def patch_design_system_css():
    path = os.path.join(BASE_DIR, "static", "css", "design-system.css")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Add color-scheme to :root
    if "color-scheme: light;" not in content:
        content = content.replace(
            ":root {\n",
            ":root, html {\n  color-scheme: light;\n"
        )
        content = content.replace(
            '[data-theme="dark"] {\n',
            '[data-theme="dark"], html[data-theme="dark"] {\n  color-scheme: dark;\n'
        )
        print("Patched design-system.css: Added color-scheme to :root and [data-theme='dark']")

    # 2. Fix transition: all on form inputs
    content = content.replace(
        "transition: all var(--tp-transition-fast);",
        "transition: border-color 0.15s ease, box-shadow 0.15s ease;"
    )

    # 3. Scope theme transitions to html.theme-transitioning
    old_transitions = """/* Universal Smooth Transitions for Theme Shifts */
body, .app-sidebar, .top-header, .card, .crm-card, .table-card, .filter-card,
.modal-content, .drawer-body, .btn-primary, .btn-secondary {
  transition: background-color 0.24s cubic-bezier(0.16, 1, 0.3, 1),
              border-color 0.24s ease,
              color 0.2s ease,
              box-shadow 0.24s ease !important;
}"""

    new_transitions = """/* Universal Smooth Transitions for Theme Shifts ONLY during explicit toggle */
html.theme-transitioning body,
html.theme-transitioning .app-sidebar,
html.theme-transitioning .top-header,
html.theme-transitioning .card,
html.theme-transitioning .crm-card,
html.theme-transitioning .table-card,
html.theme-transitioning .filter-card,
html.theme-transitioning .modal-content,
html.theme-transitioning .drawer-body,
html.theme-transitioning .btn-primary,
html.theme-transitioning .btn-secondary {
  transition: background-color 0.24s cubic-bezier(0.16, 1, 0.3, 1),
              border-color 0.24s ease,
              color 0.2s ease,
              box-shadow 0.24s ease !important;
}"""

    if old_transitions in content:
        content = content.replace(old_transitions, new_transitions)
        print("Patched design-system.css: Scoped card/body transitions to html.theme-transitioning")

    # 4. Append Universal Dropdown & Select Anti-Black-Flash rules
    dropdown_rules = """
/* ==========================================================================
   ENTERPRISE INSTANT DROPDOWN & SELECT OPTIMIZATION (ZERO BLACK FLASH / ZERO LAG)
   Directly resolves Windows Chromium native DirectComposition popup latency.
   ========================================================================== */
select,
.form-select,
.tp-select,
select.form-control,
.tp-pill-select-overlay {
  color-scheme: light !important;
  background-color: #ffffff !important;
  color: #0f172a !important;
  appearance: none !important;
  -webkit-appearance: none !important;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%23475569' stroke-width='2.2'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' d='M19 9l-7 7-7-7'%3E%3C/path%3E%3C/svg%3E") !important;
  background-repeat: no-repeat !important;
  background-position: right 10px center !important;
  background-size: 14px !important;
  padding-right: 30px !important;
  transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
}

/* Ensure active/click/focus NEVER flashes black or shifts to dark background */
select:focus, select:active,
.form-select:focus, .form-select:active,
.tp-select:focus, .tp-select:active,
select.form-control:focus, select.form-control:active,
.tp-pill-select-overlay:focus, .tp-pill-select-overlay:active {
  color-scheme: light !important;
  background-color: #ffffff !important;
  color: #0f172a !important;
  outline: none !important;
  border-color: #4f46e5 !important;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.22) !important;
}

/* Literal hex styling for options prevents DirectComposition variable stall */
select option,
.form-select option,
.tp-select option,
select.form-control option,
optgroup {
  color-scheme: light !important;
  background-color: #ffffff !important;
  color: #0f172a !important;
  font-size: 0.875rem;
  padding: 6px 12px;
}

/* Dark Mode Overrides */
[data-theme="dark"] select,
[data-theme="dark"] .form-select,
[data-theme="dark"] .tp-select,
[data-theme="dark"] select.form-control,
[data-theme="dark"] .tp-pill-select-overlay {
  color-scheme: dark !important;
  background-color: #131b2e !important;
  color: #f8fafc !important;
  border-color: #1e2c47 !important;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%2394a3b8' stroke-width='2.2'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' d='M19 9l-7 7-7-7'%3E%3C/path%3E%3C/svg%3E") !important;
}

[data-theme="dark"] select:focus, [data-theme="dark"] select:active,
[data-theme="dark"] .form-select:focus, [data-theme="dark"] .form-select:active,
[data-theme="dark"] .tp-select:focus, [data-theme="dark"] .tp-select:active,
[data-theme="dark"] select.form-control:focus, [data-theme="dark"] select.form-control:active,
[data-theme="dark"] .tp-pill-select-overlay:focus, [data-theme="dark"] .tp-pill-select-overlay:active {
  color-scheme: dark !important;
  background-color: #131b2e !important;
  color: #f8fafc !important;
  border-color: #6366f1 !important;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.3) !important;
}

[data-theme="dark"] select option,
[data-theme="dark"] .form-select option,
[data-theme="dark"] .tp-select option,
[data-theme="dark"] select.form-control option,
[data-theme="dark"] optgroup {
  color-scheme: dark !important;
  background-color: #131b2e !important;
  color: #f8fafc !important;
}
"""
    if "ENTERPRISE INSTANT DROPDOWN & SELECT OPTIMIZATION" not in content:
        content += "\n" + dropdown_rules
        print("Patched design-system.css: Added Enterprise Instant Dropdown rules")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    patch_base_html()
    patch_theme_manager()
    patch_crm_js()
    patch_crm_css()
    patch_design_system_css()
    print("All dropdown and UI flicker patches completed successfully.")
