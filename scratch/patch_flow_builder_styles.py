# -*- coding: utf-8 -*-
"""
Patch flow builder CSS, HTML, and JS for modern UI/UX and authentic WhatsApp simulator.
"""
import re
import os

# 1. Update CRM/chat/static/chat/css/flow_builder.css
css_path = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/chat/static/chat/css/flow_builder.css'
with open(css_path, 'r', encoding='utf-8') as f:
    css = f.read()

# Add Modal styles if not already present
modal_css = """
/* ==========================================================================
   Modern SaaS Modal System
   ========================================================================== */
.modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(15, 23, 42, 0.78);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    z-index: 9999;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    animation: modalFadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-box {
    background: #0f172a;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 16px;
    width: 100%;
    color: #f8fafc;
    box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.8), 0 0 0 1px rgba(255, 255, 255, 0.05);
    overflow: hidden;
    animation: modalPop 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-header {
    padding: 18px 22px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(255, 255, 255, 0.02);
}

.modal-header h3 {
    margin: 0;
    font-size: 15px;
    font-weight: 700;
    color: #f8fafc;
    letter-spacing: -0.01em;
}

.modal-close-btn {
    background: transparent;
    border: none;
    color: #94a3b8;
    width: 32px;
    height: 32px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.15s ease;
    padding: 0;
}

.modal-close-btn:hover {
    color: #fff;
    background: rgba(255, 255, 255, 0.1);
}

.form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 14px;
}

.form-label {
    font-size: 11px;
    font-weight: 700;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.form-input, .form-control {
    width: 100%;
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    color: #f8fafc;
    padding: 9px 12px;
    font-size: 13px;
    transition: all 0.2s;
    outline: none;
    box-sizing: border-box;
    font-family: inherit;
}

.form-input:focus, .form-control:focus {
    border-color: #0ea5e9;
    box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.15);
    background: #243044;
}

.form-select {
    width: 100%;
    background: #1e293b url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='%2394a3b8' viewBox='0 0 24 24'%3E%3Cpath d='M7 10l5 5 5-5z'/%3E%3C/svg%3E") no-repeat right 12px center;
    border: 1px solid #334155;
    border-radius: 8px;
    color: #f8fafc;
    padding: 9px 36px 9px 12px;
    font-size: 13px;
    appearance: none;
    cursor: pointer;
    outline: none;
    transition: all 0.2s;
    box-sizing: border-box;
}

.form-select:focus {
    border-color: #0ea5e9;
    box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.15);
    background-color: #243044;
}

@keyframes modalFadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

@keyframes modalPop {
    from { transform: scale(0.96) translateY(8px); opacity: 0; }
    to { transform: scale(1) translateY(0); opacity: 1; }
}
"""

if '.modal-box {' not in css:
    css = modal_css + "\n" + css

# Replace simulator styles with ultra-modern smartphone WhatsApp UI
old_sim_start = css.find('/* ==========================================================================\n   4. Slide-out WhatsApp Test Simulator')
if old_sim_start != -1:
    old_sim_end = css.find('/* ==========================================================================\n   5. Minimap', old_sim_start)
    if old_sim_end == -1:
        old_sim_end = css.find('/* Minimap', old_sim_start)
    if old_sim_end == -1:
        old_sim_end = old_sim_start + 4000
else:
    old_sim_start = css.find('.simulator-drawer {')
    old_sim_end = old_sim_start + 3000

