/**
 * WhatsApp CRM Inbox - Vanilla JavaScript Application
 * Production-ready handling of Conversations, Chat messages, WebSockets, and UI interactions.
 */

(function () {
    'use strict';

    // Application State
    const state = {
        businessAccounts: [],
        selectedBusinessAccountId: null,
        conversations: [],
        activeConversationId: null,
        activeFilter: 'all', // 'all' | 'unread'
        searchQuery: '',
        activeChatSocket: null,
        inboxSocket: null,
        selectedFile: null,
        isSubmitting: false,
    };

    // DOM Element References
    const elements = {
        appContainer: document.getElementById('appContainer'),
        sidebarBackdrop: document.getElementById('sidebarBackdrop'),
        // Conversations Panel
        conversationsPanel: document.getElementById('conversationsPanel'),
        btnCollapseSidebar: document.getElementById('btnCollapseSidebar'),
        businessAccountSelect: document.getElementById('businessAccountSelect'),
        conversationsList: document.getElementById('conversationsList'),
        conversationsLoading: document.getElementById('conversationsLoading'),
        conversationsEmpty: document.getElementById('conversationsEmpty'),
        conversationsNotFound: document.getElementById('conversationsNotFound'),
        conversationSearchInput: document.getElementById('conversationSearchInput'),
        searchClearBtn: document.getElementById('searchClearBtn'),
        tabFilterAll: document.getElementById('tabFilterAll'),
        tabFilterUnread: document.getElementById('tabFilterUnread'),
        totalUnreadBadge: document.getElementById('totalUnreadBadge'),
        btnRefreshConversations: document.getElementById('btnRefreshConversations'),
        btnNewChat: document.getElementById('btnNewChat'),

        // Chat Panel
        chatPanel: document.getElementById('chatPanel'),
        chatPlaceholder: document.getElementById('chatPlaceholder'),
        btnOpenSidebarEmpty: document.getElementById('btnOpenSidebarEmpty'),
        chatInterface: document.getElementById('chatInterface'),
        btnToggleSidebar: document.getElementById('btnToggleSidebar'),
        btnBackToConversations: document.getElementById('btnBackToConversations'),
        activeAvatar: document.getElementById('activeAvatar'),
        activeOnlineDot: document.getElementById('activeOnlineDot'),
        activeCustomerName: document.getElementById('activeCustomerName'),
        activeCustomerStatus: document.getElementById('activeCustomerStatus'),
        btnHeaderSearch: document.getElementById('btnHeaderSearch'),
        chatSearchBar: document.getElementById('chatSearchBar'),
        chatSearchInput: document.getElementById('chatSearchInput'),
        chatSearchCount: document.getElementById('chatSearchCount'),
        btnChatSearchClose: document.getElementById('btnChatSearchClose'),
        btnChatMenu: document.getElementById('btnChatMenu'),
        chatMenuDropdown: document.getElementById('chatMenuDropdown'),
        menuItemMarkUnread: document.getElementById('menuItemMarkUnread'),
        menuItemCopyNumber: document.getElementById('menuItemCopyNumber'),
        menuItemClearChat: document.getElementById('menuItemClearChat'),

        // Messages Flow
        chatMessagesContainer: document.getElementById('chatMessagesContainer'),
        messagesFlow: document.getElementById('messagesFlow'),
        messagesLoading: document.getElementById('messagesLoading'),
        messagesEndAnchor: document.getElementById('messagesEndAnchor'),

        // Composer
        composerForm: document.getElementById('composerForm'),
        messageTextInput: document.getElementById('messageTextInput'),
        btnSendMessage: document.getElementById('btnSendMessage'),
        btnAttachment: document.getElementById('btnAttachment'),
        attachmentPopup: document.getElementById('attachmentPopup'),
        mediaFileInput: document.getElementById('mediaFileInput'),
        attachedFilePreview: document.getElementById('attachedFilePreview'),
        attachedFileName: document.getElementById('attachedFileName'),
        removeAttachmentBtn: document.getElementById('removeAttachmentBtn'),
        btnMicrophone: document.getElementById('btnMicrophone'),

        // Toast
        toastNotification: document.getElementById('toastNotification'),
        toastMessage: document.getElementById('toastMessage'),
        toastClose: document.getElementById('toastClose'),

        // Modal
        newChatModal: document.getElementById('newChatModal'),
        newChatForm: document.getElementById('newChatForm'),
        newChatModalClose: document.getElementById('newChatModalClose'),
        newChatModalCancel: document.getElementById('newChatModalCancel'),
        newCustomerName: document.getElementById('newCustomerName'),
        newPhoneNumber: document.getElementById('newPhoneNumber'),
        newInitialMessage: document.getElementById('newInitialMessage'),

        // Add Business Modal
        btnAddBusinessLine: document.getElementById('btnAddBusinessLine'),
        addBusinessModal: document.getElementById('addBusinessModal'),
        addBusinessForm: document.getElementById('addBusinessForm'),
        addBusinessModalClose: document.getElementById('addBusinessModalClose'),
        addBusinessModalCancel: document.getElementById('addBusinessModalCancel'),
        bizName: document.getElementById('bizName'),
        bizPhoneNumber: document.getElementById('bizPhoneNumber'),
        bizPhoneNumberId: document.getElementById('bizPhoneNumberId'),
        bizAccountId: document.getElementById('bizAccountId'),
        bizAccessToken: document.getElementById('bizAccessToken'),
        btnDeleteBusinessLine: document.getElementById('btnDeleteBusinessLine'),

        // Automation & Handover Controls
        btnToggleAutomation: document.getElementById('btnToggleAutomation'),
        automationToggleDot: document.getElementById('automationToggleDot'),
        automationToggleText: document.getElementById('automationToggleText'),
        handoverPillWrap: document.getElementById('handoverPillWrap'),
        btnResumeBot: document.getElementById('btnResumeBot'),
    };

    /* ==========================================================================
       Utility Helpers
       ========================================================================== */

    function getInitials(name) {
        if (!name) return 'WA';
        const parts = name.trim().split(/\s+/);
        if (parts.length >= 2) {
            return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
        }
        return name.slice(0, 2).toUpperCase();
    }

    function escapeHtml(text) {
        if (!text) return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;',
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }

    function showToast(message, duration = 4000) {
        elements.toastMessage.textContent = message;
        elements.toastNotification.classList.add('show');
        if (window._toastTimer) clearTimeout(window._toastTimer);
        window._toastTimer = setTimeout(() => {
            elements.toastNotification.classList.remove('show');
        }, duration);
    }

    function renderStatusTicks(status) {
        if (status === 'read') {
            // WhatsApp Double Blue Tick
            return `<span class="status-tick read" title="Read" aria-label="Read">
                <svg viewBox="0 0 16 11" width="16" height="11" fill="none">
                    <path d="M11.07 0.93a.75.75 0 0 0-1.06 0L5.75 5.19 4.3 3.74a.75.75 0 0 0-1.06 1.06l2 2a.75.75 0 0 0 1.06 0l4.77-4.81a.75.75 0 0 0 0-1.06z" fill="#53bdeb"/>
                    <path d="M15.07 0.93a.75.75 0 0 0-1.06 0L9.75 5.19l-.53-.53a.75.75 0 0 0-1.06 1.06l1.06 1.06a.75.75 0 0 0 1.06 0l4.79-4.79a.75.75 0 0 0 0-1.06z" fill="#53bdeb"/>
                </svg>
            </span>`;
        }
        if (status === 'delivered') {
            // WhatsApp Double Grey Tick
            return `<span class="status-tick delivered" title="Delivered" aria-label="Delivered">
                <svg viewBox="0 0 16 11" width="16" height="11" fill="none">
                    <path d="M11.07 0.93a.75.75 0 0 0-1.06 0L5.75 5.19 4.3 3.74a.75.75 0 0 0-1.06 1.06l2 2a.75.75 0 0 0 1.06 0l4.77-4.81a.75.75 0 0 0 0-1.06z" fill="#8696a0"/>
                    <path d="M15.07 0.93a.75.75 0 0 0-1.06 0L9.75 5.19l-.53-.53a.75.75 0 0 0-1.06 1.06l1.06 1.06a.75.75 0 0 0 1.06 0l4.79-4.79a.75.75 0 0 0 0-1.06z" fill="#8696a0"/>
                </svg>
            </span>`;
        }
        if (status === 'failed') {
            return `<span class="status-tick failed" title="Failed" aria-label="Failed">
                <svg viewBox="0 0 12 12" width="12" height="12" fill="none">
                    <circle cx="6" cy="6" r="5" fill="#ea4335"/>
                    <path d="M6 3v3.5M6 8.5v.5" stroke="#fff" stroke-width="1.3" stroke-linecap="round"/>
                </svg>
            </span>`;
        }
        // Single Grey Tick (Sent)
        return `<span class="status-tick sent" title="Sent" aria-label="Sent">
            <svg viewBox="0 0 12 11" width="12" height="11" fill="none">
                <path d="M11.07 0.93a.75.75 0 0 0-1.06 0L4.75 6.19 1.8 3.24a.75.75 0 0 0-1.06 1.06l3.5 3.5a.75.75 0 0 0 1.06 0l5.77-5.81a.75.75 0 0 0 0-1.06z" fill="#8696a0"/>
            </svg>
        </span>`;
    }

    /* ==========================================================================
       Business Accounts: Multi-Number Management
       ========================================================================== */

    async function loadBusinessAccounts() {
        if (!window.CRM_CONFIG.api.businessAccounts) return;
        try {
            const response = await fetch(window.CRM_CONFIG.api.businessAccounts);
            if (!response.ok) throw new Error(`HTTP error ${response.status}`);
            const accounts = await response.json();
            state.businessAccounts = accounts;
            renderBusinessAccountSelect();
        } catch (err) {
            console.error('Failed to load business accounts:', err);
        }
    }

    function renderBusinessAccountSelect() {
        if (!elements.businessAccountSelect) return;
        elements.businessAccountSelect.innerHTML = '';

        if (!state.businessAccounts || state.businessAccounts.length === 0) {
            const opt = document.createElement('option');
            opt.value = '';
            opt.textContent = 'Default WhatsApp Line';
            elements.businessAccountSelect.appendChild(opt);
            return;
        }

        state.businessAccounts.forEach((acc, index) => {
            const opt = document.createElement('option');
            opt.value = acc.id;
            const unreadStr = acc.unread_count > 0 ? ` (${acc.unread_count} unread)` : '';
            opt.textContent = `📱 ${acc.name} ${acc.phone_number ? `(${acc.phone_number})` : ''}${unreadStr}`;
            elements.businessAccountSelect.appendChild(opt);

            // Select default account
            if (!state.selectedBusinessAccountId) {
                if (acc.is_default || index === 0) {
                    state.selectedBusinessAccountId = acc.id;
                }
            }
        });

        if (state.selectedBusinessAccountId) {
            elements.businessAccountSelect.value = state.selectedBusinessAccountId;
            const currentAcc = state.businessAccounts.find(a => a.id === state.selectedBusinessAccountId);
            updateAutomationToggleUI(currentAcc ? currentAcc.automation_enabled : true);
        }
    }

    function updateAutomationToggleUI(enabled) {
        if (!elements.btnToggleAutomation) return;
        if (enabled) {
            elements.btnToggleAutomation.classList.remove('disabled');
            if (elements.automationToggleText) elements.automationToggleText.textContent = 'Bot: ON';
        } else {
            elements.btnToggleAutomation.classList.add('disabled');
            if (elements.automationToggleText) elements.automationToggleText.textContent = 'Bot: OFF';
        }
    }

    async function toggleAutomationForSelectedAccount() {
        if (!state.selectedBusinessAccountId) {
            showToast('No business line selected.');
            return;
        }
        const acc = state.businessAccounts.find(a => a.id === state.selectedBusinessAccountId);
        if (!acc) return;
        const newStatus = !acc.automation_enabled;
        try {
            const resp = await fetch(`/api/business-accounts/${acc.id}/`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.CRM_CONFIG.csrfToken,
                },
                body: JSON.stringify({ automation_enabled: newStatus })
            });
            if (resp.ok) {
                acc.automation_enabled = newStatus;
                updateAutomationToggleUI(newStatus);
                showToast(`Bot Automation is now ${newStatus ? 'ENABLED' : 'DISABLED'} for ${acc.name}.`);
            }
        } catch (err) {
            console.error('Toggle automation error:', err);
            showToast('Failed to update automation state.');
        }
    }

    function updateHandoverPill(status) {
        if (!elements.handoverPillWrap) return;
        if (status === 'handed_over') {
            elements.handoverPillWrap.style.display = 'flex';
        } else {
            elements.handoverPillWrap.style.display = 'none';
        }
    }

    async function resumeBotAutomation() {
        if (!state.activeConversationId) return;
        try {
            const resp = await fetch(`/api/conversations/${state.activeConversationId}/resume-automation/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.CRM_CONFIG.csrfToken,
                }
            });
            if (resp.ok) {
                updateHandoverPill('active');
                const conv = state.conversations.find(c => c.id === state.activeConversationId);
                if (conv) conv.automation_status = 'active';
                showToast('🤖 Bot automation resumed for this conversation.');
            }
        } catch (err) {
            console.error('Error resuming automation:', err);
            showToast('Failed to resume automation.');
        }
    }

    /* ==========================================================================
       Conversations: Fetching & Rendering
       ========================================================================== */

    async function loadConversations(autoSelectFirst = false) {
        elements.conversationsLoading.style.display = 'flex';
        elements.conversationsEmpty.style.display = 'none';
        elements.conversationsNotFound.style.display = 'none';

        const params = new URLSearchParams();
        if (state.selectedBusinessAccountId) {
            params.append('business_account_id', state.selectedBusinessAccountId);
        }

        let url = window.CRM_CONFIG.api.conversations;
        if (state.searchQuery.trim()) {
            params.append('q', state.searchQuery.trim());
            url = `${window.CRM_CONFIG.api.search}?${params.toString()}`;
        } else {
            if (state.activeFilter === 'unread') {
                params.append('filter', 'unread');
            }
            url = `${window.CRM_CONFIG.api.conversations}?${params.toString()}`;
        }

        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error ${response.status}`);
            }
            const data = await response.json();
            state.conversations = data;
            renderConversationsList();

            // Auto-select first conversation on desktop if nothing selected
            if (autoSelectFirst && window.innerWidth > 768 && state.conversations.length > 0 && !state.activeConversationId) {
                selectConversation(state.conversations[0].id);
            }
        } catch (err) {
            console.error('Failed to load conversations:', err);
            showToast('Unable to load conversations. Please try again.');
        } finally {
            elements.conversationsLoading.style.display = 'none';
        }
    }

    function renderConversationsList() {
        elements.conversationsList.innerHTML = '';

        // Filter list based on filter tab & search query
        let filtered = state.conversations;
        if (state.activeFilter === 'unread' && !state.searchQuery) {
            filtered = filtered.filter(c => c.unread_count > 0);
        }

        // Update unread count indicator badge
        const totalUnread = state.conversations.reduce((sum, c) => sum + (c.unread_count || 0), 0);
        if (totalUnread > 0) {
            elements.totalUnreadBadge.textContent = totalUnread;
            elements.totalUnreadBadge.style.display = 'inline-block';
        } else {
            elements.totalUnreadBadge.style.display = 'none';
        }

        if (filtered.length === 0) {
            if (state.searchQuery) {
                elements.conversationsNotFound.style.display = 'flex';
            } else {
                elements.conversationsEmpty.style.display = 'flex';
            }
            return;
        }

        elements.conversationsEmpty.style.display = 'none';
        elements.conversationsNotFound.style.display = 'none';

        filtered.forEach(conv => {
            const li = document.createElement('li');
            li.className = `conversation-item ${conv.id === state.activeConversationId ? 'active' : ''} ${conv.unread_count > 0 ? 'has-unread' : ''}`;
            li.dataset.id = conv.id;

            const initials = getInitials(conv.customer_name);
            const avatarHtml = conv.profile_image_url
                ? `<img src="${conv.profile_image_url}" alt="${escapeHtml(conv.customer_name)}">`
                : initials;

            const previewText = escapeHtml(conv.last_message || 'Start a conversation');
            const formattedTime = conv.last_message_time || '';

            li.innerHTML = `
                <div class="conv-avatar-wrap ${conv.is_online ? 'is-online' : ''}">
                    <div class="conv-avatar">${avatarHtml}</div>
                    <span class="conv-online-dot"></span>
                </div>
                <div class="conv-content">
                    <div class="conv-top-row">
                        <span class="conv-name">${escapeHtml(conv.customer_name)}</span>
                        <span class="conv-time">${escapeHtml(formattedTime)}</span>
                    </div>
                    <div class="conv-bottom-row">
                        <span class="conv-preview">${previewText}</span>
                        <div class="conv-badges">
                            ${conv.is_pinned ? '<span class="pin-indicator" title="Pinned">📌</span>' : ''}
                            ${conv.unread_count > 0 ? `<span class="unread-badge">${conv.unread_count}</span>` : ''}
                        </div>
                    </div>
                </div>
            `;

            li.addEventListener('click', () => {
                selectConversation(conv.id);
            });

            elements.conversationsList.appendChild(li);
        });
    }

    /* ==========================================================================
       Active Conversation Selection & Messages
       ========================================================================== */

    async function selectConversation(conversationId) {
        state.activeConversationId = conversationId;

        // On mobile, transition view to chat panel and close drawer
        elements.appContainer.classList.add('mobile-chat-open');
        elements.appContainer.classList.remove('sidebar-mobile-open');

        // Highlight active item in list
        document.querySelectorAll('.conversation-item').forEach(item => {
            if (parseInt(item.dataset.id, 10) === conversationId) {
                item.classList.add('active');
                item.classList.remove('has-unread');
                const badge = item.querySelector('.unread-badge');
                if (badge) badge.remove();
            } else {
                item.classList.remove('active');
            }
        });

        // Find conversation details
        const conv = state.conversations.find(c => c.id === conversationId);
        if (conv) {
            conv.unread_count = 0;
            // Update active header
            elements.activeCustomerName.textContent = conv.customer_name;
            elements.activeCustomerStatus.textContent = conv.is_online ? 'online' : (conv.last_seen || 'offline');
            elements.activeAvatar.textContent = getInitials(conv.customer_name);
            if (conv.is_online) {
                elements.activeOnlineDot.parentElement.classList.add('is-online');
            } else {
                elements.activeOnlineDot.parentElement.classList.remove('is-online');
            }
            updateHandoverPill(conv.automation_status);
        }

        // Show chat interface, hide placeholder
        elements.chatPlaceholder.style.display = 'none';
        elements.chatInterface.style.display = 'flex';

        // Connect room WebSocket
        setupChatWebSocket(conversationId);

        // Fetch messages
        await loadMessages(conversationId);

        // Focus composer input
        elements.messageTextInput.focus();
    }

    async function loadMessages(conversationId) {
        elements.messagesLoading.style.display = 'flex';
        elements.messagesFlow.innerHTML = '';

        try {
            const response = await fetch(`/api/conversations/${conversationId}/messages/`);
            if (!response.ok) {
                throw new Error(`HTTP error ${response.status}`);
            }
            const messages = await response.json();
            renderMessages(messages);
            scrollToBottom(false);
        } catch (err) {
            console.error('Error loading messages:', err);
            showToast('Unable to load message history.');
        } finally {
            elements.messagesLoading.style.display = 'none';
        }
    }

    function renderMessages(messages) {
        elements.messagesFlow.innerHTML = '';
        if (!messages || messages.length === 0) {
            const emptyDivider = document.createElement('div');
            emptyDivider.className = 'date-divider';
            emptyDivider.textContent = 'Conversation Started';
            elements.messagesFlow.appendChild(emptyDivider);
            return;
        }

        // Add initial date divider
        const divider = document.createElement('div');
        divider.className = 'date-divider';
        divider.textContent = 'Today';
        elements.messagesFlow.appendChild(divider);

        messages.forEach(msg => {
            appendMessageBubble(msg);
        });
    }

    function appendMessageBubble(msg) {
        const row = document.createElement('div');
        const isOutgoing = msg.sender === 'agent';
        row.className = `message-row ${isOutgoing ? 'outgoing' : 'incoming'}`;
        row.dataset.msgId = msg.id;

        let contentHtml = '';

        // Media rendering
        if (msg.message_type === 'image' && msg.media_url) {
            contentHtml += `
                <div class="message-media-wrap">
                    <img src="${msg.media_url}" alt="Image" loading="lazy">
                </div>
            `;
        } else if (msg.message_type === 'audio' && msg.media_url) {
            contentHtml += `
                <div class="message-audio-player" data-audio-src="${escapeHtml(msg.media_url)}">
                    <button type="button" class="audio-play-btn" aria-label="Play audio" onclick="toggleAudioPlayback(this)">
                        <svg class="icon-play" viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><polygon points="6 4 20 12 6 20 6 4"></polygon></svg>
                        <svg class="icon-pause" viewBox="0 0 24 24" width="16" height="16" fill="currentColor" style="display:none;"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>
                    </button>
                    <div class="audio-waveform-bars">
                        <span class="waveform-bar" style="height: 8px;"></span>
                        <span class="waveform-bar" style="height: 14px;"></span>
                        <span class="waveform-bar" style="height: 20px;"></span>
                        <span class="waveform-bar" style="height: 10px;"></span>
                        <span class="waveform-bar" style="height: 16px;"></span>
                        <span class="waveform-bar" style="height: 22px;"></span>
                        <span class="waveform-bar" style="height: 12px;"></span>
                        <span class="waveform-bar" style="height: 18px;"></span>
                        <span class="waveform-bar" style="height: 8px;"></span>
                        <span class="waveform-bar" style="height: 15px;"></span>
                    </div>
                    <span class="audio-time-label">Voice</span>
                    <audio src="${escapeHtml(msg.media_url)}" preload="metadata" onended="onAudioEnded(this)"></audio>
                </div>
            `;
        } else if (msg.message_type === 'document' && msg.media_url) {
            const filename = msg.media_filename || 'Document';
            contentHtml += `
                <a href="${msg.media_url}" target="_blank" download class="message-doc-card">
                    <span class="doc-icon-badge">📄</span>
                    <div class="doc-info">
                        <span class="doc-name">${escapeHtml(filename)}</span>
                        <span class="doc-action">Click to download</span>
                    </div>
                </a>
            `;
        }

        // Text rendering
        if (msg.message_text) {
            contentHtml += `<div class="message-text">${escapeHtml(msg.message_text)}</div>`;
        }

        // Metadata: time + status ticks
        const statusHtml = isOutgoing ? renderStatusTicks(msg.status) : '';
        const metaHtml = `
            <div class="message-meta">
                <span class="message-time">${escapeHtml(msg.display_time || '')}</span>
                ${statusHtml}
            </div>
        `;

        row.innerHTML = `
            <div class="message-bubble">
                ${contentHtml}
                ${metaHtml}
            </div>
        `;

        elements.messagesFlow.appendChild(row);
    }

    function scrollToBottom(smooth = true) {
        requestAnimationFrame(() => {
            elements.chatMessagesContainer.scrollTop = elements.chatMessagesContainer.scrollHeight;
            if (elements.messagesEndAnchor) {
                elements.messagesEndAnchor.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'end' });
            }
        });
    }

    /* ==========================================================================
       Message Composer: Send Outbound Message
       ========================================================================== */

    async function handleSendMessage(e) {
        if (e) e.preventDefault();
        if (state.isSubmitting) return;

        const text = elements.messageTextInput.value.trim();
        const file = state.selectedFile;

        if (!text && !file) return;
        if (!state.activeConversationId) return;

        state.isSubmitting = true;
        elements.btnSendMessage.disabled = true;

        const formData = new FormData();
        formData.append('conversation_id', state.activeConversationId);
        if (state.selectedBusinessAccountId) {
            formData.append('business_account_id', state.selectedBusinessAccountId);
        }
        formData.append('message_text', text);

        if (file) {
            let msgType = 'document';
            if (file.type.startsWith('image/')) msgType = 'image';
            else if (file.type.startsWith('video/')) msgType = 'video';
            else if (file.type.startsWith('audio/')) msgType = 'audio';
            formData.append('message_type', msgType);
            formData.append('media_file', file);
        } else {
            formData.append('message_type', 'text');
        }

        try {
            const response = await fetch(window.CRM_CONFIG.api.sendMessage, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': window.CRM_CONFIG.csrfToken,
                },
                body: formData,
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || 'Failed to send');
            }

            const sentMessage = await response.json();

            // Clear input
            elements.messageTextInput.value = '';
            clearAttachment();
            autoResizeTextarea();
            elements.messageTextInput.focus();

            // Append bubble if not already received via websocket
            const existing = document.querySelector(`[data-msg-id="${sentMessage.id}"]`);
            if (!existing) {
                appendMessageBubble(sentMessage);
                scrollToBottom(true);
            }

            if (sentMessage.whatsapp_error) {
                showToast(`Meta WhatsApp API Notice: ${sentMessage.whatsapp_error}`);
            }

            // Update conversation in list
            updateConversationPreview(state.activeConversationId, sentMessage.message_text || '[Media]', sentMessage.display_time);

            // Agent manually sent message -> conversation is handed over to human
            const currentConv = state.conversations.find(c => c.id === state.activeConversationId);
            if (currentConv) {
                currentConv.automation_status = 'handed_over';
            }
            updateHandoverPill('handed_over');

        } catch (err) {
            console.error('Send message error:', err);
            showToast("Message couldn't be sent. Try again.");
        } finally {
            state.isSubmitting = false;
            updateSendButtonState();
        }
    }

    function updateConversationPreview(conversationId, lastMessage, lastMessageTime) {
        const conv = state.conversations.find(c => c.id === conversationId);
        if (conv) {
            conv.last_message = lastMessage;
            conv.last_message_time = lastMessageTime;
            // Move conversation to top
            state.conversations = [conv, ...state.conversations.filter(c => c.id !== conversationId)];
            renderConversationsList();
        }
    }

    function updateSendButtonState() {
        const hasText = elements.messageTextInput.value.trim().length > 0;
        const hasFile = state.selectedFile !== null;
        elements.btnSendMessage.disabled = !(hasText || hasFile) || state.isSubmitting;
    }

    function autoResizeTextarea() {
        const textarea = elements.messageTextInput;
        textarea.style.height = 'auto';
        textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
    }

    function setAttachment(file) {
        state.selectedFile = file;
        elements.attachedFileName.textContent = file.name;
        elements.attachedFilePreview.style.display = 'inline-flex';
        elements.attachmentPopup.style.display = 'none';
        updateSendButtonState();
    }

    function clearAttachment() {
        state.selectedFile = null;
        elements.mediaFileInput.value = '';
        elements.attachedFilePreview.style.display = 'none';
        updateSendButtonState();
    }

    /* ==========================================================================
       Real-Time WebSocket Integration
       ========================================================================== */

    function setupChatWebSocket(conversationId) {
        if (state.activeChatSocket) {
            state.activeChatSocket.close();
            state.activeChatSocket = null;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const socketUrl = `${protocol}//${window.location.host}/ws/chat/${conversationId}/`;

        try {
            const socket = new WebSocket(socketUrl);

            socket.onmessage = function (event) {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'message' && data.message) {
                        const msg = data.message;
                        if (msg.conversation_id === state.activeConversationId) {
                            const existing = document.querySelector(`[data-msg-id="${msg.id}"]`);
                            if (!existing) {
                                appendMessageBubble(msg);
                                scrollToBottom(true);
                            }
                        }
                    } else if (data.type === 'status_update') {
                        // Update status ticks
                        const row = document.querySelector(`[data-msg-id="${data.message_id}"]`);
                        if (row) {
                            const meta = row.querySelector('.message-meta');
                            if (meta) {
                                const tick = meta.querySelector('.status-tick');
                                if (tick) {
                                    tick.outerHTML = renderStatusTicks(data.status);
                                }
                            }
                        }
                    }
                } catch (e) {
                    console.error('Socket message parse error:', e);
                }
            };

            socket.onerror = function () {
                console.warn('Chat WebSocket error. Falling back to HTTP.');
            };

            state.activeChatSocket = socket;
        } catch (e) {
            console.warn('WebSocket connection not initialized:', e);
        }
    }

    function setupInboxWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const socketUrl = `${protocol}//${window.location.host}/ws/inbox/`;

        try {
            const socket = new WebSocket(socketUrl);

            socket.onmessage = function (event) {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'conversation_update' && data.conversation) {
                        const updated = data.conversation;

                        // Only update if it belongs to selected business account (or all)
                        if (!state.selectedBusinessAccountId || !updated.business_account_id || updated.business_account_id === state.selectedBusinessAccountId) {
                            const existing = state.conversations.find(c => c.id === updated.id);

                            if (existing) {
                                existing.last_message = updated.last_message;
                                existing.last_message_time = updated.last_message_time;
                                if (updated.id !== state.activeConversationId) {
                                    existing.unread_count = updated.unread_count;
                                }
                                // Move to top
                                state.conversations = [existing, ...state.conversations.filter(c => c.id !== updated.id)];
                            } else {
                                state.conversations.unshift(updated);
                            }
                            renderConversationsList();
                        }
                    }
                } catch (e) {
                    console.error('Inbox socket parse error:', e);
                }
            };

            socket.onclose = function () {
                // Reconnect after 5 seconds
                setTimeout(setupInboxWebSocket, 5000);
            };

            state.inboxSocket = socket;
        } catch (e) {
            console.warn('Inbox WebSocket not initialized:', e);
        }
    }

    function jsonParse(str) {
        try {
            return JSON.parse(str);
        } catch (e) {
            return {};
        }
    }

    /* ==========================================================================
       Event Listeners & UI Wiring
       ========================================================================== */

    function initEventListeners() {
        // Textarea typing & auto-resize
        elements.messageTextInput.addEventListener('input', () => {
            autoResizeTextarea();
            updateSendButtonState();
        });

        // Enter to send, Shift+Enter for new line
        elements.messageTextInput.addEventListener('keydown', (e) => {
            if ((e.key === 'Enter' || e.keyCode === 13) && !e.shiftKey) {
                e.preventDefault();
                e.stopPropagation();
                handleSendMessage(e);
            }
        });

        // Send button click
        elements.composerForm.addEventListener('submit', handleSendMessage);

        // Attachment toggle
        elements.btnAttachment.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = elements.attachmentPopup.style.display === 'flex';
            elements.attachmentPopup.style.display = isOpen ? 'none' : 'flex';
        });

        document.addEventListener('click', () => {
            elements.attachmentPopup.style.display = 'none';
            elements.chatMenuDropdown.classList.remove('show');
        });

        // Attachment option click
        document.querySelectorAll('.attachment-option').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const type = btn.dataset.type;
                if (type === 'image') {
                    elements.mediaFileInput.accept = 'image/*,video/*';
                } else {
                    elements.mediaFileInput.accept = '.pdf,.doc,.docx,.txt,.csv';
                }
                elements.mediaFileInput.click();
            });
        });

        elements.mediaFileInput.addEventListener('change', () => {
            if (elements.mediaFileInput.files.length > 0) {
                setAttachment(elements.mediaFileInput.files[0]);
            }
        });

        elements.removeAttachmentBtn.addEventListener('click', clearAttachment);

        /* ==========================================================================
           Sliding Sidebar Drawer Logic & Event Handlers
           ========================================================================== */

        function isMobileView() {
            return window.innerWidth <= 768;
        }

        function toggleSidebar(forceState) {
            if (isMobileView()) {
                const willOpen = forceState !== undefined ? forceState : !elements.appContainer.classList.contains('sidebar-mobile-open');
                if (willOpen) {
                    elements.appContainer.classList.add('sidebar-mobile-open');
                } else {
                    elements.appContainer.classList.remove('sidebar-mobile-open');
                }
            } else {
                // Desktop / Tablet sliding bar
                const willCollapse = forceState !== undefined ? forceState : !elements.appContainer.classList.contains('sidebar-collapsed');
                if (willCollapse) {
                    elements.appContainer.classList.add('sidebar-collapsed');
                    localStorage.setItem('wa_sidebar_collapsed', 'true');
                } else {
                    elements.appContainer.classList.remove('sidebar-collapsed');
                    localStorage.setItem('wa_sidebar_collapsed', 'false');
                }
                updateSidebarToggleTooltips();
            }
        }

        function updateSidebarToggleTooltips() {
            const isCollapsed = elements.appContainer.classList.contains('sidebar-collapsed');
            if (elements.btnToggleSidebar) {
                elements.btnToggleSidebar.title = isCollapsed ? 'Expand conversations sidebar' : 'Collapse conversations sidebar';
            }
        }

        // Sidebar Collapse / Expand buttons
        if (elements.btnCollapseSidebar) {
            elements.btnCollapseSidebar.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleSidebar(true);
            });
        }

        if (elements.btnToggleSidebar) {
            elements.btnToggleSidebar.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleSidebar();
            });
        }

        if (elements.btnOpenSidebarEmpty) {
            elements.btnOpenSidebarEmpty.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleSidebar(false);
            });
        }

        // Mobile backdrop overlay click
        if (elements.sidebarBackdrop) {
            elements.sidebarBackdrop.addEventListener('click', () => {
                elements.appContainer.classList.remove('sidebar-mobile-open');
            });
        }

        // In-Chat Search Logic
        function toggleChatSearch() {
            if (!elements.chatSearchBar) return;
            const isHidden = elements.chatSearchBar.style.display === 'none';
            if (isHidden) {
                elements.chatSearchBar.style.display = 'block';
                if (elements.chatSearchInput) {
                    elements.chatSearchInput.focus();
                    elements.chatSearchInput.select();
                }
            } else {
                closeChatSearch();
            }
        }

        function closeChatSearch() {
            if (!elements.chatSearchBar) return;
            elements.chatSearchBar.style.display = 'none';
            if (elements.chatSearchInput) elements.chatSearchInput.value = '';
            if (elements.chatSearchCount) elements.chatSearchCount.style.display = 'none';
            const rows = elements.messagesFlow.querySelectorAll('.message-row');
            rows.forEach(r => {
                r.style.display = '';
                const bubble = r.querySelector('.message-bubble');
                if (bubble) bubble.style.boxShadow = '';
            });
        }

        function filterChatMessages(query) {
            query = (query || '').toLowerCase().trim();
            const rows = elements.messagesFlow.querySelectorAll('.message-row');
            if (!query) {
                rows.forEach(r => {
                    r.style.display = '';
                    const bubble = r.querySelector('.message-bubble');
                    if (bubble) bubble.style.boxShadow = '';
                });
                if (elements.chatSearchCount) elements.chatSearchCount.style.display = 'none';
                return;
            }

            let matches = 0;
            let firstMatch = null;
            rows.forEach(row => {
                const textEl = row.querySelector('.message-text');
                const text = (textEl ? textEl.textContent : '').toLowerCase();
                if (text.includes(query)) {
                    row.style.display = '';
                    matches++;
                    if (!firstMatch) firstMatch = row;
                    const bubble = row.querySelector('.message-bubble');
                    if (bubble) bubble.style.boxShadow = '0 0 0 2px var(--accent-primary)';
                } else {
                    row.style.display = 'none';
                    const bubble = row.querySelector('.message-bubble');
                    if (bubble) bubble.style.boxShadow = '';
                }
            });

            if (elements.chatSearchCount) {
                elements.chatSearchCount.textContent = `${matches} match${matches === 1 ? '' : 'es'}`;
                elements.chatSearchCount.style.display = 'inline-block';
            }

            if (firstMatch) {
                firstMatch.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }

        if (elements.btnHeaderSearch) {
            elements.btnHeaderSearch.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleChatSearch();
            });
        }

        if (elements.btnChatSearchClose) {
            elements.btnChatSearchClose.addEventListener('click', closeChatSearch);
        }

        if (elements.chatSearchInput) {
            elements.chatSearchInput.addEventListener('input', (e) => {
                filterChatMessages(e.target.value);
            });
        }

        // Microphone UI interaction with active feedback
        let isRecording = false;
        elements.btnMicrophone.addEventListener('click', () => {
            isRecording = !isRecording;
            if (isRecording) {
                elements.btnMicrophone.classList.add('recording');
                showToast('🎙️ Recording voice note... Tap mic again to stop.');
            } else {
                elements.btnMicrophone.classList.remove('recording');
                showToast('🎙️ Voice note recorded. Ready to attach.');
            }
        });

        // Mobile back button
        elements.btnBackToConversations.addEventListener('click', () => {
            elements.appContainer.classList.remove('mobile-chat-open');
        });

        // Search input with debounce
        let searchTimeout = null;
        elements.conversationSearchInput.addEventListener('input', (e) => {
            const query = e.target.value;
            state.searchQuery = query;
            elements.searchClearBtn.style.display = query ? 'block' : 'none';

            if (searchTimeout) clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                loadConversations();
            }, 250);
        });

        elements.searchClearBtn.addEventListener('click', () => {
            elements.conversationSearchInput.value = '';
            state.searchQuery = '';
            elements.searchClearBtn.style.display = 'none';
            loadConversations();
        });

        // Filter tabs (All / Unread)
        elements.tabFilterAll.addEventListener('click', () => {
            state.activeFilter = 'all';
            elements.tabFilterAll.classList.add('active');
            elements.tabFilterUnread.classList.remove('active');
            renderConversationsList();
        });

        elements.tabFilterUnread.addEventListener('click', () => {
            state.activeFilter = 'unread';
            elements.tabFilterUnread.classList.add('active');
            elements.tabFilterAll.classList.remove('active');
            renderConversationsList();
        });

        // Refresh button with spinning animation feedback
        elements.btnRefreshConversations.addEventListener('click', async () => {
            elements.btnRefreshConversations.classList.add('spinning');
            try {
                await loadConversations();
                showToast('Conversations refreshed.');
            } finally {
                setTimeout(() => elements.btnRefreshConversations.classList.remove('spinning'), 600);
            }
        });

        // Chat Header Dropdown Menu
        elements.btnChatMenu.addEventListener('click', (e) => {
            e.stopPropagation();
            elements.chatMenuDropdown.classList.toggle('show');
        });

        elements.menuItemMarkUnread.addEventListener('click', () => {
            if (state.activeConversationId) {
                const conv = state.conversations.find(c => c.id === state.activeConversationId);
                if (conv) {
                    conv.unread_count = 1;
                    renderConversationsList();
                    showToast('Conversation marked as unread.');
                }
            }
            elements.chatMenuDropdown.classList.remove('show');
        });

        elements.menuItemCopyNumber.addEventListener('click', () => {
            if (state.activeConversationId) {
                const conv = state.conversations.find(c => c.id === state.activeConversationId);
                if (conv && conv.phone_number) {
                    navigator.clipboard.writeText(conv.phone_number);
                    showToast(`Copied ${conv.phone_number} to clipboard.`);
                }
            }
            elements.chatMenuDropdown.classList.remove('show');
        });

        elements.menuItemClearChat.addEventListener('click', () => {
            elements.messagesFlow.innerHTML = '';
            showToast('Chat messages cleared from current view.');
            elements.chatMenuDropdown.classList.remove('show');
        });

        // Global Keyboard Shortcuts (Escape to close modals, dropdown, search)
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                if (elements.newChatModal && elements.newChatModal.style.display === 'flex') {
                    elements.newChatModal.style.display = 'none';
                }
                if (elements.addBusinessModal && elements.addBusinessModal.style.display === 'flex') {
                    elements.addBusinessModal.style.display = 'none';
                }
                if (elements.chatMenuDropdown) {
                    elements.chatMenuDropdown.classList.remove('show');
                }
                if (elements.attachmentPopup) {
                    elements.attachmentPopup.style.display = 'none';
                }
                closeChatSearch();
            }
        });

        // Toast close
        elements.toastClose.addEventListener('click', () => {
            elements.toastNotification.classList.remove('show');
        });

        // New Chat Modal
        elements.btnNewChat.addEventListener('click', () => {
            elements.newChatModal.style.display = 'flex';
        });

        elements.newChatModalClose.addEventListener('click', () => {
            elements.newChatModal.style.display = 'none';
        });

        // Business Account Switcher change event
        if (elements.businessAccountSelect) {
            elements.businessAccountSelect.addEventListener('change', (e) => {
                const val = e.target.value;
                state.selectedBusinessAccountId = val ? parseInt(val, 10) : null;
                const acc = state.businessAccounts.find(a => a.id === state.selectedBusinessAccountId);
                updateAutomationToggleUI(acc ? acc.automation_enabled : true);

                // Deselect active chat if not in selected business line
                const currentConv = state.conversations.find(c => c.id === state.activeConversationId && c.business_account_id === state.selectedBusinessAccountId);
                if (!currentConv) {
                    state.activeConversationId = null;
                    elements.chatInterface.style.display = 'none';
                    elements.chatPlaceholder.style.display = 'flex';
                }
                loadConversations(true);
            });
        }

        // Toggle Automation for Selected Account
        if (elements.btnToggleAutomation) {
            elements.btnToggleAutomation.addEventListener('click', toggleAutomationForSelectedAccount);
        }

        // Resume Automation when Handed Over
        if (elements.btnResumeBot) {
            elements.btnResumeBot.addEventListener('click', resumeBotAutomation);
        }

        elements.newChatModalCancel.addEventListener('click', () => {
            elements.newChatModal.style.display = 'none';
        });

        elements.newChatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const name = elements.newCustomerName.value.trim();
            const phone = elements.newPhoneNumber.value.trim();
            const message = elements.newInitialMessage.value.trim();

            if (!name || !phone || !message) return;

            // Submit initial message via API or webhook
            try {
                // Check if conversation exists or create via sending message
                const response = await fetch(window.CRM_CONFIG.api.sendMessage, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': window.CRM_CONFIG.csrfToken,
                    },
                    body: JSON.stringify({
                        business_account_id: state.selectedBusinessAccountId,
                        customer_name: name,
                        phone_number: phone,
                        message_text: message,
                    }),
                });

                if (!response.ok) {
                    throw new Error('Failed to create conversation');
                }
                const sentMsg = await response.json();
                elements.newChatModal.style.display = 'none';
                elements.newChatForm.reset();
                await loadConversations(false);
                if (sentMsg.conversation_id) {
                    selectConversation(sentMsg.conversation_id);
                }
                showToast(`Started conversation with ${name}`);
            } catch (err) {
                console.error('Error starting conversation:', err);
                showToast('Unable to start conversation.');
            }
        });

        // Add Business Line Modal events
        if (elements.btnAddBusinessLine) {
            elements.btnAddBusinessLine.addEventListener('click', () => {
                elements.addBusinessModal.style.display = 'flex';
            });
        }

        if (elements.addBusinessModalClose) {
            elements.addBusinessModalClose.addEventListener('click', () => {
                elements.addBusinessModal.style.display = 'none';
            });
        }

        if (elements.addBusinessModalCancel) {
            elements.addBusinessModalCancel.addEventListener('click', () => {
                elements.addBusinessModal.style.display = 'none';
            });
        }

        if (elements.addBusinessForm) {
            elements.addBusinessForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const name = elements.bizName.value.trim();
                const phone = elements.bizPhoneNumber.value.trim();
                const phoneId = elements.bizPhoneNumberId.value.trim();
                const accountId = elements.bizAccountId.value.trim();
                const token = elements.bizAccessToken.value.trim();

                if (!name || !phone || !phoneId) {
                    showToast('Please fill all required fields.');
                    return;
                }

                try {
                    const response = await fetch(window.CRM_CONFIG.api.businessAccounts, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': window.CRM_CONFIG.csrfToken,
                        },
                        body: JSON.stringify({
                            name: name,
                            phone_number: phone,
                            phone_number_id: phoneId,
                            business_account_id: accountId,
                            access_token: token,
                            is_active: true
                        }),
                    });

                    if (!response.ok) {
                        const errData = await response.json().catch(() => ({}));
                        const errMsg = Object.values(errData).flat().join(' ') || 'Failed to add business account.';
                        throw new Error(errMsg);
                    }

                    const newAcc = await response.json();
                    elements.addBusinessModal.style.display = 'none';
                    elements.addBusinessForm.reset();
                    showToast(`Business Line "${name}" added successfully!`);

                    // Reload business accounts and switch to newly added line
                    state.selectedBusinessAccountId = newAcc.id;
                    await loadBusinessAccounts();
                    await loadConversations(true);
                } catch (err) {
                    console.error('Error adding business line:', err);
                    showToast(`Error: ${err.message || 'Could not save business line.'}`);
                }
            });
        }

        // Delete/Remove Selected Business Line
        if (elements.btnDeleteBusinessLine) {
            elements.btnDeleteBusinessLine.addEventListener('click', async () => {
                if (!state.selectedBusinessAccountId) {
                    showToast('No business line selected.');
                    return;
                }

                const currentAcc = (state.businessAccounts || []).find(a => a.id === state.selectedBusinessAccountId);
                const accName = currentAcc ? currentAcc.name : 'this business line';

                const confirmed = window.confirm(`Are you sure you want to remove "${accName}" and its conversations from this CRM?`);
                if (!confirmed) return;

                try {
                    const deleteUrl = `${window.CRM_CONFIG.api.businessAccounts}${state.selectedBusinessAccountId}/`;
                    const response = await fetch(deleteUrl, {
                        method: 'DELETE',
                        headers: {
                            'X-CSRFToken': window.CRM_CONFIG.csrfToken,
                        },
                    });

                    if (!response.ok) {
                        throw new Error('Failed to delete business line.');
                    }

                    showToast(`Removed "${accName}".`);
                    state.selectedBusinessAccountId = null;
                    state.activeConversationId = null;
                    elements.chatInterface.style.display = 'none';
                    elements.chatPlaceholder.style.display = 'flex';

                    await loadBusinessAccounts();
                    await loadConversations(true);
                } catch (err) {
                    console.error('Error removing business line:', err);
                    showToast('Could not remove business line.');
                }
            });
        }
    }

    /* ==========================================================================
       Initialization
       ========================================================================== */

    async function init() {
        initEventListeners();

        // Restore saved sidebar collapsed state on desktop
        if (window.innerWidth > 768) {
            const savedCollapsed = localStorage.getItem('wa_sidebar_collapsed') === 'true';
            if (savedCollapsed) {
                elements.appContainer.classList.add('sidebar-collapsed');
            }
            if (elements.btnToggleSidebar) {
                elements.btnToggleSidebar.title = savedCollapsed ? 'Expand conversations sidebar' : 'Collapse conversations sidebar';
            }
        }

        // Deep link from a CRM lead page: /whatsapp/?phone=9876543210  or  ?conversation=<id>
        const deepLink = new URLSearchParams(window.location.search);
        const linkConversation = parseInt(deepLink.get('conversation'), 10);
        const linkPhone = (deepLink.get('phone') || '').replace(/\D/g, '').slice(-10);

        await loadBusinessAccounts();
        if (linkConversation || linkPhone) state.selectedBusinessAccountId = null; // search all numbers
        await loadConversations(!(linkConversation || linkPhone));
        if (linkConversation) {
            selectConversation(linkConversation);
        } else if (linkPhone) {
            const match = state.conversations.find(c => String(c.phone_number || '').replace(/\D/g, '').endsWith(linkPhone));
            if (match) selectConversation(match.id);
            else showToast('No WhatsApp chat with this number yet.');
        }
        setupInboxWebSocket();
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();

// Global Audio Player Helpers
window.toggleAudioPlayback = function(btn) {
    const player = btn.closest('.message-audio-player');
    if (!player) return;
    const audio = player.querySelector('audio');
    const playIcon = btn.querySelector('.icon-play');
    const pauseIcon = btn.querySelector('.icon-pause');
    if (!audio) return;

    document.querySelectorAll('.message-audio-player.playing').forEach(p => {
        if (p !== player) {
            const a = p.querySelector('audio');
            if (a) a.pause();
            p.classList.remove('playing');
            const b = p.querySelector('.audio-play-btn');
            if (b) {
                const pi = b.querySelector('.icon-play');
                const pui = b.querySelector('.icon-pause');
                if (pi) pi.style.display = 'block';
                if (pui) pui.style.display = 'none';
            }
        }
    });

    if (audio.paused) {
        audio.play().then(() => {
            player.classList.add('playing');
            if (playIcon) playIcon.style.display = 'none';
            if (pauseIcon) pauseIcon.style.display = 'block';
        }).catch(e => console.warn('Audio play prevented:', e));
    } else {
        audio.pause();
        player.classList.remove('playing');
        if (playIcon) playIcon.style.display = 'block';
        if (pauseIcon) pauseIcon.style.display = 'none';
    }
};

window.onAudioEnded = function(audio) {
    const player = audio.closest('.message-audio-player');
    if (!player) return;
    player.classList.remove('playing');
    const btn = player.querySelector('.audio-play-btn');
    if (btn) {
        const playIcon = btn.querySelector('.icon-play');
        const pauseIcon = btn.querySelector('.icon-pause');
        if (playIcon) playIcon.style.display = 'block';
        if (pauseIcon) pauseIcon.style.display = 'none';
    }
};
