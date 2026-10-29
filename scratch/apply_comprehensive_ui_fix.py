# -*- coding: utf-8 -*-
import os
import re

SVG_CLOSE = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>'

# -------------------------------------------------------------
# 1. Update CRM/chat/templates/chat/automation_list.html
# -------------------------------------------------------------
auto_list_path = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/chat/templates/chat/automation_list.html'
with open(auto_list_path, 'r', encoding='utf-8') as f:
    al_content = f.read()

# Replace &times; in automation_list.html
al_content = al_content.replace(
    '<button class="modal-close-btn" id="btnCloseNewModal">&times;</button>',
    f'<button class="modal-close-btn" id="btnCloseNewModal" title="Close">{SVG_CLOSE}</button>'
)
al_content = al_content.replace(
    '<button class="modal-close-btn" id="btnCancelConfirmModal">&times;</button>',
    f'<button class="modal-close-btn" id="btnCancelConfirmModal" title="Close">{SVG_CLOSE}</button>'
)

with open(auto_list_path, 'w', encoding='utf-8') as f:
    f.write(al_content)
print("Updated automation_list.html successfully!")


# -------------------------------------------------------------
# 2. Update CRM/chat/templates/chat/flow_builder.html
# -------------------------------------------------------------
fb_path = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/chat/templates/chat/flow_builder.html'
with open(fb_path, 'r', encoding='utf-8') as f:
    fb_content = f.read()

# Replace all &times; close buttons
fb_content = fb_content.replace(
    '<button class="icon-close-btn" id="btnCloseInspector" title="Deselect">&times;</button>',
    f'<button class="icon-close-btn" id="btnCloseInspector" title="Deselect">{SVG_CLOSE}</button>'
)
fb_content = fb_content.replace(
    '<button type="button" class="icon-close-btn" id="btnCloseVarPicker">&times;</button>',
    f'<button type="button" class="icon-close-btn" id="btnCloseVarPicker" title="Close">{SVG_CLOSE}</button>'
)
fb_content = fb_content.replace(
    '<button type="button" class="icon-close-btn" id="btnCloseValidationModal">&times;</button>',
    f'<button type="button" class="icon-close-btn" id="btnCloseValidationModal" title="Close">{SVG_CLOSE}</button>'
)
fb_content = fb_content.replace(
    '<button class="modal-close-btn" id="btnCancelDialogX">&times;</button>',
    f'<button class="modal-close-btn" id="btnCancelDialogX" title="Close">{SVG_CLOSE}</button>'
)
fb_content = fb_content.replace(
    '<button class="modal-close-btn" id="btnCloseAIAssistant">&times;</button>',
    f'<button class="modal-close-btn" id="btnCloseAIAssistant" title="Close">{SVG_CLOSE}</button>'
)
fb_content = fb_content.replace(
    '<button class="modal-close-btn" id="btnCloseVersionHistory">&times;</button>',
    f'<button class="modal-close-btn" id="btnCloseVersionHistory" title="Close">{SVG_CLOSE}</button>'
)
fb_content = fb_content.replace(
    '<button class="modal-close-btn" id="btnCloseNewFlowModal">&times;</button>',
    f'<button class="modal-close-btn" id="btnCloseNewFlowModal" title="Close">{SVG_CLOSE}</button>'
)

# Replace Simulator Drawer structure in flow_builder.html
old_sim_snippet = re.search(r'(<!--\s*Slide-out WhatsApp Test Simulator Drawer\s*-->.*?</form>)', fb_content, re.DOTALL)
if old_sim_snippet:
    new_sim_markup = """<!-- Slide-out WhatsApp Test Simulator Drawer -->
        <div class="simulator-backdrop" id="simulatorBackdrop"></div>
        <div class="simulator-drawer" id="simulatorDrawer">
            <!-- Smartphone Bezel Dynamic Island / Status Bar -->
            <div class="sim-device-top">
                <div class="sim-device-time">09:41</div>
                <div class="sim-dynamic-island">
                    <span class="sim-island-cam"></span>
                </div>
                <div class="sim-device-indicators">
                    <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M12 3c-4.97 0-9 4.03-9 9 0 2.12.74 4.07 1.97 5.61L4.35 21l3.53-.93C9.36 20.66 10.64 21 12 21c4.97 0 9-4.03 9-9s-4.03-9-9-9z"/></svg>
                    <span style="font-size: 10px; font-weight: 700;">5G</span>
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><rect x="2" y="7" width="18" height="10" rx="2" ry="2" fill="none" stroke="currentColor" stroke-width="2"/><line x1="22" y1="11" x2="22" y2="13" stroke="currentColor" stroke-width="2"/><rect x="4" y="9" width="12" height="6" fill="currentColor"/></svg>
                </div>
            </div>

            <!-- WhatsApp Application Bar -->
            <div class="sim-header">
                <div class="sim-brand">
                    <div class="sim-avatar-wrap">
                        <div class="sim-avatar">🤖</div>
                        <span class="sim-online-dot"></span>
                    </div>
                    <div class="sim-titles">
                        <h3>
                            <span>TechPanda Bot</span>
                            <svg viewBox="0 0 24 24" width="13" height="13" fill="#00a884" title="Verified Business"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
                        </h3>
                        <span class="sim-status">online &bull; automation active</span>
                    </div>
                </div>
                <div class="sim-header-actions">
                    <button class="sim-btn-restart" id="btnRestartSimulation" title="Restart Simulator">
                        <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5">
                            <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/>
                        </svg>
                        <span>Reset</span>
                    </button>
                    <button class="sim-btn-close" id="btnCloseSimulator" title="Close Simulator">
                        """ + SVG_CLOSE + """
                    </button>
                </div>
            </div>

            <!-- Simulator Chat Screen with WhatsApp Wallpaper -->
            <div class="sim-screen">
                <!-- End-to-End Encryption Notice -->
                <div class="sim-security-notice">
                    <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z"/></svg>
                    <span>Messages and calls are end-to-end encrypted. No one outside of this chat can read or listen to them.</span>
                </div>
                <div class="sim-date-pill">TODAY</div>

                <div class="sim-messages" id="simMessages">
                    <!-- Populated dynamically during test -->
                </div>

                <!-- Simulation Interactive List Bottom Sheet -->
                <div class="sim-list-sheet" id="simListSheet">
                    <div class="sim-sheet-header">
                        <h4 id="simSheetTitle">Select Option</h4>
                        <button type="button" class="sim-sheet-close" id="btnCloseSimSheet" title="Close">
                            """ + SVG_CLOSE + """
                        </button>
                    </div>
                    <div class="sim-sheet-items" id="simSheetItems"></div>
                </div>
            </div>

            <!-- Simulator Input Footer -->
            <form class="sim-footer" id="simChatForm">
                <div class="sim-input-box">
                    <input type="text" id="simChatInput" placeholder="Type a test message..." autocomplete="off">
                </div>
                <button type="submit" id="btnSimSend" title="Send Message">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                        <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                    </svg>
                </button>
            </form>"""
    fb_content = fb_content[:old_sim_snippet.start()] + new_sim_markup + fb_content[old_sim_snippet.end():]

