import os
import re

BASE_DIR = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM"

# 1. Update custom-dropdown.js
def patch_custom_dropdown_js():
    p = os.path.join(BASE_DIR, "static", "js", "custom-dropdown.js")
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()

    # Enhance openMenu and closeMenu
    old_open = """        menu.style.display = 'block';
        menu.classList.add('is-open');
        trigger.classList.add('is-open');
        trigger.setAttribute('aria-expanded', 'true');"""

    new_open = """        menu.style.display = 'block';
        menu.classList.add('is-open');
        wrapper.classList.add('is-open');
        trigger.classList.add('is-open');
        trigger.setAttribute('aria-expanded', 'true');

        var fCard = wrapper.closest('.filter-card, .filter-conditions-list');
        if (fCard) fCard.classList.add('has-open-dropdown');
        var fCol = wrapper.closest('.filter-col, .condition-field');
        if (fCol) fCol.classList.add('has-open-dropdown');"""

    content = content.replace(old_open, new_open)

    old_close = """      function closeMenu() {
        menu.style.display = 'none';
        menu.classList.remove('is-open');
        trigger.classList.remove('is-open');
        trigger.setAttribute('aria-expanded', 'false');
      }"""

    new_close = """      function closeMenu() {
        menu.style.display = 'none';
        menu.classList.remove('is-open');
        wrapper.classList.remove('is-open');
        trigger.classList.remove('is-open');
        trigger.setAttribute('aria-expanded', 'false');

        var fCard = wrapper.closest('.filter-card, .filter-conditions-list');
        if (fCard) fCard.classList.remove('has-open-dropdown');
        var fCol = wrapper.closest('.filter-col, .condition-field');
        if (fCol) fCol.classList.remove('has-open-dropdown');
      }"""

    content = content.replace(old_close, new_close)

    # Dismiss helper
    old_dismiss = """  // Global click outside to dismiss all custom dropdowns
  document.addEventListener('click', function (e) {
    if (!e.target.closest('.tp-cselect-wrapper')) {
      document.querySelectorAll('.tp-cselect-menu.is-open').forEach(function (m) {
        m.style.display = 'none';
        m.classList.remove('is-open');
        var tr = m.parentElement.querySelector('.tp-cselect-trigger');
        if (tr) {
          tr.classList.remove('is-open');
          tr.setAttribute('aria-expanded', 'false');
        }
      });
    }
  });

  // Global Esc key to dismiss
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      document.querySelectorAll('.tp-cselect-menu.is-open').forEach(function (m) {
        m.style.display = 'none';
        m.classList.remove('is-open');
        var tr = m.parentElement.querySelector('.tp-cselect-trigger');
        if (tr) {
          tr.classList.remove('is-open');
          tr.setAttribute('aria-expanded', 'false');
        }
      });
    }
  });"""

    new_dismiss = """  function dismissAllOpen() {
    document.querySelectorAll('.tp-cselect-menu.is-open').forEach(function (m) {
      m.style.display = 'none';
      m.classList.remove('is-open');
      var w = m.closest('.tp-cselect-wrapper');
      if (w) w.classList.remove('is-open');
      var tr = w ? w.querySelector('.tp-cselect-trigger') : null;
      if (tr) {
        tr.classList.remove('is-open');
        tr.setAttribute('aria-expanded', 'false');
      }
    });
    document.querySelectorAll('.has-open-dropdown').forEach(function (el) {
      el.classList.remove('has-open-dropdown');
    });
  }

  // Global click outside to dismiss all custom dropdowns
  document.addEventListener('click', function (e) {
    if (!e.target.closest('.tp-cselect-wrapper')) {
      dismissAllOpen();
    }
  });

  // Global Esc key to dismiss
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      dismissAllOpen();
    }
  });"""

    content = content.replace(old_dismiss, new_dismiss)

    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched custom-dropdown.js")

# 2. Add Stacking Context & Overflow CSS
stacking_css = """
/* ==========================================================================
   DROPDOWN STACKING CONTEXT & OVERFLOW ELEVATION (PREVENTS TABLE CLIPPING)
   ========================================================================== */
.filter-card {
  position: relative !important;
  z-index: 50 !important;
  overflow: visible !important;
}

.filter-card.has-open-dropdown,
.filter-card:focus-within {
  z-index: 1000 !important;
}

.filter-form {
  position: relative !important;
  overflow: visible !important;
}

.filter-col,
.condition-row,
.condition-field {
  position: relative !important;
  overflow: visible !important;
}

.filter-col.has-open-dropdown,
.condition-field.has-open-dropdown {
  z-index: 1010 !important;
}

.crm-card,
.table-card {
  position: relative !important;
  z-index: 1 !important;
}

.tp-cselect-wrapper {
  position: relative !important;
}

.tp-cselect-wrapper.is-open {
  z-index: 1050 !important;
}

.tp-cselect-menu {
  z-index: 9999 !important;
}
"""

def patch_css(rel_path):
    p = os.path.join(BASE_DIR, rel_path)
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()

    # Remove animation on .filter-card, .crm-card if present
    content = content.replace(
        """.filter-card,
.crm-card {
  animation: tpFadeSlideUp var(--motion-enter, 300ms) var(--motion-ease-out) both;
}""",
        """.filter-card,
.crm-card {
  animation: none !important;
}"""
    )

    if "DROPDOWN STACKING CONTEXT & OVERFLOW ELEVATION" not in content:
        content += "\n" + stacking_css

    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Patched {rel_path}")

def update_base_html():
    p = os.path.join(BASE_DIR, "templates", "base.html")
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()
    content = content.replace("custom-dropdown.js' %}?v=20261022_v1", "custom-dropdown.js' %}?v=20261022_v2")
    content = content.replace("crm.css' %}?v=20261022_dropdown_fix", "crm.css' %}?v=20261022_v2")
    content = content.replace("design-system.css' %}?v=20261022_dropdown_fix", "design-system.css' %}?v=20261022_v2")
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    print("Updated base.html cache busters to v2")

if __name__ == "__main__":
    patch_custom_dropdown_js()
    patch_css(os.path.join("static", "css", "crm.css"))
    patch_css(os.path.join("static", "css", "design-system.css"))
    update_base_html()
    print("All stacking context fixes applied successfully.")
