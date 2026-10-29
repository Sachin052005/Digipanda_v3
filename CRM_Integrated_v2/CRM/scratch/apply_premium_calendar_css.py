css_replacement = """/* ==========================================================================
   PREMIUM SMART CALENDAR POPOVER & TRIGGER COMPONENT
   ========================================================================== */

/* Hide standalone monogram when sidebar is expanded; show only when collapsed */
.app-sidebar .brand-symbol {
  display: none !important;
}
.app-sidebar.collapsed .brand-symbol {
  display: block !important;
}

.tp-smart-date-container {
  position: relative;
  display: inline-flex;
  align-items: center;
  vertical-align: middle;
  width: auto;
}

.tp-smart-date-container.w-100 {
  width: 100%;
}

.tp-smart-date-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  height: 38px;
  padding: 0 12px;
  background: var(--tp-surface-card, #ffffff);
  border: 1px solid var(--tp-surface-border, #e2e8f0);
  border-radius: 8px;
  color: var(--tp-text-primary, #0f172a);
  font-size: 0.84rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s cubic-bezier(0.16, 1, 0.3, 1);
  user-select: none;
  outline: none;
  min-width: 190px;
  max-width: 250px;
  width: 100%;
}

[data-theme="dark"] .tp-smart-date-trigger {
  background: #111827;
  border-color: #1f2937;
  color: #f3f4f6;
}

.tp-smart-date-trigger:hover {
  border-color: #3b82f6;
}

.tp-smart-date-trigger:focus-visible,
.tp-smart-date-trigger.is-open {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.tp-smart-date-trigger.has-filter {
  border-color: #3b82f6;
  background: rgba(59, 130, 246, 0.08);
  color: #1d4ed8;
}

[data-theme="dark"] .tp-smart-date-trigger.has-filter {
  background: rgba(59, 130, 246, 0.15);
  border-color: #3b82f6;
  color: #93c5fd;
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.3);
}

.tp-smart-date-icon {
  color: #3b82f6;
  flex-shrink: 0;
}

[data-theme="dark"] .tp-smart-date-icon {
  color: #60a5fa;
}

.tp-smart-date-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 170px;
  font-size: 0.84rem;
}

.tp-smart-date-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #3b82f6;
  flex-shrink: 0;
}

[data-theme="dark"] .tp-smart-date-dot {
  background: #60a5fa;
}

.tp-smart-date-quick-reset {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: none;
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  margin-left: 2px;
  padding: 0;
  transition: background 0.12s, transform 0.12s;
}

.tp-smart-date-quick-reset:hover {
  background: rgba(239, 68, 68, 0.25);
  transform: scale(1.08);
}

.tp-smart-date-chevron {
  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  color: var(--tp-text-muted, #64748b);
  flex-shrink: 0;
  margin-left: 2px;
}

.tp-smart-date-trigger.is-open .tp-smart-date-chevron {
  transform: rotate(180deg);
}

/* Popover Floating Container */
.tp-smart-date-popover {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  z-index: 1060;
  width: 680px;
  max-width: 95vw;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  box-shadow: 0 20px 50px -10px rgba(0, 0, 0, 0.16), 0 0 0 1px rgba(0, 0, 0, 0.04);
  animation: smartCalPopIn 0.18s cubic-bezier(0.16, 1, 0.3, 1);
  font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', Roboto, sans-serif;
  overflow: hidden;
}

.tp-smart-date-popover.popover-up {
  top: auto;
  bottom: calc(100% + 6px);
}

.tp-smart-date-popover.popover-right {
  left: auto;
  right: 0;
}

[data-theme="dark"] .tp-smart-date-popover {
  background: #0f172a;
  border-color: rgba(255, 255, 255, 0.08);
  box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.75), 0 0 0 1px rgba(255, 255, 255, 0.06);
}

/* Popover Body & Panels */
.tp-smart-date-body {
  display: flex;
  min-height: 330px;
}

/* Left Presets Sidebar */
.tp-smart-date-presets {
  width: 140px;
  flex-shrink: 0;
  padding: 14px 10px;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  gap: 3px;
  background: #f8fafc;
}

[data-theme="dark"] .tp-smart-date-presets {
  background: rgba(15, 23, 42, 0.85);
  border-right-color: rgba(255, 255, 255, 0.06);
}

.tp-smart-preset-btn {
  display: block;
  width: 100%;
  text-align: left;
  padding: 8px 12px;
  font-size: 0.8rem;
  font-weight: 500;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: #475569;
  cursor: pointer;
  transition: all 0.15s ease;
  user-select: none;
}

[data-theme="dark"] .tp-smart-preset-btn {
  color: #94a3b8;
}

.tp-smart-preset-btn:hover {
  background: #f1f5f9;
  color: #0f172a;
  transform: translateX(2px);
}

[data-theme="dark"] .tp-smart-preset-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #f8fafc;
}

.tp-smart-preset-btn.is-active {
  background: rgba(37, 99, 235, 0.1) !important;
  color: #2563eb !important;
  font-weight: 600;
  border-left: 3px solid #2563eb;
  border-radius: 0 8px 8px 0;
}

[data-theme="dark"] .tp-smart-preset-btn.is-active {
  background: rgba(59, 130, 246, 0.16) !important;
  color: #60a5fa !important;
  border-left: 3px solid #3b82f6;
  border-radius: 0 8px 8px 0;
}

/* Right Main Calendar Area */
.tp-smart-date-main {
  flex: 1;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.tp-smart-date-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e2e8f0;
}

[data-theme="dark"] .tp-smart-date-header {
  border-bottom-color: rgba(255, 255, 255, 0.06);
}

.tp-smart-date-inputs {
  display: flex;
  align-items: center;
  gap: 10px;
}

.tp-smart-date-box {
  display: flex;
  flex-direction: column;
  background: #f8fafc;
  padding: 5px 12px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  min-width: 116px;
  transition: border-color 0.15s, box-shadow 0.15s;
}

[data-theme="dark"] .tp-smart-date-box {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255, 255, 255, 0.08);
}

.tp-smart-date-box:focus-within {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.tp-box-label {
  font-size: 0.64rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #64748b;
  margin-bottom: 1px;
}

[data-theme="dark"] .tp-box-label {
  color: #64748b;
}

.tp-smart-date-input-field {
  height: 24px;
  width: 100%;
  border: none;
  padding: 0;
  font-size: 0.85rem;
  font-weight: 600;
  color: #0f172a;
  background: transparent;
  outline: none;
}

[data-theme="dark"] .tp-smart-date-input-field {
  color: #f1f5f9;
}

.tp-smart-date-input-field::placeholder {
  color: #94a3b8;
  font-weight: 500;
}

[data-theme="dark"] .tp-smart-date-input-field::placeholder {
  color: #475569;
}

.tp-smart-date-arrow {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  padding: 0 4px;
}

.tp-smart-date-duration {
  font-size: 0.72rem;
  font-weight: 700;
  background: rgba(37, 99, 235, 0.08);
  color: #2563eb;
  padding: 3px 10px;
  border-radius: 20px;
  border: 1px solid rgba(37, 99, 235, 0.2);
}

[data-theme="dark"] .tp-smart-date-duration {
  background: rgba(59, 130, 246, 0.12);
  color: #93c5fd;
  border-color: rgba(59, 130, 246, 0.25);
}

/* Dual Months Layout */
.tp-smart-date-dual-view {
  display: flex;
  gap: 24px;
}

.tp-smart-month {
  flex: 1;
  min-width: 0;
}

.tp-smart-date-dual-view #month1 {
  padding-right: 18px;
  border-right: 1px solid #f1f5f9;
}

[data-theme="dark"] .tp-smart-date-dual-view #month1 {
  border-right-color: rgba(255, 255, 255, 0.06);
}

.tp-smart-month-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 32px;
  margin-bottom: 10px;
}

.tp-month-title {
  font-size: 0.85rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: #0f172a;
}

[data-theme="dark"] .tp-month-title {
  color: #f1f5f9;
}

.tp-month-nav-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 7px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  color: #475569;
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
}

[data-theme="dark"] .tp-month-nav-btn {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.08);
  color: #cbd5e1;
}

.tp-month-nav-btn:hover {
  border-color: #3b82f6;
  color: #ffffff;
  background: #3b82f6;
}

.tp-nav-spacer {
  width: 28px;
  height: 28px;
  display: inline-block;
}

.tp-smart-weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  text-align: center;
  font-size: 0.7rem;
  font-weight: 700;
  color: #94a3b8;
  margin-bottom: 6px;
}

[data-theme="dark"] .tp-smart-weekdays {
  color: #64748b;
}

.tp-smart-days-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  row-gap: 2px;
}

.tp-smart-day-cell {
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 0.8rem;
  font-weight: 500;
  position: relative;
  color: #334155;
  user-select: none;
  border-radius: 6px;
  transition: background 0.1s, color 0.1s;
}

[data-theme="dark"] .tp-smart-day-cell {
  color: #cbd5e1;
}

.tp-smart-day-cell.is-outside {
  opacity: 0.18 !important;
  pointer-events: none;
}

.tp-smart-day-cell.is-today .tp-day-num {
  font-weight: 800;
  text-decoration: underline;
  text-decoration-color: #3b82f6;
  text-underline-offset: 3px;
}

.tp-smart-day-cell:hover:not(.is-start):not(.is-end):not(.is-single) {
  background: #f1f5f9;
  color: #0f172a;
}

[data-theme="dark"] .tp-smart-day-cell:hover:not(.is-start):not(.is-end):not(.is-single) {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}

.tp-smart-day-cell.is-start {
  background: #2563eb !important;
  color: #ffffff !important;
  font-weight: 700;
  border-radius: 7px 0 0 7px !important;
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.35);
}

.tp-smart-day-cell.is-end {
  background: #2563eb !important;
  color: #ffffff !important;
  font-weight: 700;
  border-radius: 0 7px 7px 0 !important;
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.35);
}

.tp-smart-day-cell.is-single {
  background: #2563eb !important;
  color: #ffffff !important;
  font-weight: 700;
  border-radius: 7px !important;
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.35);
}

.tp-smart-day-cell.is-in-range {
  background: rgba(37, 99, 235, 0.09) !important;
  color: #1d4ed8 !important;
  border-radius: 0 !important;
}

[data-theme="dark"] .tp-smart-day-cell.is-in-range {
  background: rgba(37, 99, 235, 0.18) !important;
  color: #93c5fd !important;
  border-radius: 0 !important;
}

/* Footer Section */
.tp-smart-date-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  border-top: 1px solid #e2e8f0;
  background: #f8fafc;
}

[data-theme="dark"] .tp-smart-date-footer {
  background: rgba(15, 23, 42, 0.95);
  border-top-color: rgba(255, 255, 255, 0.06);
}

.tp-smart-date-summary {
  font-size: 0.8rem;
  font-weight: 500;
  color: #64748b;
}

[data-theme="dark"] .tp-smart-date-summary {
  color: #94a3b8;
}

.tp-smart-date-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tp-smart-btn-clear {
  font-size: 0.8rem;
  padding: 6px 12px;
  color: #94a3b8;
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.12s;
}

.tp-smart-btn-clear:hover {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.08);
}

.tp-smart-btn-cancel {
  font-size: 0.8rem;
  padding: 6px 14px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  color: #334155;
  border-radius: 7px;
  cursor: pointer;
  transition: background 0.12s, border-color 0.12s;
}

[data-theme="dark"] .tp-smart-btn-cancel {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.1);
  color: #cbd5e1;
}

.tp-smart-btn-cancel:hover {
  background: #f1f5f9;
}

[data-theme="dark"] .tp-smart-btn-cancel:hover {
  background: rgba(255, 255, 255, 0.08);
}

.tp-smart-btn-apply {
  font-size: 0.8rem;
  padding: 6px 18px;
  font-weight: 600;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: #ffffff;
  border: 1px solid #3b82f6;
  border-radius: 7px;
  cursor: pointer;
  transition: all 0.15s;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.35);
}

.tp-smart-btn-apply:hover {
  background: linear-gradient(135deg, #1d4ed8, #1e40af);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.45);
}

/* Mobile & Tablet Responsive Layout */
@media (max-width: 768px) {
  .tp-smart-date-popover {
    width: calc(100vw - 24px);
    max-width: 360px;
  }
  .tp-smart-date-body {
    flex-direction: column;
  }
  .tp-smart-date-presets {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid #e2e8f0;
    flex-direction: row;
    overflow-x: auto;
    padding: 8px;
    gap: 6px;
    border-radius: 12px 12px 0 0;
  }
  .tp-smart-preset-btn {
    width: auto;
    white-space: nowrap;
    padding: 5px 10px;
    font-size: 0.75rem;
  }
  .tp-smart-date-dual-view #month2 {
    display: none;
  }
  .tp-smart-date-dual-view #month1 {
    padding-right: 0;
    border-right: none;
  }
  .tp-smart-date-footer {
    flex-direction: column;
    gap: 8px;
    align-items: stretch;
  }
  .tp-smart-date-actions {
    justify-content: flex-end;
  }
}
"""

for css_file in [r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\static\css\design-system.css", r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\static\css\crm.css"]:
    with open(css_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    start_marker = ".tp-smart-date-container {"
    idx = content.find(start_marker)
    if idx != -1:
        # replace from idx to the end of smart calendar section
        content = content[:idx] + css_replacement
        with open(css_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Replaced Smart Calendar CSS in {css_file}!")
    else:
        print(f"Start marker not found in {css_file}")
