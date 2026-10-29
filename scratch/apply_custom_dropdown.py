import os

BASE_DIR = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM"

css_rules = """
/* ==========================================================================
   MODERN CUSTOM DROPDOWN COMPONENT STYLES
   ========================================================================== */
.tp-cselect-wrapper {
  position: relative;
  display: block;
  width: 100%;
}

.tp-cselect-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  height: 36px;
  padding: 6px 12px;
  font-family: inherit;
  font-size: 0.835rem;
  font-weight: 500;
  border-radius: var(--radius-sm, 6px);
  background-color: var(--bg-card, #ffffff);
  color: var(--text-main, #0f172a);
  border: 1px solid var(--border-color, #cbd5e1);
  cursor: pointer;
  text-align: left;
  user-select: none;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.tp-cselect-trigger:focus,
.tp-cselect-trigger.is-open {
  outline: none;
  border-color: var(--primary, #4f46e5);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
}

.tp-cselect-value {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.tp-cselect-chevron {
  display: flex;
  align-items: center;
  color: var(--text-muted, #64748b);
  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  flex-shrink: 0;
}

.tp-cselect-trigger.is-open .tp-cselect-chevron {
  transform: rotate(180deg);
  color: var(--primary, #4f46e5);
}

.tp-cselect-menu {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  min-width: 100%;
  max-height: 250px;
  overflow-y: auto;
  margin-top: 5px;
  padding: 5px;
  background-color: var(--bg-card, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 10px;
  box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.14), 0 8px 10px -6px rgba(15, 23, 42, 0.08);
  z-index: 1050;
  animation: tpCSelectFadeIn 0.16s cubic-bezier(0.16, 1, 0.3, 1);
}

.tp-cselect-menu.drop-up {
  top: auto;
  bottom: 100%;
  margin-top: 0;
  margin-bottom: 5px;
}

@keyframes tpCSelectFadeIn {
  0% {
    opacity: 0;
    transform: translateY(-4px);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}

.tp-cselect-menu::-webkit-scrollbar {
  width: 5px;
}
.tp-cselect-menu::-webkit-scrollbar-thumb {
  background-color: #cbd5e1;
  border-radius: 10px;
}

.tp-cselect-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 12px;
  font-size: 0.835rem;
  font-weight: 500;
  border-radius: 6px;
  color: var(--text-main, #334155);
  cursor: pointer;
  transition: background-color 0.12s ease, color 0.12s ease;
  user-select: none;
}

.tp-cselect-option:hover,
.tp-cselect-option.is-highlighted {
  background-color: var(--bg-card-hover, #f1f5f9);
  color: var(--text-main, #0f172a);
}

.tp-cselect-option.is-selected {
  background-color: #eef2ff;
  color: #4338ca;
  font-weight: 600;
}

.tp-cselect-check {
  display: none;
  align-items: center;
  color: #4f46e5;
  flex-shrink: 0;
}

.tp-cselect-option.is-selected .tp-cselect-check {
  display: flex;
}

/* Dark Mode */
[data-theme="dark"] .tp-cselect-trigger {
  background-color: #131b2e;
  color: #f8fafc;
  border-color: #1e2c47;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

[data-theme="dark"] .tp-cselect-trigger:focus,
[data-theme="dark"] .tp-cselect-trigger.is-open {
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.28);
}

[data-theme="dark"] .tp-cselect-menu {
  background-color: #131b2e;
  border-color: #222f49;
  box-shadow: 0 12px 28px -4px rgba(0, 0, 0, 0.7);
}

[data-theme="dark"] .tp-cselect-menu::-webkit-scrollbar-thumb {
  background-color: #334155;
}

[data-theme="dark"] .tp-cselect-option {
  color: #cbd5e1;
}

[data-theme="dark"] .tp-cselect-option:hover,
[data-theme="dark"] .tp-cselect-option.is-highlighted {
  background-color: #1b263e;
  color: #ffffff;
}

[data-theme="dark"] .tp-cselect-option.is-selected {
  background-color: rgba(99, 102, 241, 0.18);
  color: #818cf8;
}

[data-theme="dark"] .tp-cselect-check {
  color: #818cf8;
}
"""

def add_css_to_file(rel_path):
    p = os.path.join(BASE_DIR, rel_path)
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()
    if "MODERN CUSTOM DROPDOWN COMPONENT STYLES" not in content:
        content += "\n" + css_rules
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Added custom dropdown CSS to {rel_path}")

def update_base_html():
    p = os.path.join(BASE_DIR, "templates", "base.html")
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()
    
    script_tag = "<script src=\"{% static 'js/custom-dropdown.js' %}?v=20261022_v1\"></script>"
    if "custom-dropdown.js" not in content:
        content = content.replace(
            "<script src=\"{% static 'js/auto-filter.js' %}?v=20261012\"></script>",
            "<script src=\"{% static 'js/auto-filter.js' %}?v=20261012\"></script>\n  " + script_tag
        )
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        print("Added custom-dropdown.js to base.html")

if __name__ == "__main__":
    add_css_to_file(os.path.join("static", "css", "crm.css"))
    add_css_to_file(os.path.join("static", "css", "design-system.css"))
    update_base_html()
    print("Done!")
