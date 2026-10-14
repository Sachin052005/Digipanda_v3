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
    localStorage.setItem(THEME_KEY, theme);
    if (themeToggleBtn) {
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

  const savedTheme = localStorage.getItem(THEME_KEY) || 'light';
  applyTheme(savedTheme);

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', function () {
      const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
      applyTheme(newTheme);
    });
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
    if (dialerCard) dialerCard.classList.remove('dialer-card-lead-details');

    document.getElementById('dialer-lead-name').textContent = leadName;
    document.getElementById('dialer-lead-phone').textContent = leadPhone;
    document.getElementById('dialer-timer-display').textContent = '00:00';
    document.getElementById('dialer-calling-state').style.display = 'block';
    document.getElementById('dialer-completion-form').style.display = 'none';

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
          if (!statusText || currentActiveCallId !== callId) return;

          // Device connectivity alert
          if (!st.has_device || !st.is_online) {
            statusText.textContent = '⚠️ Connection lost — reconnect CRM CallSync app on mobile';
            if (statusBox) {
              statusBox.style.background = '#fef2f2';
              statusBox.style.borderColor = '#fca5a5';
              statusBox.style.color = '#b91c1c';
            }
          }

          const callStatus = st.call_status;

          // 1. QUEUED / DISPATCHED
          if (callStatus === 'Queued' || (!callStatus && st.is_dispatched)) {
            if (stateBadge) stateBadge.textContent = 'Queued for phone…';
            if (statusText && st.is_online) {
              statusText.textContent = st.is_dispatched ? '✓ Call received by phone — dialing now!' : 'Waiting for phone to pick up request…';
              if (statusBox && st.is_dispatched) {
                statusBox.style.background = '#eff6ff';
                statusBox.style.borderColor = '#93c5fd';
                statusBox.style.color = '#1d4ed8';
              }
            }
            const timerEl = document.getElementById('dialer-timer-display');
            if (timerEl) timerEl.textContent = '00:00';
          }
          // 2. DIALING
          else if (callStatus === 'Dialing') {
            if (stateBadge) stateBadge.textContent = 'Dialing…';
            if (statusText) {
              statusText.textContent = 'Dialing number on mobile device…';
              if (statusBox) {
                statusBox.style.background = '#eff6ff';
                statusBox.style.borderColor = '#bfdbfe';
                statusBox.style.color = '#1d4ed8';
              }
            }
            const timerEl = document.getElementById('dialer-timer-display');
            if (timerEl) timerEl.textContent = '00:00';
          }
          // 3. RINGING
          else if (callStatus === 'Ringing') {
            if (stateBadge) stateBadge.textContent = 'Ringing…';
            if (statusText) {
              statusText.textContent = 'Recipient phone is ringing…';
              if (statusBox) {
                statusBox.style.background = '#fef3c7';
                statusBox.style.borderColor = '#fcd34d';
                statusBox.style.color = '#b45309';
              }
            }
            const timerEl = document.getElementById('dialer-timer-display');
            if (timerEl) timerEl.textContent = '00:00';
          }
          // 4. IN PROGRESS (Answered!)
          else if (callStatus === 'In Progress') {
            if (stateBadge) {
              stateBadge.textContent = 'Call Connected';
              stateBadge.style.color = '#16a34a';
            }
            if (statusText) {
              statusText.textContent = 'Call connected — conversation in progress';
              if (statusBox) {
                statusBox.style.background = '#dcfce7';
                statusBox.style.borderColor = '#86efac';
                statusBox.style.color = '#15803d';
              }
            }

            // Sync authoritative server duration & start local ticking if not already running
            if (typeof st.elapsed_seconds === 'number' && st.elapsed_seconds >= 0) {
              callSeconds = st.elapsed_seconds;
              const timerEl = document.getElementById('dialer-timer-display');
              if (timerEl) timerEl.textContent = formatDuration(callSeconds);
            }

            if (!isTimerActive) {
              isTimerActive = true;
              if (callTimerInterval) clearInterval(callTimerInterval);
              callTimerInterval = setInterval(function () {
                callSeconds++;
                const timerEl = document.getElementById('dialer-timer-display');
                if (timerEl) timerEl.textContent = formatDuration(callSeconds);
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

            const timerEl = document.getElementById('dialer-timer-display');
            if (timerEl) timerEl.textContent = formatDuration(callSeconds);

            // Transition to modern lead completion interface
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

    maximizeCallDock();

    // Call backend end endpoint
    const formData = new FormData();
    formData.append('duration', callSeconds);
    fetch(`/calls/${currentActiveCallId}/end/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken') || '',
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: formData
    }).catch(err => console.warn('Call end notify failed:', err));

    // Transition to modern lead completion interface
    showLeadCompletionInterface(callSeconds, 'Completed');
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
      notesInput.value = '';
      setTimeout(() => notesInput.focus(), 120);
    }

    if (currentActiveLeadId) {
      loadModalLeadDetails(currentActiveLeadId);
    }
  };

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
      if (phoneEl) phoneEl.textContent = data.phone || '-';

      const statusLabel = document.getElementById('modalStatusLabel');
      if (statusLabel) statusLabel.textContent = data.status || 'Contacted';

      const statusSelect = document.getElementById('modalStatusSelect');
      if (statusSelect && data.status) statusSelect.value = data.status;

      const leadStatusForm = document.getElementById('call-form-lead-status');
      if (leadStatusForm && data.status) leadStatusForm.value = data.status;

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

      // Populate field mapping
      const fieldMap = {
        'modal-field-degree': data.degree,
        'modal-field-passed-out': data.passed_out,
        'modal-field-branch': data.branch,
        'modal-field-working-status': data.working_status,
        'modal-field-assignee': data.assignee,
        'modal-field-join': data.joining_preference,
        'modal-field-source': data.source,
        'modal-field-retargeted': data.retargeted,
        'modal-field-captured-on': data.captured_on,
        'modal-field-pref-exam': data.pref_exam_location,
        'modal-field-purpose': data.purpose,
        'modal-field-pref-branch': data.pref_branch,
        'modal-field-experience': data.total_experience,
        'modal-field-college': data.college,
        'modal-field-frequency': data.capture_frequency,
        'modal-field-created-on': data.created_on,
        'modal-field-act-type': data.last_activity_type,
        'modal-field-courses': data.course_name,
        'modal-field-center-visit': data.center_visit_date
      };

      for (const [id, val] of Object.entries(fieldMap)) {
        const el = document.getElementById(id);
        if (!el) continue;
        const item = el.closest('.lead-field-item');
        const displayVal = (val && String(val).trim() !== '' && String(val).trim() !== '-') ? String(val).trim() : 'Empty';
        el.textContent = displayVal;

        if (displayVal === 'Empty') {
          el.classList.add('text-empty');
          if (item) item.classList.add('is-empty-field');
        } else {
          el.classList.remove('text-empty');
          if (item) item.classList.remove('is-empty-field');
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
            submitBtn.textContent = 'Save Call Notes';
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
        window.location.reload();
      })
      .catch(err => {
        console.error('Call completion error:', err);
        alert('An unexpected error occurred while saving call notes.');
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Save Call Notes';
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

  // Reset loading state on browser back/forward cache navigation
  window.addEventListener('pageshow', function (event) {
    if (event.persisted) {
      document.querySelectorAll('.btn.is-loading, .tp-btn.is-loading').forEach(function (btn) {
        btn.classList.remove('is-loading');
        btn.disabled = false;
      });
    }
  });

})();