with open(fb_path, 'w', encoding='utf-8') as f:
    f.write(fb_content)
print("Updated flow_builder.html successfully!")


# -------------------------------------------------------------
# 3. Update CRM/chat/static/chat/js/flow_builder.js
# -------------------------------------------------------------
js_path = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/chat/static/chat/js/flow_builder.js'
with open(js_path, 'r', encoding='utf-8') as f:
    js_content = f.read()

# Enhance addSimUserBubble with double blue checkmarks
old_user_bubble = """    function addSimUserBubble(text) {
        const bubble = document.createElement('div');
        bubble.className = 'sim-bubble sim-bubble-user';
        bubble.innerHTML = `
            <div>${escapeHtml(text)}</div>
            <div class="sim-bubble-time">${getCurrentTime()}</div>
        `;
        elements.simMessages.appendChild(bubble);
        scrollSimToBottom();
    }"""

new_user_bubble = """    function addSimUserBubble(text) {
        const bubble = document.createElement('div');
        bubble.className = 'sim-bubble sim-bubble-user';
        bubble.innerHTML = `
            <div>${escapeHtml(text)}</div>
            <div class="sim-bubble-meta">
                <span class="sim-bubble-time">${getCurrentTime()}</span>
                <span class="sim-double-tick" title="Read">
                    <svg viewBox="0 0 16 15" width="15" height="14" fill="none">
                        <path d="M15.01 3.316l-7.79 7.789a.5.5 0 01-.707 0L2.99 7.581a.5.5 0 11.707-.707l3.17 3.17 7.436-7.435a.5.5 0 11.707.707z" fill="#53bdeb"/>
                        <path d="M12.01 3.316l-7.79 7.789a.5.5 0 01-.707 0L.09 7.581a.5.5 0 11.707-.707l3.17 3.17 7.436-7.435a.5.5 0 11.707.707z" fill="#53bdeb"/>
                    </svg>
                </span>
            </div>
        `;
        elements.simMessages.appendChild(bubble);
        scrollSimToBottom();
    }"""

if old_user_bubble in js_content:
    js_content = js_content.replace(old_user_bubble, new_user_bubble)
    print("Replaced addSimUserBubble!")

# Enhance addSimBotButtons with WhatsApp reply arrow SVG
old_btns_loop = """        (node.options || []).forEach(opt => {
            btnsHtml += `<button type="button" class="sim-btn-choice" data-id="${opt.id}">${escapeHtml(opt.title)}</button>`;
        });"""

new_btns_loop = """        (node.options || []).forEach(opt => {
            btnsHtml += `
            <button type="button" class="sim-btn-choice" data-id="${opt.id}">
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 10 4 15 9 20"></polyline><path d="M20 4v7a4 4 0 0 1-4 4H4"></path></svg>
                <span>${escapeHtml(opt.title)}</span>
            </button>`;
        });"""

if old_btns_loop in js_content:
    js_content = js_content.replace(old_btns_loop, new_btns_loop)
    print("Replaced addSimBotButtons!")

# Enhance addSimBotList button with SVG icon
old_list_btn = """            <button type="button" class="sim-list-btn">
                <span>📋</span>
                <span>${escapeHtml(node.button_text || 'View Courses')}</span>
            </button>"""

new_list_btn = """            <button type="button" class="sim-list-btn">
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>
                <span>${escapeHtml(node.button_text || 'View Options')}</span>
            </button>"""

if old_list_btn in js_content:
    js_content = js_content.replace(old_list_btn, new_list_btn)
    print("Replaced addSimBotList!")

with open(js_path, 'w', encoding='utf-8') as f:
    f.write(js_content)
print("Updated flow_builder.js successfully!")
