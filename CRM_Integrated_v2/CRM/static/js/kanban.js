/**
 * TECHPANDA CRM - Interactive Kanban Pipeline Drag & Drop
 * Handles HTML5 drag-and-drop, optimistic visual updates, CSRF authenticated
 * status transitions via /leads/api/update-status/, and instant rollback on failure.
 */
(function () {
  'use strict';

  var draggedCard = null;
  var originContainer = null;
  var originNextSibling = null;

  function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      var cookies = document.cookie.split(';');
      for (var i = 0; i < cookies.length; i++) {
        var cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  function updateColumnCounts() {
    var columns = document.querySelectorAll('.tp-kanban-column');
    columns.forEach(function (col) {
      var colId = col.getAttribute('data-column-id');
      var cards = col.querySelectorAll('.tp-kanban-card');
      var badge = document.getElementById('count-' + colId);
      if (badge) {
        badge.textContent = cards.length;
      }
      var emptySlot = col.querySelector('.tp-kanban-empty-slot');
      if (emptySlot) {
        emptySlot.style.display = cards.length === 0 ? 'block' : 'none';
      }
    });
  }

  function showToast(message, isError) {
    var toast = document.createElement('div');
    toast.style.position = 'fixed';
    toast.style.bottom = '24px';
    toast.style.left = '50%';
    toast.style.transform = 'translateX(-50%)';
    toast.style.background = isError ? '#ef4444' : '#10b981';
    toast.style.color = '#ffffff';
    toast.style.padding = '10px 20px';
    toast.style.borderRadius = '8px';
    toast.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.2)';
    toast.style.fontSize = '0.88rem';
    toast.style.fontWeight = '600';
    toast.style.zIndex = '99999';
    toast.style.transition = 'opacity 0.3s ease';
    toast.textContent = message;

    document.body.appendChild(toast);
    setTimeout(function () {
      toast.style.opacity = '0';
      setTimeout(function () {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, 300);
    }, 3200);
  }

  function initKanban() {
    var cards = document.querySelectorAll('.tp-kanban-card');
    var dropzones = document.querySelectorAll('.tp-kanban-dropzone');

    cards.forEach(function (card) {
      card.addEventListener('dragstart', function (e) {
        draggedCard = card;
        originContainer = card.parentElement;
        originNextSibling = card.nextElementSibling;
        card.style.opacity = '0.5';
        card.style.transform = 'scale(0.98)';
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', card.getAttribute('data-lead-id'));
      });

      card.addEventListener('dragend', function () {
        if (draggedCard) {
          draggedCard.style.opacity = '1';
          draggedCard.style.transform = 'none';
        }
        draggedCard = null;
      });
    });

    dropzones.forEach(function (zone) {
      zone.addEventListener('dragover', function (e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        zone.style.background = 'var(--tp-surface-card-hover)';
        zone.style.borderRadius = 'var(--tp-radius-md)';
      });

      zone.addEventListener('dragleave', function () {
        zone.style.background = 'transparent';
      });

      zone.addEventListener('drop', function (e) {
        e.preventDefault();
        zone.style.background = 'transparent';

        if (!draggedCard) return;

        var targetContainer = zone;
        var leadId = draggedCard.getAttribute('data-lead-id');
        var targetStatus = zone.getAttribute('data-target-status');
        var currentStatus = draggedCard.getAttribute('data-current-status');

        if (originContainer === targetContainer) {
          // Dropped in the same column
          return;
        }

        // 1. Optimistic UI update: move card to target column immediately
        targetContainer.appendChild(draggedCard);
        updateColumnCounts();

        // 2. Fire backend transition API
        var csrfToken = getCookie('csrftoken') || '';

        fetch('/leads/api/update-status/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest'
          },
          body: JSON.stringify({
            lead_id: leadId,
            new_status: targetStatus,
            remarks: 'Moved to ' + targetStatus + ' via Kanban Board'
          })
        })
        .then(function (res) {
          return res.json().then(function (data) {
            return { ok: res.ok, status: res.status, data: data };
          });
        })
        .then(function (result) {
          if (!result.ok || !result.data.success) {
            throw new Error(result.data.error || 'Failed to update lead status');
          }

          // Successfully updated: update badges
          draggedCard.setAttribute('data-current-status', result.data.new_status);
          var badge = draggedCard.querySelector('.tp-palette-badge');
          if (badge) {
            badge.textContent = result.data.new_status;
          }

          var msg = 'Lead status updated to ' + result.data.new_status;
          if (result.data.assigned_counselor) {
            msg += ' (Assigned to ' + result.data.assigned_counselor + ')';
          }
          showToast(msg, false);
        })
        .catch(function (err) {
          // 3. Rollback on failure: restore card to original container
          if (originNextSibling && originNextSibling.parentElement === originContainer) {
            originContainer.insertBefore(draggedCard, originNextSibling);
          } else {
            originContainer.appendChild(draggedCard);
          }
          updateColumnCounts();
          showToast(err.message || 'Permission denied or update failed.', true);
        });
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initKanban);
  } else {
    initKanban();
  }
})();
