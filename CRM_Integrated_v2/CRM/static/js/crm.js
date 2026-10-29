/**
 * TECHPANDA CRM - Interactive Client Scripts
 * Handles: Theme toggle, Sidebar state persistence, Confirmation dialogs, Live Call Dialer
 */

(function () {
  'use strict';

  // 0. Auto-detect Device Time Zone and pass to CRM
  try {
    const deviceTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (deviceTz) {
      const existingTz = (document.cookie.match(/(?:^|; )django_timezone=([^;]*)/) || [])[1];
      if (existingTz !== encodeURIComponent(deviceTz)) {
        document.cookie = `django_timezone=${encodeURIComponent(deviceTz)}; path=/; max-age=31536000; SameSite=Lax`;
      }
    }
  } catch (e) {
    console.warn('Timezone detection error:', e);
  }

  // 1. Theme Management (Light / Dark)
  const THEME_KEY = 'techpanda_theme';
  const themeToggleBtn = document.getElementById('theme-toggle');

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    document.documentElement.style.colorScheme = theme;
    localStorage.setItem(THEME_KEY, theme);
    if (themeToggleBtn) {
      const is3dCoin = themeToggleBtn.querySelector('.tp-3d-coin');
      if (is3dCoin) {
        themeToggleBtn.setAttribute('title', theme === 'dark' ? 'Switch to Light theme' : 'Switch to Dark theme');
      } else {
        const sunIcon = themeToggleBtn.querySelector('.icon-sun');
        const moonIcon = themeToggleBtn.querySelector('.icon-moon');
        if (theme === 'dark') {
          if (sunIcon) sunIcon.style.display = 'inline-block';
          if (moonIcon) moonIcon.style.display = 'none';
        } else {
          if (sunIcon) sunIcon.style.display = 'none';
          if (moonIcon) moonIcon.style.display = 'inline-block';
        }
      }
    }
    window.dispatchEvent(new CustomEvent('tp:themechange', { detail: { theme: theme } }));
  }

  const savedTheme = localStorage.getItem(THEME_KEY) || 'light';
  applyTheme(savedTheme);

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', function () {
      document.documentElement.classList.add('theme-transitioning');
      const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
      applyTheme(newTheme);
      setTimeout(function () {
        document.documentElement.classList.remove('theme-transitioning');
      }, 350);
    });
  }

  // 1.1 Presentation: Password Visibility Toggle
  document.addEventListener('click', function(e) {
    const toggleBtn = e.target.closest('.tp-password-toggle-btn');
    if (!toggleBtn) return;
    const wrapper = toggleBtn.closest('.tp-password-field-wrapper') || toggleBtn.parentElement;
    if (!wrapper) return;
    const input = wrapper.querySelector('input');
    if (!input) return;
    if (input.type === 'password') {
      input.type = 'text';
      toggleBtn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>';
      toggleBtn.setAttribute('aria-label', 'Hide password');
    } else {
      input.type = 'password';
      toggleBtn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>';
      toggleBtn.setAttribute('aria-label', 'Show password');
    }
  });

  // 1.2 Presentation: KPI Cards Stagger & Number Counter Animation
  function initDashboardStaggerAndCounters() {
    const kpiCards = document.querySelectorAll('.tp-kpi-card, .kpi-card');
    kpiCards.forEach(function(card, idx) {
      card.style.setProperty('--stagger-index', idx);
    });

    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return;
    }

    const valueEls = document.querySelectorAll('.kpi-value');
    valueEls.forEach(function(el) {
      const text = el.textContent.trim();
      if (/^\d+$/.test(text)) {
        const target = parseInt(text, 10);
        if (target > 0) {
          const duration = Math.min(750, 250 + target * 15);
          const startTimestamp = performance.now();
          function step(now) {
            const progress = Math.min((now - startTimestamp) / duration, 1);
            const easeOut = 1 - Math.pow(1 - progress, 3);
            const current = Math.floor(target * easeOut);
            el.textContent = current;
            if (progress < 1) {
              requestAnimationFrame(step);
            } else {
              el.textContent = target;
            }
          }
          requestAnimationFrame(step);
        }
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDashboardStaggerAndCounters);
  } else {
    initDashboardStaggerAndCounters();
  }

  // 2. Sidebar Persistence and Collapse
  const SIDEBAR_KEY = 'techpanda_sidebar_collapsed';
  const sidebar = document.querySelector('.app-sidebar');
  const sidebarToggle = document.getElementById('sidebar-toggle');
  const sidebarBackdrop = document.getElementById('sidebar-backdrop');

  if (sidebar && sidebarToggle) {
    const isCollapsed = localStorage.getItem(SIDEBAR_KEY) === 'true';
    if (isCollapsed && window.innerWidth > 900) {
      sidebar.classList.add('collapsed');
    }

    function toggleMobileSidebar(open) {
      if (open === undefined) {
        open = !sidebar.classList.contains('mobile-open');
      }
      if (open) {
        sidebar.classList.add('mobile-open');
        if (sidebarBackdrop) sidebarBackdrop.classList.add('is-active');
      } else {
        sidebar.classList.remove('mobile-open');
        if (sidebarBackdrop) sidebarBackdrop.classList.remove('is-active');
      }
    }

    sidebarToggle.addEventListener('click', function () {
      if (window.innerWidth <= 900) {
        toggleMobileSidebar();
      } else {
        sidebar.classList.toggle('collapsed');
        localStorage.setItem(SIDEBAR_KEY, sidebar.classList.contains('collapsed'));
      }
    });

    if (sidebarBackdrop) {
      sidebarBackdrop.addEventListener('click', function () {
        toggleMobileSidebar(false);
      });
    }
  }


  // 2.1 Navigation Accordions (Expand/Collapse Drawers)
  const navGroupHeaders = document.querySelectorAll('.nav-group-header');
  navGroupHeaders.forEach(header => {
    header.addEventListener('click', function(e) {
      e.preventDefault();
      const targetId = this.getAttribute('data-target');
      const children = document.getElementById(targetId);
      if (children) {
        const isOpen = children.classList.contains('open');
        children.classList.toggle('open', !isOpen);
        this.classList.toggle('open', !isOpen);
        if (targetId) {
          localStorage.setItem('tp_nav_' + targetId, !isOpen);
        }
      }
    });
  });

  // Auto-open groups that contain an active nav item or was previously saved as open
  document.querySelectorAll('.nav-group').forEach(group => {
    const children = group.querySelector('.nav-group-children');
    const header = group.querySelector('.nav-group-header');
    if (children && header) {
      const hasActive = children.querySelector('.nav-item.active') !== null;
      const targetId = header.getAttribute('data-target');
      const savedOpen = targetId ? localStorage.getItem('tp_nav_' + targetId) === 'true' : false;
      if (hasActive || savedOpen) {
        children.classList.add('open');
        header.classList.add('open');
      }
    }
  });

  // 3. Confirmation Dialogs for Destructive Actions
  document.addEventListener('click', function (e) {
    const confirmBtn = e.target.closest('[data-confirm]');
    if (confirmBtn) {
      const message = confirmBtn.getAttribute('data-confirm') || 'Are you sure you want to perform this action?';
      if (!window.confirm(message)) {
        e.preventDefault();
        e.stopPropagation();
      }
    }
  });

  // Helper: CSRF Cookie reader
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  // 4. Live Call Timer & Mandatory Call-Notes Lock Workflow
  let callTimerInterval = null;
  let callSeconds = 0;
  let currentActiveCallId = null;

  function formatDuration(sec) {
    const hrs = Math.floor(sec / 3600);
    const mins = Math.floor((sec % 3600) / 60);
    const secs = sec % 60;
    if (hrs > 0) {
      return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }

  function showCallNotesRequiredModal(pendingCall) {
    const lockModal = document.getElementById('call-notes-required-modal');
    if (!lockModal) {
      alert('You have a completed call that still requires notes before calling another lead.');
      return;
    }
    const leadNameEl = document.getElementById('lock-modal-lead-name');
    const leadPhoneEl = document.getElementById('lock-modal-lead-phone');
    if (leadNameEl) leadNameEl.textContent = pendingCall.lead_name || 'Assigned Lead';
    if (leadPhoneEl) leadPhoneEl.textContent = pendingCall.lead_phone || '-';

    const addNotesBtn = document.getElementById('lock-modal-add-notes-btn');
    if (addNotesBtn) {
      addNotesBtn.onclick = function () {
        lockModal.style.display = 'none';
        openCompletionFormForPendingCall(pendingCall);
      };
    }
    lockModal.style.display = 'flex';
  }

  function openCompletionFormForPendingCall(pendingCall) {
    const overlay = document.getElementById('call-dialer-overlay');
    if (!overlay) return;

    if (callTimerInterval) clearInterval(callTimerInterval);

    currentActiveCallId = pendingCall.id;
    callSeconds = pendingCall.duration || 0;

    const callInput = document.getElementById('call-form-call-id');
    if (callInput) callInput.value = pendingCall.id;

    const leadInput = document.getElementById('call-form-lead-id');
    if (leadInput) leadInput.value = pendingCall.lead_id;

    const durationInput = document.getElementById('call-form-duration');
    if (durationInput) durationInput.value = callSeconds;

    const compName = document.getElementById('completion-lead-name');
    if (compName) compName.textContent = pendingCall.lead_name;

    const compPhone = document.getElementById('completion-lead-phone');
    if (compPhone) compPhone.textContent = pendingCall.lead_phone;

    const compDur = document.getElementById('completion-lead-duration');
    if (compDur) compDur.textContent = pendingCall.formatted_duration || formatDuration(callSeconds);

    const notesInput = document.getElementById('call-form-notes');
    if (notesInput) {
      notesInput.value = '';
      setTimeout(() => notesInput.focus(), 150);
    }
    const notesErr = document.getElementById('call-form-notes-error');
    if (notesErr) notesErr.style.display = 'none';

    document.getElementById('dialer-calling-state').style.display = 'none';
    document.getElementById('dialer-completion-form').style.display = 'block';
    overlay.classList.add('active');
  }

  function minimizeCallDock() {
    const overlay = document.getElementById('call-dialer-overlay');
    const btnMin = document.getElementById('btn-minimize-call-dock');
    const btnMax = document.getElementById('btn-maximize-call-dock');
    const miniActions = document.querySelector('.tp-minimized-actions');
    const fullActions = document.querySelector('.tp-full-modal-actions');
    if (overlay) {
      overlay.classList.add('tp-call-dock-minimized');
      if (btnMin) btnMin.style.display = 'none';
      if (btnMax) btnMax.style.display = 'inline-flex';
      if (miniActions) miniActions.style.display = 'flex';
      if (fullActions) fullActions.style.display = 'none';
    }
  }

  function maximizeCallDock() {
    const overlay = document.getElementById('call-dialer-overlay');
    const btnMin = document.getElementById('btn-minimize-call-dock');
    const btnMax = document.getElementById('btn-maximize-call-dock');
    const miniActions = document.querySelector('.tp-minimized-actions');
    const fullActions = document.querySelector('.tp-full-modal-actions');
    if (overlay) {
      overlay.classList.remove('tp-call-dock-minimized');
      if (btnMin) btnMin.style.display = 'inline-flex';
      if (btnMax) btnMax.style.display = 'none';
      if (miniActions) miniActions.style.display = 'none';
      if (fullActions) fullActions.style.display = 'block';
    }
  }

  window.minimizeCallDock = minimizeCallDock;
  window.maximizeCallDock = maximizeCallDock;

  // Wire floating dock minimize & expand click triggers
  document.addEventListener('DOMContentLoaded', function () {
    const btnMin = document.getElementById('btn-minimize-call-dock');
    const btnMax = document.getElementById('btn-maximize-call-dock');
    if (btnMin) btnMin.addEventListener('click', function (e) { e.stopPropagation(); minimizeCallDock(); });
    if (btnMax) btnMax.addEventListener('click', function (e) { e.stopPropagation(); maximizeCallDock(); });

    const dialerCard = document.querySelector('.dialer-card');
    if (dialerCard) {
      dialerCard.addEventListener('click', function (e) {
        const overlay = document.getElementById('call-dialer-overlay');
        if (overlay && overlay.classList.contains('tp-call-dock-minimized')) {
          if (e.target.closest('.btn-end-minimized')) return;
          maximizeCallDock();
        }
      });
    }
  });

  let callPollInterval = null;
  let currentActiveLeadId = null;

  function startDialerUI(callId, leadId, leadName, leadPhone) {
    const overlay = document.getElementById('call-dialer-overlay');
    if (!overlay) return;

    maximizeCallDock();
    currentActiveCallId = callId;
    currentActiveLeadId = leadId;
    callSeconds = 0;

    // Reset intervals
    if (callTimerInterval) clearInterval(callTimerInterval);
    callTimerInterval = null;
    if (callPollInterval) clearInterval(callPollInterval);
    callPollInterval = null;

    const dialerCard = document.querySelector('.dialer-card');
    if (dialerCard) dialerCard.classList.add('dialer-card-lead-details');

    document.getElementById('dialer-lead-name').textContent = leadName;
    document.getElementById('dialer-lead-phone').textContent = leadPhone;
    document.getElementById('dialer-timer-display').textContent = '00:00';
    
    // Switch to unified in-call workspace immediately
    document.getElementById('dialer-calling-state').style.display = 'none';
    const compForm = document.getElementById('dialer-completion-form');
    if (compForm) {
      compForm.style.display = 'block';
      compForm.classList.remove('hide-empty-active');
    }

    const incallTopBar = document.getElementById('modal-incall-top-bar');
    if (incallTopBar) incallTopBar.style.display = 'flex';
    const defaultTopRibbon = document.getElementById('modal-default-top-ribbon');
    if (defaultTopRibbon) defaultTopRibbon.style.display = 'none';

    const incallTimerEl = document.getElementById('incall-timer-display');
    if (incallTimerEl) incallTimerEl.textContent = '00:00';
    const incallBadge = document.getElementById('incall-status-badge');
    if (incallBadge) {
      incallBadge.textContent = 'Connecting Call…';
      incallBadge.style.color = '#60a5fa';
      incallBadge.style.background = 'rgba(59, 130, 246, 0.2)';
      incallBadge.style.borderColor = 'rgba(59, 130, 246, 0.4)';
    }
    const incallSyncText = document.getElementById('incall-sync-status-text');
    if (incallSyncText) incallSyncText.textContent = 'Sending call request to paired mobile…';
    const btnIncallEnd = document.getElementById('btn-incall-end');
    if (btnIncallEnd) btnIncallEnd.style.display = 'inline-flex';

    const stateBadge = document.getElementById('dialer-state-badge');
    if (stateBadge) {
      stateBadge.textContent = 'Connecting Call…';
      stateBadge.style.color = 'var(--primary, #2563eb)';
    }

    const callInput = document.getElementById('call-form-call-id');
    if (callInput) callInput.value = callId;

    const leadInput = document.getElementById('call-form-lead-id');
    if (leadInput) leadInput.value = leadId;

    const compName = document.getElementById('completion-lead-name');
    if (compName) compName.textContent = leadName;

    const compPhone = document.getElementById('completion-lead-phone');
    if (compPhone) compPhone.textContent = leadPhone;

    overlay.classList.add('active');

    // Immediately load full lead details so telecaller can fill info during the call!
    loadModalLeadDetails(leadId);

    // Real-time tracking of phone dispatch & call states
    const statusText = document.getElementById('dialer-sync-status-text');
    const statusBox = document.getElementById('dialer-sync-status');
    if (statusText) statusText.textContent = 'Sending call request to paired mobile…';

    let isTimerActive = false;
    let pollFailures = 0;

    callPollInterval = setInterval(function () {
      if (currentActiveCallId !== callId) {
        clearInterval(callPollInterval);
        return;
      }

      fetch('/calls/device-status/?call_id=' + encodeURIComponent(callId))
        .then(r => r.json())
        .then(st => {
          if (currentActiveCallId !== callId) return;

          // Device connectivity alert
          if (!st.has_device || !st.is_online) {
            if (statusText) statusText.textContent = '⚠️ Connection lost — reconnect CRM CallSync app on mobile';
            if (incallSyncText) incallSyncText.textContent = '⚠️ Reconnect phone: CRM CallSync offline';
            if (statusBox) {
              statusBox.style.background = '#fef2f2';
              statusBox.style.borderColor = '#fca5a5';
              statusBox.style.color = '#b91c1c';
            }
          }

          const callStatus = st.call_status;

          // Helper to update both timers
          function updateTimerDisplays(sec) {
            const formatted = formatDuration(sec);
            const timerEl = document.getElementById('dialer-timer-display');
            if (timerEl) timerEl.textContent = formatted;
            const incallTimer = document.getElementById('incall-timer-display');
            if (incallTimer) incallTimer.textContent = formatted;
          }

          // 1. QUEUED / DISPATCHED
          if (callStatus === 'Queued' || (!callStatus && st.is_dispatched)) {
            if (stateBadge) stateBadge.textContent = 'Queued for phone…';
            if (incallBadge) {
              incallBadge.textContent = st.is_dispatched ? 'Dialing on Phone…' : 'Queued…';
              incallBadge.style.color = '#93c5fd';
            }
            const msg = st.is_dispatched ? '✓ Call received by phone — dialing now!' : 'Waiting for phone to pick up request…';
            if (statusText && st.is_online) statusText.textContent = msg;
            if (incallSyncText && st.is_online) incallSyncText.textContent = msg;
            if (statusBox && st.is_dispatched) {
              statusBox.style.background = '#eff6ff';
              statusBox.style.borderColor = '#93c5fd';
              statusBox.style.color = '#1d4ed8';
            }
            updateTimerDisplays(0);
          }
          // 2. DIALING
          else if (callStatus === 'Dialing') {
            if (stateBadge) stateBadge.textContent = 'Dialing…';
            if (incallBadge) {
              incallBadge.textContent = 'Dialing…';
              incallBadge.style.color = '#fef08a';
            }
            const msg = 'Dialing number on mobile device…';
            if (statusText) statusText.textContent = msg;
            if (incallSyncText) incallSyncText.textContent = msg;
            if (statusBox) {
              statusBox.style.background = '#eff6ff';
              statusBox.style.borderColor = '#bfdbfe';
              statusBox.style.color = '#1d4ed8';
            }
            updateTimerDisplays(0);
          }
          // 3. RINGING
          else if (callStatus === 'Ringing') {
            if (stateBadge) stateBadge.textContent = 'Ringing…';
            if (incallBadge) {
              incallBadge.textContent = 'Ringing…';
              incallBadge.style.color = '#fde047';
            }
            const msg = 'Recipient phone is ringing…';
            if (statusText) statusText.textContent = msg;
            if (incallSyncText) incallSyncText.textContent = msg;
            if (statusBox) {
              statusBox.style.background = '#fef3c7';
              statusBox.style.borderColor = '#fcd34d';
              statusBox.style.color = '#b45309';
            }
            updateTimerDisplays(0);
          }
          // 4. IN PROGRESS (Answered!)
          else if (callStatus === 'In Progress') {
            if (stateBadge) {
              stateBadge.textContent = 'Call Connected';
              stateBadge.style.color = '#16a34a';
            }
            if (incallBadge) {
              incallBadge.textContent = 'Call Connected';
              incallBadge.style.color = '#4ade80';
              incallBadge.style.background = 'rgba(34, 197, 94, 0.2)';
              incallBadge.style.borderColor = 'rgba(34, 197, 94, 0.4)';
            }
            const msg = 'Conversation in progress — fill lead qualification details below';
            if (statusText) statusText.textContent = msg;
            if (incallSyncText) incallSyncText.textContent = msg;
            if (statusBox) {
              statusBox.style.background = '#dcfce7';
              statusBox.style.borderColor = '#86efac';
              statusBox.style.color = '#15803d';
            }

            // Sync authoritative server duration & start local ticking if not already running
            if (typeof st.elapsed_seconds === 'number' && st.elapsed_seconds >= 0) {
              callSeconds = st.elapsed_seconds;
              updateTimerDisplays(callSeconds);
            }

            if (!isTimerActive) {
              isTimerActive = true;
              if (callTimerInterval) clearInterval(callTimerInterval);
              callTimerInterval = setInterval(function () {
                callSeconds++;
                updateTimerDisplays(callSeconds);
              }, 1000);
            }
          }
          // 5. COMPLETED / TERMINAL STATES
          else if (['Completed', 'No Answer', 'Busy', 'Failed', 'Cancelled'].includes(callStatus)) {
            clearInterval(callPollInterval);
            if (callTimerInterval) clearInterval(callTimerInterval);
            isTimerActive = false;
            maximizeCallDock();

            if (typeof st.duration === 'number' && st.duration > 0) {
              callSeconds = st.duration;
            }

            updateTimerDisplays(callSeconds);

            // Transition to lead completion state
            showLeadCompletionInterface(callSeconds, callStatus);
          }
        })
        .catch(() => {
          pollFailures++;
        });
    }, 1500);
  }

  let isDialerRequestInProgress = false;

  window.openCallDialer = function (leadId, leadName, leadPhone) {
    if (isDialerRequestInProgress) {
      console.warn('Call dialer start already in progress');
      return;
    }
    isDialerRequestInProgress = true;

    // Call backend start endpoint to verify Call-Notes Lock
    const csrfToken = getCookie('csrftoken') || '';
    const formData = new FormData();
    formData.append('lead_id', leadId);

    fetch('/calls/start/', {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrfToken,
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: formData
    })
    .then(r => r.json().then(data => ({ status: r.status, ok: r.ok, data: data })))
    .then(res => {
      isDialerRequestInProgress = false;
      if (res.status === 400 && res.data.blocked) {
        showCallNotesRequiredModal(res.data.pending_call);
        return;
      }
      if (!res.ok || !res.data.success) {
        alert(res.data.error || 'Failed to start call.');
        return;
      }
      // Start call UI
      startDialerUI(res.data.call_id, res.data.lead_id, res.data.lead_name || leadName, res.data.lead_phone || leadPhone);
    })
    .catch(err => {
      console.error('Call start error:', err);
      // Fallback: check lock via GET if POST fails unexpectedly
      fetch(`/calls/start/?lead_id=${leadId}`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      })
      .then(r => r.json().then(data => ({ status: r.status, ok: r.ok, data: data })))
      .then(res => {
        isDialerRequestInProgress = false;
        if (res.status === 400 && res.data.blocked) {
          showCallNotesRequiredModal(res.data.pending_call);
        } else if (res.data.success) {
          startDialerUI(res.data.call_id, res.data.lead_id, res.data.lead_name || leadName, res.data.lead_phone || leadPhone);
        }
      })
      .catch(() => {
        isDialerRequestInProgress = false;
      });
    });
  };

  window.endActiveCall = function () {
    if (callPollInterval) clearInterval(callPollInterval);
    if (callTimerInterval) clearInterval(callTimerInterval);
    callPollInterval = null;
    callTimerInterval = null;

    // If there is no active call ID, this was not a real call session — simply close the dialer
    if (!currentActiveCallId) {
      closeCallDialer();
      return;
    }

    const endingCallId = currentActiveCallId;
    const endingLeadId = currentActiveLeadId;
    const endingDuration = callSeconds;

    // Call backend end endpoint
    const formData = new FormData();
    formData.append('duration', endingDuration);
    fetch(`/calls/${endingCallId}/end/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken') || '',
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: formData
    }).catch(err => console.warn('Call end notify failed:', err));

    // Check if user is ALREADY on this lead's detail page
    const currentPath = window.location.pathname;
    const isOnCurrentLeadPage = endingLeadId && (
      currentPath.endsWith(`/leads/${endingLeadId}/`) ||
      currentPath.includes(`/leads/${endingLeadId}/`)
    );

    if (isOnCurrentLeadPage && document.getElementById('callNotesSection')) {
      closeCallDialer();
      if (typeof window.focusCallNotesSection === 'function') {
        window.focusCallNotesSection(endingCallId, endingDuration);
      } else {
        const section = document.getElementById('callNotesSection');
        if (section) section.scrollIntoView({ behavior: 'smooth', block: 'center' });
        const notesInput = document.getElementById('page-call-notes');
        if (notesInput) setTimeout(() => notesInput.focus(), 300);
        const cIdInput = document.getElementById('page-call-id');
        if (cIdInput) cIdInput.value = endingCallId;
        const dInput = document.getElementById('page-call-duration');
        if (dInput) dInput.value = endingDuration;
      }
      return;
    }

    maximizeCallDock();

    // Transition to modern lead completion interface
    showLeadCompletionInterface(endingDuration, 'Completed');
  };

  window.closeCallDialer = function () {
    if (callPollInterval) clearInterval(callPollInterval);
    if (callTimerInterval) clearInterval(callTimerInterval);
    callPollInterval = null;
    callTimerInterval = null;
    currentActiveCallId = null;
    currentActiveLeadId = null;
    const dialerCard = document.querySelector('.dialer-card');
    if (dialerCard) dialerCard.classList.remove('dialer-card-lead-details');
    const overlay = document.getElementById('call-dialer-overlay');
    if (overlay) {
      overlay.classList.remove('active');
      overlay.classList.remove('tp-call-dock-minimized');
    }
  };

  function escapeModalHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Modern Lead Completion Interface Handlers
  window.showLeadCompletionInterface = function (callSeconds, callStatus) {
    const dialerCard = document.querySelector('.dialer-card');
    if (dialerCard) dialerCard.classList.add('dialer-card-lead-details');

    const callingState = document.getElementById('dialer-calling-state');
    if (callingState) callingState.style.display = 'none';

    const compForm = document.getElementById('dialer-completion-form');
    if (compForm) {
      compForm.style.display = 'block';
      compForm.classList.remove('hide-empty-active');
    }

    const durationInput = document.getElementById('call-form-duration');
    if (durationInput) durationInput.value = callSeconds || 0;

    const compDur = document.getElementById('completion-lead-duration');
    if (compDur) compDur.textContent = formatDuration(callSeconds || 0);

    const outcomeSelect = document.getElementById('call-form-outcome');
    if (outcomeSelect && callStatus) {
      if (['No Answer', 'Busy'].includes(callStatus)) {
        outcomeSelect.value = callStatus;
      }
    }

    const notesInput = document.getElementById('call-form-notes');
    if (notesInput) {
      if (!notesInput.value) {
        notesInput.value = '';
      }
      setTimeout(() => notesInput.focus(), 120);
    }

    const btnIncallEnd = document.getElementById('btn-incall-end');
    if (btnIncallEnd) btnIncallEnd.style.display = 'none';

    const incallBadge = document.getElementById('incall-state-badge');
    if (incallBadge) {
      incallBadge.textContent = callStatus === 'Completed' ? 'Call Ended' : (callStatus || 'Call Ended');
      incallBadge.style.color = '#ef4444';
      incallBadge.style.background = 'rgba(239, 68, 68, 0.2)';
      incallBadge.style.borderColor = 'rgba(239, 68, 68, 0.4)';
    }

    const incallSyncText = document.getElementById('incall-sync-status-text');
    if (incallSyncText) incallSyncText.textContent = 'Call finished — review qualification details and submit conversation notes';

    if (currentActiveLeadId) {
      loadModalLeadDetails(currentActiveLeadId);
    }
  };

  // Modal Inline Field Editing Engine
  let modalCurrentEditingKey = null;
  const modalFieldControllers = {};
  const modalFieldCounters = {};

  window.activateModalFieldEdit = function (key) {
    const item = document.querySelector(`.lead-field-item[data-modal-key="${key}"]`);
    if (!item || item.getAttribute('data-editable') !== '1') return;

    if (modalCurrentEditingKey && modalCurrentEditingKey !== key) {
      const prevKey = modalCurrentEditingKey;
      const prevItem = document.querySelector(`.lead-field-item[data-modal-key="${prevKey}"]`);
      const prevInput = document.getElementById(`modal-input-${prevKey}`);
      if (prevItem && prevInput) {
        const prevRaw = (prevItem.getAttribute('data-raw') || '').trim();
        if (prevInput.value.trim() !== prevRaw) {
          window.saveModalFieldAuto(currentActiveLeadId, prevKey, true);
        } else {
          closeModalFieldEditorIfClean(prevKey);
        }
      }
    }

    const displayEl = document.getElementById(`modal-display-${key}`);
    const editorEl = document.getElementById(`modal-editor-${key}`);
    const inputEl = document.getElementById(`modal-input-${key}`);
    const errEl = document.getElementById(`modal-error-${key}`);

    if (errEl) errEl.style.display = 'none';
    if (displayEl) displayEl.style.display = 'none';
    if (editorEl) editorEl.style.display = 'flex';
    item.classList.add('is-editing');
    modalCurrentEditingKey = key;

    if (inputEl) {
      inputEl.focus();
      if (inputEl.select && inputEl.type !== 'select-one' && inputEl.type !== 'datetime-local' && inputEl.type !== 'date') {
        inputEl.select();
      }
    }
  };

  function closeModalFieldEditorIfClean(key) {
    const item = document.querySelector(`.lead-field-item[data-modal-key="${key}"]`);
    const displayEl = document.getElementById(`modal-display-${key}`);
    const editorEl = document.getElementById(`modal-editor-${key}`);
    const errEl = document.getElementById(`modal-error-${key}`);

    if (errEl && errEl.style.display !== 'none') return;
    if (editorEl) editorEl.style.display = 'none';
    if (displayEl) displayEl.style.display = 'flex';
    if (item) item.classList.remove('is-editing');
    if (modalCurrentEditingKey === key) modalCurrentEditingKey = null;
  }

  window.setModalFieldStatus = function (key, state, errorMsg) {
    const statusEl = document.getElementById(`modal-status-${key}`);
    const badgeEl = document.getElementById(`modal-status-badge-${key}`);
    const errEl = document.getElementById(`modal-error-${key}`);

    [statusEl, badgeEl].forEach(el => {
      if (!el) return;
      el.className = 'lead-field-status';
      if (state === 'saving') {
        el.classList.add('status-saving');
        el.innerHTML = `<svg class="spin-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> <span>Saving...</span>`;
        el.style.display = 'inline-flex';
      } else if (state === 'saved') {
        el.classList.add('status-saved');
        el.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg> <span>Saved</span>`;
        el.style.display = 'inline-flex';
        setTimeout(() => {
          if (el.classList.contains('status-saved')) {
            el.style.display = 'none';
            el.classList.remove('status-saved');
          }
        }, 2500);
      } else if (state === 'error') {
        el.classList.add('status-error');
        el.innerHTML = `<span>Failed</span>`;
        el.style.display = 'inline-flex';
      } else {
        el.style.display = 'none';
      }
    });

    if (errEl) {
      if (state === 'error' && errorMsg) {
        errEl.textContent = errorMsg;
        errEl.style.display = 'block';
      } else if (state !== 'error') {
        errEl.style.display = 'none';
      }
    }
  };

  window.saveModalFieldAuto = function (leadId, key, closeOnSuccess) {
    if (!leadId) leadId = currentActiveLeadId;
    const item = document.querySelector(`.lead-field-item[data-modal-key="${key}"]`);
    const inputEl = document.getElementById(`modal-input-${key}`);
    const displayEl = document.getElementById(`modal-display-${key}`);
    const textEl = document.getElementById(`modal-text-${key}`);

    if (!item || !inputEl || !leadId) return;
    const newVal = inputEl.value.trim();
    const currentRaw = (item.getAttribute('data-raw') || '').trim();

    if (newVal === currentRaw) {
      if (closeOnSuccess) closeModalFieldEditorIfClean(key);
      return;
    }

    if (modalFieldControllers[key]) {
      modalFieldControllers[key].abort();
    }
    const controller = new AbortController();
    modalFieldControllers[key] = controller;

    modalFieldCounters[key] = (modalFieldCounters[key] || 0) + 1;
    const reqId = modalFieldCounters[key];

    setModalFieldStatus(key, 'saving');
    const csrf = getCookie('csrftoken') || '';

    fetch(`/leads/api/${leadId}/update-field/`, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf,
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: JSON.stringify({
        field: key,
        value: newVal
      })
    })
    .then(res => res.json().then(data => ({ ok: res.ok, status: res.status, data: data })))
    .then(res => {
      if (reqId !== modalFieldCounters[key]) return;

      if (!res.ok || !res.data.success) {
        const msg = (res.data && res.data.error) ? res.data.error : 'Failed to update field.';
        setModalFieldStatus(key, 'error', msg);
        return;
      }

      const d = res.data;
      item.setAttribute('data-raw', d.raw_value || '');
      setModalFieldStatus(key, 'saved');

      if (textEl) {
        if (key === 'phone') {
          textEl.innerHTML = `<span class="lead-phone-flag">🇮🇳</span><span>${escapeModalHtml(d.value)}</span>`;
        } else {
          textEl.innerHTML = `<span>${escapeModalHtml(d.value)}</span>`;
        }
      }

      if (d.is_empty) {
        item.classList.add('is-empty-field');
        if (displayEl) displayEl.classList.add('text-empty');
      } else {
        item.classList.remove('is-empty-field');
        if (displayEl) displayEl.classList.remove('text-empty');
      }

      // Sync header or form elements if status or assignee changed
      if (key === 'status') {
        const pillLabel = document.getElementById('modalStatusLabel');
        if (pillLabel) pillLabel.textContent = d.value;
        const selectHidden = document.getElementById('modalStatusSelect');
        if (selectHidden) selectHidden.value = d.value;
        const callFormStatus = document.getElementById('call-form-lead-status');
        if (callFormStatus) callFormStatus.value = d.value;
      } else if (key === 'assignee_name' || key === 'assignee') {
        const aName = document.getElementById('modal-assignee-name');
        if (aName) aName.textContent = d.value;
      }

      if (closeOnSuccess) {
        closeModalFieldEditorIfClean(key);
      }
    })
    .catch(err => {
      if (err.name === 'AbortError') return;
      setModalFieldStatus(key, 'error', 'Network error.');
    });
  };

  function renderModalFieldHtml(f, leadId) {
    const isEditable = Boolean(f.is_editable);
    const isEmpty = Boolean(f.is_empty);
    const rawVal = f.raw_value !== undefined ? f.raw_value : '';
    const displayVal = f.value || 'Empty';

    let iconHtml = '';
    if (f.type === 'text') {
      iconHtml = '<span class="field-icon">T</span>';
    } else if (f.type === 'select') {
      iconHtml = '<span class="field-icon icon-select">▾</span>';
    } else if (f.type === 'phone') {
      iconHtml = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg>';
    } else if (f.type === 'date') {
      iconHtml = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>';
    } else {
      iconHtml = '<span class="field-icon">#</span>';
    }

    const badgeHtml = f.badge ? `<span class="lead-phone-sim-badge">${escapeModalHtml(f.badge)}</span>` : '';
    const lockHtml = !isEditable ? `<span class="field-readonly-lock" title="${escapeModalHtml(f.read_only_reason || 'Read-only field')}"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg></span>` : '';

    let editorHtml = '';
    if (isEditable) {
      let inputControlHtml = '';
      if (f.control_type === 'select') {
        let optHtml = `<option value="">-- Select ${escapeModalHtml(f.label)} --</option>`;
        if (Array.isArray(f.options)) {
          f.options.forEach(opt => {
            const isSelected = (opt.value === rawVal || opt.label === rawVal || opt.value === displayVal || opt.label === displayVal);
            optHtml += `<option value="${escapeModalHtml(opt.value)}" ${isSelected ? 'selected' : ''}>${escapeModalHtml(opt.label)}</option>`;
          });
        }
        inputControlHtml = `<select class="lead-inline-input form-select" id="modal-input-${escapeModalHtml(f.key)}" onchange="saveModalFieldAuto('${leadId}', '${escapeModalHtml(f.key)}', true)">${optHtml}</select>`;
      } else if (f.control_type === 'number') {
        inputControlHtml = `<input type="number" class="lead-inline-input form-control" id="modal-input-${escapeModalHtml(f.key)}" value="${escapeModalHtml(rawVal)}" min="1950" max="2050" placeholder="${escapeModalHtml(f.label)}..." onblur="saveModalFieldAuto('${leadId}', '${escapeModalHtml(f.key)}', true)" onkeydown="if(event.key==='Enter') saveModalFieldAuto('${leadId}', '${escapeModalHtml(f.key)}', true)">`;
      } else if (f.control_type === 'date') {
        inputControlHtml = `<input type="date" class="lead-inline-input form-control" id="modal-input-${escapeModalHtml(f.key)}" value="${escapeModalHtml(rawVal)}" onchange="saveModalFieldAuto('${leadId}', '${escapeModalHtml(f.key)}', true)" onblur="saveModalFieldAuto('${leadId}', '${escapeModalHtml(f.key)}', true)">`;
      } else if (f.control_type === 'phone') {
        inputControlHtml = `<input type="tel" class="lead-inline-input form-control" id="modal-input-${escapeModalHtml(f.key)}" value="${escapeModalHtml(rawVal)}" placeholder="10-digit mobile number" onblur="saveModalFieldAuto('${leadId}', '${escapeModalHtml(f.key)}', true)" onkeydown="if(event.key==='Enter') saveModalFieldAuto('${leadId}', '${escapeModalHtml(f.key)}', true)">`;
      } else if (f.control_type === 'email') {
        inputControlHtml = `<input type="email" class="lead-inline-input form-control" id="modal-input-${escapeModalHtml(f.key)}" value="${escapeModalHtml(rawVal)}" placeholder="email@example.com" onblur="saveModalFieldAuto('${leadId}', '${escapeModalHtml(f.key)}', true)" onkeydown="if(event.key==='Enter') saveModalFieldAuto('${leadId}', '${escapeModalHtml(f.key)}', true)">`;
      } else {
        inputControlHtml = `<input type="text" class="lead-inline-input form-control" id="modal-input-${escapeModalHtml(f.key)}" value="${escapeModalHtml(rawVal)}" placeholder="Enter ${escapeModalHtml(f.label)}..." onblur="saveModalFieldAuto('${leadId}', '${escapeModalHtml(f.key)}', true)" onkeydown="if(event.key==='Enter') saveModalFieldAuto('${leadId}', '${escapeModalHtml(f.key)}', true)">`;
      }

      editorHtml = `
        <div class="lead-inline-editor" id="modal-editor-${escapeModalHtml(f.key)}" style="display: none;">
          <div class="lead-inline-input-wrap">
            ${inputControlHtml}
          </div>
          <div class="lead-inline-status-wrap">
            <span class="lead-field-status" id="modal-status-${escapeModalHtml(f.key)}"></span>
          </div>
          <div class="lead-inline-error" id="modal-error-${escapeModalHtml(f.key)}" style="display: none;"></div>
        </div>
      `;
    }

    const editPencilHtml = isEditable ? `<span class="lead-field-edit-btn" title="Edit ${escapeModalHtml(f.label)}"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg></span>` : '';
    const clickAttr = isEditable ? `onclick="activateModalFieldEdit('${escapeModalHtml(f.key)}');"` : '';
    const titleAttr = isEditable ? `title="Click to edit ${escapeModalHtml(f.label)}"` : `title="${escapeModalHtml(f.read_only_reason || '')}"`;

    return `
      <div class="lead-field-item ${isEmpty ? 'is-empty-field' : ''} ${isEditable ? 'is-editable' : 'is-readonly'}"
           data-modal-key="${escapeModalHtml(f.key)}"
           data-control="${escapeModalHtml(f.control_type || 'text')}"
           data-editable="${isEditable ? '1' : '0'}"
           data-raw="${escapeModalHtml(rawVal)}">
        <div class="lead-field-label">
          ${iconHtml}
          <span>${escapeModalHtml(f.label)}</span>
          ${badgeHtml}
          ${lockHtml}
        </div>
        <div class="lead-field-value ${isEmpty ? 'text-empty' : ''}" id="modal-display-${escapeModalHtml(f.key)}" ${clickAttr} ${titleAttr}>
          <span class="lead-field-text" id="modal-text-${escapeModalHtml(f.key)}">
            ${f.type === 'phone' && !isEmpty ? '<span class="lead-phone-flag">🇮🇳</span>' : ''}
            <span>${escapeModalHtml(displayVal)}</span>
          </span>
          ${editPencilHtml}
          <span class="lead-field-status inline-status-badge" id="modal-status-badge-${escapeModalHtml(f.key)}"></span>
        </div>
        ${editorHtml}
      </div>
    `;
  }

  window.loadModalLeadDetails = function (leadId) {
    if (!leadId) return;
    fetch(`/leads/api/${leadId}/quick-details/`, {
      headers: {
        'X-Requested-With': 'XMLHttpRequest'
      }
    })
    .then(r => r.json())
    .then(data => {
      if (!data || !data.success) return;

      const nameEl = document.getElementById('completion-lead-name');
      if (nameEl) nameEl.textContent = data.name || 'Lead Details';

      const phoneEl = document.getElementById('completion-lead-phone');
      if (phoneEl) phoneEl.textContent = data.display_phone || data.phone || '-';

      const statusLabel = document.getElementById('modalStatusLabel');
      if (statusLabel) statusLabel.textContent = data.status || 'Contacted';

      const statusSelect = document.getElementById('modalStatusSelect');
      if (statusSelect && data.status) statusSelect.value = data.status;

      const leadStatusForm = document.getElementById('call-form-lead-status');
      if (leadStatusForm && data.status) leadStatusForm.value = data.status;

      const counterEl = document.getElementById('modal-lead-counter');
      if (counterEl) counterEl.textContent = `Lead #${leadId} Call Session`;

      // Wire full lead page links
      ['modal-title-view-link', 'modal-open-full-page-btn', 'modal-btn-open-lead-page'].forEach(id => {
        const btn = document.getElementById(id);
        if (btn && data.lead_detail_url) {
          btn.href = data.lead_detail_url;
        }
      });

      const waBtn = document.getElementById('modal-whatsapp-btn');
      if (waBtn) {
        if (data.whatsapp_url) {
          waBtn.href = data.whatsapp_url;
          waBtn.style.pointerEvents = 'auto';
          waBtn.style.opacity = '1';
        } else {
          waBtn.href = '#';
          waBtn.style.pointerEvents = 'none';
          waBtn.style.opacity = '0.5';
        }
      }

      const emailBtn = document.getElementById('modal-email-btn');
      if (emailBtn) {
        if (data.email_url) {
          emailBtn.href = data.email_url;
          emailBtn.style.pointerEvents = 'auto';
          emailBtn.style.opacity = '1';
        } else {
          emailBtn.href = '#';
          emailBtn.style.pointerEvents = 'none';
          emailBtn.style.opacity = '0.5';
        }
      }

      const assigneeName = document.getElementById('modal-assignee-name');
      if (assigneeName) assigneeName.textContent = data.assignee || 'Unassigned';

      const assigneeAvatar = document.getElementById('modal-assignee-avatar');
      if (assigneeAvatar) assigneeAvatar.textContent = data.assignee_initials || 'TS';

      // Render Dynamic Two-Column Layout (Matching Lead Detail Page)
      const col1El = document.getElementById('modal-col1');
      const col2El = document.getElementById('modal-col2');
      if (col1El && Array.isArray(data.col1_fields)) {
        col1El.innerHTML = data.col1_fields.map(f => renderModalFieldHtml(f, leadId)).join('');
      }
      if (col2El && Array.isArray(data.col2_fields)) {
        col2El.innerHTML = data.col2_fields.map(f => renderModalFieldHtml(f, leadId)).join('');
      }

      // Render Recent Call Recordings & History Table
      const recentCallsWrap = document.getElementById('modal-recent-calls-wrap');
      if (recentCallsWrap) {
        if (Array.isArray(data.recent_calls) && data.recent_calls.length > 0) {
          let rowsHtml = '';
          data.recent_calls.forEach(rc => {
            let audioHtml = rc.recording_url
              ? `<audio controls preload="none" src="${escapeModalHtml(rc.recording_url)}" style="height: 30px; width: 220px; vertical-align: middle;">Audio not supported</audio>`
              : '<span style="color: var(--text-muted); font-size: 0.775rem;">No recording file</span>';

            rowsHtml += `
              <tr>
                <td style="white-space: nowrap; padding: 8px 12px; border-bottom: 1px solid var(--border-color);">${escapeModalHtml(rc.time)}</td>
                <td style="padding: 8px 12px; border-bottom: 1px solid var(--border-color);"><strong>${escapeModalHtml(rc.caller)}</strong></td>
                <td style="padding: 8px 12px; border-bottom: 1px solid var(--border-color);"><code>${escapeModalHtml(rc.duration)}</code></td>
                <td style="padding: 8px 12px; border-bottom: 1px solid var(--border-color);"><span class="badge" style="background: #eff6ff; color: #1d4ed8; font-size: 0.75rem;">${escapeModalHtml(rc.outcome)}</span></td>
                <td style="padding: 8px 12px; border-bottom: 1px solid var(--border-color); max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeModalHtml(rc.notes)}">${escapeModalHtml(rc.notes)}</td>
                <td style="padding: 8px 12px; border-bottom: 1px solid var(--border-color);">${audioHtml}</td>
              </tr>
            `;
          });

          recentCallsWrap.innerHTML = `
            <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 8px; padding: 16px; margin-top: 16px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <h4 style="font-size: 0.925rem; font-weight: 700; margin: 0; color: var(--text-main); display: flex; align-items: center; gap: 8px;">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg>
                  <span>Recent Calls &amp; Audio Recordings (${data.recent_calls.length})</span>
                </h4>
                <span style="font-size: 0.775rem; color: var(--text-muted);">Synced from mobile app / drive</span>
              </div>
              <div class="table-responsive" style="border: 1px solid var(--border-color); border-radius: 6px; overflow: hidden;">
                <table class="crm-table" style="font-size: 0.8125rem; width: 100%; margin: 0; background: var(--bg-card);">
                  <thead style="background: var(--bg-body);">
                    <tr>
                      <th style="padding: 8px 12px; font-weight: 600;">Date &amp; Time</th>
                      <th style="padding: 8px 12px; font-weight: 600;">Telecaller</th>
                      <th style="padding: 8px 12px; font-weight: 600;">Duration</th>
                      <th style="padding: 8px 12px; font-weight: 600;">Outcome</th>
                      <th style="padding: 8px 12px; font-weight: 600;">Notes</th>
                      <th style="padding: 8px 12px; font-weight: 600;">Recording Playback</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${rowsHtml}
                  </tbody>
                </table>
              </div>
            </div>
          `;
        } else {
          recentCallsWrap.innerHTML = `
            <div style="background: var(--bg-body); border: 1px dashed var(--border-color); padding: 14px 20px; text-align: center; border-radius: 8px; color: var(--text-muted); font-size: 0.825rem; margin-top: 16px;">
              No previous call recordings found for this lead yet. Newly synced calls will appear here automatically.
            </div>
          `;
        }
      }
    })
    .catch(err => console.warn('Could not load modal lead details:', err));
  };

  window.toggleModalEmptyFields = function () {
    const compForm = document.getElementById('dialer-completion-form');
    if (!compForm) return;
    const isHidden = compForm.classList.toggle('hide-empty-active');
    const label = document.getElementById('modalEmptyToggleLabel');
    const chevron = document.getElementById('modalEmptyToggleChevron');
    if (label) label.textContent = isHidden ? 'Show Empty Fields' : 'Hide Empty Fields';
    if (chevron) chevron.textContent = isHidden ? '▼ Show all' : '▲ Show less';
  };

  window.updateModalStatusPill = function (newStatus) {
    const label = document.getElementById('modalStatusLabel');
    if (label) label.textContent = newStatus;

    const leadStatusSelect = document.getElementById('call-form-lead-status');
    if (leadStatusSelect) leadStatusSelect.value = newStatus;

    if (currentActiveLeadId) {
      const csrf = getCookie('csrftoken') || '';
      fetch('/leads/api/update-status/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrf,
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({
          lead_id: currentActiveLeadId,
          new_status: newStatus,
          remarks: 'Updated via Call Completion Interface'
        })
      }).catch(err => console.warn('Status quick-sync error:', err));
    }
  };

  // Bind 5-Star Priority Rating in Modal
  document.addEventListener('DOMContentLoaded', function () {
    const modalStars = document.querySelectorAll('#modalStarRating .star');
    modalStars.forEach(star => {
      star.addEventListener('click', function () {
        const rating = parseInt(this.getAttribute('data-rating') || '0', 10);
        modalStars.forEach(s => {
          const r = parseInt(s.getAttribute('data-rating') || '0', 10);
          if (r <= rating) {
            s.classList.add('filled');
          } else {
            s.classList.remove('filled');
          }
        });
      });
    });
  });

  // Bind Call Notes Completion Form
  const completionForm = document.getElementById('call-notes-completion-form');
  if (completionForm) {
    completionForm.addEventListener('submit', function (e) {
      const notesInput = document.getElementById('call-form-notes');
      const notesErr = document.getElementById('call-form-notes-error');
      const notesVal = (notesInput ? notesInput.value : '').trim();

      if (!notesVal) {
        e.preventDefault();
        if (notesErr) {
          notesErr.textContent = 'Call Notes are required before completing this call.';
          notesErr.style.display = 'block';
        }
        if (notesInput) notesInput.focus();
        return false;
      }
      if (notesErr) notesErr.style.display = 'none';

      const leadInput = document.getElementById('call-form-lead-id');
      const callInput = document.getElementById('call-form-call-id');
      const leadVal = (leadInput ? leadInput.value : '').trim();
      const callVal = (callInput ? callInput.value : '').trim();
      if (!leadVal && !callVal) {
        e.preventDefault();
        alert('Cannot save call notes: No active lead or call record associated with this form.');
        return false;
      }

      e.preventDefault();
      const submitBtn = document.getElementById('save-call-notes-btn');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Saving Call Notes...';
      }

      const formData = new FormData(completionForm);
      fetch('/calls/complete/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCookie('csrftoken') || '',
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: formData
      })
      .then(r => r.json().then(data => ({ status: r.status, ok: r.ok, data: data })))
      .then(res => {
        if (!res.ok || !res.data.success) {
          if (notesErr) {
            notesErr.textContent = res.data.error || 'Failed to save call notes.';
            notesErr.style.display = 'block';
          } else {
            alert(res.data.error || 'Failed to save call notes.');
          }
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Save Call Notes & Outcome';
          }
          return;
        }

        // Unlocked!
        currentActiveCallId = null;
        currentActiveLeadId = null;
        const dialerCard = document.querySelector('.dialer-card');
        if (dialerCard) dialerCard.classList.remove('dialer-card-lead-details');
        const overlay = document.getElementById('call-dialer-overlay');
        if (overlay) overlay.classList.remove('active');
        alert('✓ ' + (res.data.message || 'Call notes saved successfully. You can now call another lead.'));
        if (res.data && res.data.redirect_url) {
          window.location.href = res.data.redirect_url;
        } else {
          window.location.reload();
        }
      })
      .catch(err => {
        console.error('Call completion error:', err);
        alert('An unexpected error occurred while saving call notes.');
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Save Call Notes & Outcome';
        }
      });
    });
  }

  const notifBellBtn = document.getElementById('notification-bell-btn');
  const notifPanel = document.getElementById('notification-panel');
  const notifContainer = document.getElementById('notification-items-container');
  const notifBadge = document.getElementById('notif-badge-count');
  const markAllReadBtn = document.getElementById('mark-all-read-btn');

  function renderNotifications(items) {
    if (!notifContainer) return;
    if (!items || items.length === 0) {
      notifContainer.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--text-muted); font-size: 0.85rem;">No notifications right now.</div>';
      return;
    }
    let html = '';
    items.forEach(function (n) {
      const bg = n.is_read ? 'transparent' : 'rgba(37, 99, 235, 0.05)';
      html += `
        <div class="notif-item" data-id="${n.id}" style="padding: 10px 14px; border-bottom: 1px solid var(--border-color); background: ${bg}; display: flex; justify-content: space-between; align-items: flex-start; gap: 10px;">
          <div style="flex: 1;">
            <div style="font-size: 0.825rem; font-weight: 600; color: var(--text-main); margin-bottom: 2px;">${n.title}</div>
            <div style="font-size: 0.775rem; color: var(--text-muted); line-height: 1.3; margin-bottom: 4px;">${n.message}</div>
            <div style="font-size: 0.7rem; color: var(--text-muted);">${n.timestamp}</div>
          </div>
          ${!n.is_read ? `<button type="button" class="btn-mark-single-read" data-id="${n.id}" style="background: none; border: none; color: var(--primary); font-size: 0.8rem; cursor: pointer; padding: 2px 6px; font-weight: bold;" title="Mark read">✓</button>` : ''}
        </div>
      `;
    });
    notifContainer.innerHTML = html;
  }

  // Real-Time Notification Polling, Web Audio Chime & In-App Toast
  let lastUnreadCount = 0;
  let isInitialNotifLoad = true;

  function playNotificationChime() {
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) return;
      const ctx = new AudioContext();
      if (ctx.state === 'suspended') {
        ctx.resume();
      }

      // 2-tone melodic chime: C6 (1046Hz) -> E6 (1318Hz)
      const now = ctx.currentTime;
      const osc1 = ctx.createOscillator();
      const gain1 = ctx.createGain();
      osc1.type = 'sine';
      osc1.frequency.setValueAtTime(1046.50, now);
      gain1.gain.setValueAtTime(0.08, now);
      gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.28);
      osc1.connect(gain1);
      gain1.connect(ctx.destination);
      osc1.start(now);
      osc1.stop(now + 0.3);

      const osc2 = ctx.createOscillator();
      const gain2 = ctx.createGain();
      osc2.type = 'sine';
      osc2.frequency.setValueAtTime(1318.51, now + 0.12);
      gain2.gain.setValueAtTime(0.09, now + 0.12);
      gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.55);
      osc2.connect(gain2);
      gain2.connect(ctx.destination);
      osc2.start(now + 0.12);
      osc2.stop(now + 0.6);
    } catch (e) {
      console.warn('Audio chime note error:', e);
    }
  }

  function showNotificationToast(notif) {
    let toastContainer = document.getElementById('tp-toast-container');
    if (!toastContainer) {
      toastContainer = document.createElement('div');
      toastContainer.id = 'tp-toast-container';
      toastContainer.style.cssText = 'position: fixed; bottom: 24px; right: 24px; z-index: 99999; display: flex; flex-direction: column; gap: 10px; max-width: 360px; pointer-events: none;';
      document.body.appendChild(toastContainer);
    }

    const toast = document.createElement('div');
    toast.className = 'tp-live-toast';
    toast.style.cssText = 'background: var(--bg-card, #ffffff); color: var(--text-main, #0f172a); border-left: 4px solid #2563eb; border-radius: 8px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.2), 0 8px 10px -6px rgba(0,0,0,0.1); padding: 14px 16px; font-size: 0.85rem; pointer-events: auto; display: flex; flex-direction: column; gap: 4px; animation: slideInToast 0.3s cubic-bezier(0.16, 1, 0.3, 1); border: 1px solid var(--border-color, #e2e8f0); border-left: 4px solid #2563eb;';

    toast.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;">
        <div style="font-weight: 700; color: #2563eb; font-size: 0.875rem; display: flex; align-items: center; gap: 6px;">
          <span>🔔</span>
          <span>${notif.title || 'New Notification'}</span>
        </div>
        <button type="button" class="btn-close-toast" style="background: none; border: none; cursor: pointer; color: var(--text-muted, #64748b); font-size: 1.1rem; line-height: 1; padding: 0;">&times;</button>
      </div>
      <div style="color: var(--text-muted, #475569); line-height: 1.4; font-size: 0.825rem;">
        ${notif.message || ''}
      </div>
      ${notif.link ? `<div style="margin-top: 6px;"><a href="${notif.link}" class="btn btn-sm btn-primary" style="padding: 3px 10px; font-size: 0.775rem; text-decoration: none; border-radius: 4px; display: inline-block;">Open Lead</a></div>` : ''}
    `;

    toast.querySelector('.btn-close-toast').onclick = function () {
      toast.remove();
    };

    toastContainer.appendChild(toast);

    setTimeout(() => {
      if (toast.parentNode) {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.4s ease';
        setTimeout(() => toast.remove(), 400);
      }
    }, 6500);
  }

  function loadNotifications(isBackgroundPoll = false) {
    fetch('/notifications/latest/')
      .then(r => r.json())
      .then(data => {
        const unreadCount = data.unread_count || 0;
        if (notifBadge) {
          notifBadge.textContent = unreadCount;
          notifBadge.style.display = unreadCount > 0 ? 'inline-block' : 'none';
        }
        
        if (isBackgroundPoll && !isInitialNotifLoad && unreadCount > lastUnreadCount) {
          playNotificationChime();
          if (data.notifications && data.notifications.length > 0) {
            const newest = data.notifications[0];
            if (!newest.is_read) {
              showNotificationToast(newest);
            }
          }
        }
        
        lastUnreadCount = unreadCount;
        isInitialNotifLoad = false;
        renderNotifications(data.notifications);
      })
      .catch(err => console.warn('Failed to load notifications:', err));
  }

  // Load immediately on page open
  loadNotifications(false);

  // Poll in background every 12 seconds
  setInterval(() => {
    loadNotifications(true);
  }, 12000);

  if (notifBellBtn && notifPanel) {
    notifBellBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      if (window.dismissAllCustomDropdowns) {
        window.dismissAllCustomDropdowns();
      }
      const isVisible = notifPanel.style.display === 'flex';
      if (isVisible) {
        notifPanel.style.display = 'none';
      } else {
        notifPanel.style.display = 'flex';
        loadNotifications(false);
      }
    });

    document.addEventListener('click', function (e) {
      if (!notifPanel.contains(e.target) && e.target !== notifBellBtn) {
        notifPanel.style.display = 'none';
      }
    });
  }

  if (markAllReadBtn) {
    markAllReadBtn.addEventListener('click', function (e) {
      e.preventDefault();
      fetch('/notifications/mark-all-read/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCookie('csrftoken') || '',
          'Content-Type': 'application/json'
        }
      })
      .then(r => r.json())
      .then(() => {
        if (notifBadge) {
          notifBadge.textContent = '0';
          notifBadge.style.display = 'none';
        }
        lastUnreadCount = 0;
        loadNotifications(false);
      });
    });
  }

  if (notifContainer) {
    notifContainer.addEventListener('click', function (e) {
      const markBtn = e.target.closest('.btn-mark-single-read');
      if (markBtn) {
        e.stopPropagation();
        const notifId = markBtn.getAttribute('data-id');
        fetch(`/notifications/${notifId}/mark-read/`, {
          method: 'POST',
          headers: {
            'X-CSRFToken': getCookie('csrftoken') || '',
            'Content-Type': 'application/json'
          }
        })
        .then(r => r.json())
        .then(() => loadNotifications(false));
      }
    });
  }

  // Universal Form Submit Protection & Loading Indicators
  document.addEventListener('submit', function (e) {
    const form = e.target;
    if (!form || form.tagName !== 'FORM') return;

    if (form.hasAttribute('data-no-loading') || e.defaultPrevented) return;

    if (typeof form.checkValidity === 'function' && !form.checkValidity()) {
      return;
    }

    const submitBtn = form.querySelector('button[type="submit"]:not([data-no-loading]), input[type="submit"]:not([data-no-loading])');
    if (submitBtn) {
      submitBtn.classList.add('is-loading');
      setTimeout(function () {
        submitBtn.disabled = true;
      }, 20);
    }
  });

  // Dedicated Logout Exit Animation Interceptor
  document.addEventListener('click', function (e) {
    const logoutLink = e.target.closest('.tp-logout-trigger, a[href*="/logout/"]');
    if (!logoutLink) return;

    // If user clicked with modifier keys (Ctrl/Cmd for new tab), let default behavior happen
    if (e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return;

    const overlay = document.getElementById('tp-logout-overlay');
    if (!overlay) return;

    e.preventDefault();
    const targetUrl = logoutLink.getAttribute('href');

    overlay.style.display = 'flex';
    const progressFill = document.getElementById('tp-logout-progress-fill');
    
    // Trigger smooth progress bar animation
    setTimeout(function () {
      if (progressFill) progressFill.style.width = '100%';
    }, 40);

    // Gracefully navigate to logout endpoint after animation
    setTimeout(function () {
      window.location.href = targetUrl;
    }, 800);
  });


  // 1.3 Interactive 3D Perspective Card Tilt Engine (60fps requestAnimationFrame)
  function init3DCardTiltEngine() {
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return;
    }

    const cards = document.querySelectorAll('.tp-kpi-card, .kpi-card, .tp-3d-card');
    cards.forEach(function (card) {
      if (card.dataset.has3dTilt) return;
      card.dataset.has3dTilt = 'true';

      // Insert dynamic specular light glare if not present
      if (!card.querySelector('.tp-3d-glare')) {
        const glare = document.createElement('div');
        glare.className = 'tp-3d-glare';
        card.appendChild(glare);
      }

      let rafId = null;

      function onMouseMove(e) {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        const rotateX = (((y - centerY) / centerY) * -8).toFixed(2);
        const rotateY = (((x - centerX) / centerX) * 8).toFixed(2);

        if (rafId) cancelAnimationFrame(rafId);
        rafId = requestAnimationFrame(function () {
          card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateZ(10px)`;
          card.style.setProperty('--glare-x', `${((x / rect.width) * 100).toFixed(1)}%`);
          card.style.setProperty('--glare-y', `${((y / rect.height) * 100).toFixed(1)}%`);
        });
      }

      function onMouseLeave() {
        if (rafId) cancelAnimationFrame(rafId);
        rafId = requestAnimationFrame(function () {
          card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateZ(0)';
        });
      }

      card.addEventListener('mousemove', onMouseMove, { passive: true });
      card.addEventListener('mouseleave', onMouseLeave, { passive: true });
    });
  }

  // Auto-init 3D Card Tilt on DOM load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init3DCardTiltEngine);
  } else {
    init3DCardTiltEngine();
  }

})();