new_sim_css = """/* ==========================================================================
   4. Slide-out WhatsApp Test Simulator (Ultra-Realistic Smartphone Mockup)
   ========================================================================== */

.simulator-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(15, 23, 42, 0.7);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    z-index: 100;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.25s ease;
}

.simulator-backdrop.open {
    opacity: 1;
    pointer-events: auto;
}

.simulator-drawer {
    position: fixed;
    top: 20px;
    right: 24px;
    bottom: 20px;
    width: 390px;
    max-height: calc(100vh - 40px);
    background: #0b141a;
    border: 4px solid #1f2c34;
    border-radius: 42px;
    z-index: 101;
    display: flex;
    flex-direction: column;
    box-shadow: 0 30px 90px -15px rgba(0, 0, 0, 0.9), 0 0 0 1px rgba(255, 255, 255, 0.08);
    transform: translateX(450px);
    transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1);
    overflow: hidden;
}

.simulator-drawer.open {
    transform: translateX(0);
}

/* Smartphone Top Bar & Dynamic Island */
.sim-device-top {
    height: 30px;
    background: #1f2c34;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 20px;
    color: #94a3b8;
    font-size: 11px;
    font-weight: 600;
    user-select: none;
    flex-shrink: 0;
}

.sim-device-time {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    letter-spacing: 0.02em;
}

.sim-dynamic-island {
    width: 86px;
    height: 16px;
    background: #0b141a;
    border-radius: 20px;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding-right: 10px;
    gap: 6px;
}

.sim-island-cam {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #1e293b;
    border: 1px solid #334155;
}

.sim-device-indicators {
    display: flex;
    align-items: center;
    gap: 6px;
}

/* WhatsApp Application Header */
.sim-header {
    background: #202c33;
    padding: 10px 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    flex-shrink: 0;
}

.sim-brand {
    display: flex;
    align-items: center;
    gap: 10px;
}

.sim-avatar-wrap {
    position: relative;
}

.sim-avatar {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: linear-gradient(135deg, #00a884, #008069);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    color: white;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
}

.sim-online-dot {
    position: absolute;
    bottom: 0;
    right: 0;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #25d366;
    border: 2px solid #202c33;
    box-shadow: 0 0 6px rgba(37, 211, 102, 0.7);
}

.sim-titles h3 {
    margin: 0;
    font-size: 13.5px;
    font-weight: 700;
    color: #e9edef;
    letter-spacing: -0.01em;
    display: flex;
    align-items: center;
    gap: 5px;
}

.sim-status {
    font-size: 11px;
    color: #00a884;
    font-weight: 500;
}

.sim-header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
}

.sim-btn-restart {
    display: flex;
    align-items: center;
    gap: 5px;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: #cbd5e1;
    padding: 5px 9px;
    border-radius: 8px;
    font-size: 11.5px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
}

.sim-btn-restart:hover {
    color: #fff;
    background: rgba(255, 255, 255, 0.16);
    border-color: rgba(255, 255, 255, 0.2);
}

.sim-btn-close {
    background: transparent;
    border: none;
    color: #94a3b8;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.15s ease;
}

.sim-btn-close:hover {
    color: #fff;
    background: rgba(255, 255, 255, 0.1);
}

/* WhatsApp Screen & Wallpaper */
.sim-screen {
    flex: 1;
    overflow-y: auto;
    position: relative;
    background-color: #0b141a;
    background-image: radial-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px);
    background-size: 18px 18px;
    display: flex;
    flex-direction: column;
}

.sim-security-notice {
    margin: 12px 14px 4px 14px;
    background: #182229;
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 8px;
    padding: 7px 10px;
    font-size: 10.5px;
    color: #ffd279;
    text-align: center;
    line-height: 1.4;
    display: flex;
    align-items: center;
    gap: 7px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}

.sim-security-notice svg {
    flex-shrink: 0;
    color: #ffd279;
}

.sim-date-pill {
    align-self: center;
    margin: 8px 0;
    background: #182229;
    color: #8696a0;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.05em;
    padding: 4px 10px;
    border-radius: 10px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.3);
}

.sim-messages {
    flex: 1;
    padding: 10px 14px 14px 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
}

/* WhatsApp Message Bubbles */
.sim-bubble {
    max-width: 82%;
    padding: 8px 12px;
    border-radius: 12px;
    font-size: 13px;
    line-height: 1.45;
    position: relative;
    word-break: break-word;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
    animation: bubblePop 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.sim-bubble-bot {
    align-self: flex-start;
    background-color: #202c33;
    color: #e9edef;
    border-top-left-radius: 3px;
    margin-left: 4px;
}

.sim-bubble-bot::before {
    content: "";
    position: absolute;
    top: 0;
    left: -6px;
    width: 0;
    height: 0;
    border-top: 8px solid #202c33;
    border-left: 8px solid transparent;
}

.sim-bubble-user {
    align-self: flex-end;
    background-color: #005c4b;
    color: #e9edef;
    border-top-right-radius: 3px;
    margin-right: 4px;
}

.sim-bubble-user::before {
    content: "";
    position: absolute;
    top: 0;
    right: -6px;
    width: 0;
    height: 0;
    border-top: 8px solid #005c4b;
    border-right: 8px solid transparent;
}

.sim-bubble-meta {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 4px;
    margin-top: 4px;
}

.sim-bubble-time {
    font-size: 10px;
    color: rgba(255, 255, 255, 0.55);
}

.sim-double-tick {
    display: inline-flex;
    align-items: center;
}

.sim-crm-note {
    align-self: center;
    background: rgba(14, 165, 233, 0.12);
    border: 1px solid rgba(14, 165, 233, 0.3);
    color: #38bdf8;
    padding: 6px 12px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    max-width: 90%;
    text-align: center;
    line-height: 1.35;
}

/* WhatsApp Interactive Button Cards */
.sim-buttons-wrap {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 8px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    padding-top: 8px;
}

.sim-btn-choice {
    background: rgba(0, 168, 132, 0.1);
    border: 1px solid rgba(0, 168, 132, 0.35);
    color: #25d366;
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    text-align: center;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    transition: all 0.15s ease;
}

.sim-btn-choice:hover {
    background: #00a884;
    color: #ffffff;
    border-color: #00a884;
    transform: translateY(-1px);
    box-shadow: 0 4px 10px rgba(0, 168, 132, 0.35);
}

.sim-list-btn {
    margin-top: 8px;
    width: 100%;
    background: #00a884;
    color: white;
    border: none;
    padding: 9px 14px;
    border-radius: 8px;
    font-size: 12.5px;
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    cursor: pointer;
    transition: background 0.15s ease;
}

.sim-list-btn:hover {
    background: #029474;
}

/* Bottom Sheet for WhatsApp List Menus */
.sim-list-sheet {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    background: #202c33;
    border-top: 1px solid rgba(255, 255, 255, 0.12);
    border-top-left-radius: 20px;
    border-top-right-radius: 20px;
    max-height: 65%;
    overflow-y: auto;
    z-index: 20;
    transform: translateY(100%);
    transition: transform 0.28s cubic-bezier(0.16, 1, 0.3, 1);
    box-shadow: 0 -8px 25px rgba(0, 0, 0, 0.6);
}

.sim-list-sheet.open {
    transform: translateY(0);
}

.sim-sheet-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 18px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.sim-sheet-header h4 {
    margin: 0;
    font-size: 13.5px;
    font-weight: 700;
    color: #e9edef;
}

.sim-sheet-close {
    background: transparent;
    border: none;
    color: #94a3b8;
    width: 28px;
    height: 28px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.15s ease;
    padding: 0;
}

.sim-sheet-close:hover {
    color: #fff;
    background: rgba(255, 255, 255, 0.1);
}

.sim-sheet-items {
    padding: 10px 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.sim-sheet-item {
    padding: 10px 12px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.04);
    cursor: pointer;
    transition: all 0.15s ease;
}

.sim-sheet-item:hover {
    background: rgba(0, 168, 132, 0.22);
    transform: translateX(2px);
}

.sim-sheet-item-title {
    font-size: 12.5px;
    font-weight: 600;
    color: #e9edef;
}

.sim-sheet-item-desc {
    font-size: 11px;
    color: #8696a0;
    margin-top: 2px;
}

/* Media and Location in Simulator */
.sim-media-card {
    display: flex;
    align-items: center;
    gap: 10px;
    background: rgba(0, 0, 0, 0.25);
    padding: 9px 12px;
    border-radius: 8px;
    margin-bottom: 6px;
    border: 1px solid rgba(255, 255, 255, 0.05);
}

.sim-media-icon {
    font-size: 20px;
}

.sim-media-info {
    overflow: hidden;
}

.sim-media-filename {
    font-size: 12px;
    font-weight: 600;
    color: #e9edef;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.sim-location-card {
    display: flex;
    flex-direction: column;
    gap: 4px;
    background: rgba(0, 0, 0, 0.25);
    padding: 9px 12px;
    border-radius: 8px;
    margin-bottom: 6px;
    border: 1px solid rgba(255, 255, 255, 0.05);
}

.sim-loc-title {
    font-size: 12.5px;
    font-weight: 700;
    color: #34d399;
}

.sim-loc-addr {
    font-size: 11px;
    color: #94a3b8;
}

/* WhatsApp Input Footer */
.sim-footer {
    background: #202c33;
    padding: 10px 12px;
    display: flex;
    align-items: center;
    gap: 8px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    flex-shrink: 0;
}

.sim-input-box {
    flex: 1;
    display: flex;
    align-items: center;
    background: #2a3942;
    border-radius: 20px;
    padding: 0 12px;
}

.sim-footer input {
    width: 100%;
    background: transparent;
    border: none;
    padding: 9px 0;
    color: #e9edef;
    font-size: 13px;
    outline: none;
}

.sim-footer input::placeholder {
    color: #8696a0;
}

.sim-footer button[type="submit"] {
    background: #00a884;
    border: none;
    border-radius: 50%;
    width: 38px;
    height: 38px;
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    flex-shrink: 0;
    transition: all 0.15s ease;
    box-shadow: 0 2px 8px rgba(0, 168, 132, 0.4);
}

.sim-footer button[type="submit"]:hover {
    background: #029474;
    transform: scale(1.05);
}

/* Telemetry & State Debug Accordion */
.sim-debug-drawer {
    border-top: 1px solid #1e293b;
    background: #090d16;
    flex-shrink: 0;
}

.sim-debug-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 14px;
    cursor: pointer;
    background: rgba(255, 255, 255, 0.02);
    user-select: none;
    color: #94a3b8;
    transition: color 0.15s;
}

.sim-debug-header:hover {
    color: #fff;
    background: rgba(255, 255, 255, 0.05);
}

.sim-debug-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #10b981;
    box-shadow: 0 0 6px rgba(16, 185, 129, 0.6);
}

.sim-debug-content {
    padding: 10px 14px;
    border-top: 1px solid rgba(255, 255, 255, 0.04);
}

.sim-debug-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
}

.sim-debug-col {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.sim-debug-label {
    font-size: 9px;
    font-weight: 800;
    color: #64748b;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

.sim-debug-row {
    font-size: 11px;
    color: #cbd5e1;
}

.sim-debug-val {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    color: #38bdf8;
    font-weight: 600;
}

.sim-debug-data {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 10.5px;
    color: #a7f3d0;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 75px;
    overflow-y: auto;
    background: rgba(0,0,0,0.3);
    padding: 4px 6px;
    border-radius: 4px;
}

@keyframes bubblePop {
    from { opacity: 0; transform: translateY(4px) scale(0.98); }
    to { opacity: 1; transform: translateY(0) scale(1); }
}
"""

if old_sim_start != -1 and old_sim_end > old_sim_start:
    css = css[:old_sim_start] + new_sim_css + "\n\n" + css[old_sim_end:]
else:
    css = css + "\n\n" + new_sim_css

with open(css_path, 'w', encoding='utf-8') as f:
    f.write(css)

print("Updated flow_builder.css successfully!")
