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
        var countSpan = badge.querySelector('.count-val');
        if (countSpan) {
          countSpan.textContent = cards.length;
        } else {
          badge.textContent = cards.length;
        }
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

  function getGhostPlaceholder() {
    var placeholder = document.getElementById('tp-kanban-ghost');
    if (!placeholder) {
      placeholder = document.createElement('div');
      placeholder.id = 'tp-kanban-ghost';
      placeholder.className = 'tp-kanban-ghost-placeholder';
    }
    return placeholder;
  }

  function removeGhostPlaceholder() {
    var placeholder = document.getElementById('tp-kanban-ghost');
    if (placeholder && placeholder.parentNode) {
      placeholder.parentNode.removeChild(placeholder);
    }
  }

  function getDragAfterElement(container, y) {
    var draggableElements = Array.prototype.slice.call(container.querySelectorAll('.tp-kanban-card:not(.is-dragging)'));

    return draggableElements.reduce(function (closest, child) {
      var box = child.getBoundingClientRect();
      var offset = y - box.top - box.height / 2;
      if (offset < 0 && offset > closest.offset) {
        return { offset: offset, element: child };
      } else {
        return closest;
      }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
  }

  function initKanban() {
    var cards = document.querySelectorAll('.tp-kanban-card');
    var dropzones = document.querySelectorAll('.tp-kanban-dropzone');

    cards.forEach(function (card) {
      card.addEventListener('dragstart', function (e) {
        draggedCard = card;
        originContainer = card.parentElement;
        originNextSibling = card.nextElementSibling;
        
        // Add floating glass elevation class with micro-delay for clean drag preview
        setTimeout(function () {
          card.classList.add('is-dragging');
        }, 10);

        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', card.getAttribute('data-lead-id'));
      });

      card.addEventListener('dragend', function () {
        if (draggedCard) {
          draggedCard.classList.remove('is-dragging');
        }
        removeGhostPlaceholder();
        dropzones.forEach(function (z) { z.classList.remove('drag-active'); });
        draggedCard = null;
      });
    });

    dropzones.forEach(function (zone) {
      zone.addEventListener('dragover', function (e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        zone.classList.add('drag-active');

        if (!draggedCard) return;

        var ghost = getGhostPlaceholder();
        var afterElement = getDragAfterElement(zone, e.clientY);
        if (afterElement == null) {
          zone.appendChild(ghost);
        } else {
          zone.insertBefore(ghost, afterElement);
        }
      });

      zone.addEventListener('dragleave', function (e) {
        // Only remove if leaving the dropzone boundary entirely
        if (!zone.contains(e.relatedTarget)) {
          zone.classList.remove('drag-active');
        }
      });

      zone.addEventListener('drop', function (e) {
        e.preventDefault();
        zone.classList.remove('drag-active');

        if (!draggedCard) return;

        var ghost = document.getElementById('tp-kanban-ghost');
        var targetContainer = zone;
        var leadId = draggedCard.getAttribute('data-lead-id');
        var targetStatus = zone.getAttribute('data-target-status');
        var currentStatus = draggedCard.getAttribute('data-current-status');

        draggedCard.classList.remove('is-dragging');

        if (originContainer === targetContainer) {
          // Reordering within same column
          if (ghost && ghost.parentElement === targetContainer) {
            targetContainer.insertBefore(draggedCard, ghost);
          }
          removeGhostPlaceholder();
          return;
        }

        // 1. Optimistic UI update: place card where ghost was
        if (ghost && ghost.parentElement === targetContainer) {
          targetContainer.insertBefore(draggedCard, ghost);
        } else {
          targetContainer.appendChild(draggedCard);
        }
        removeGhostPlaceholder();
        updateColumnCounts();

        // Spring snap animation feedback
        draggedCard.style.animation = 'tpCardSnap 0.3s cubic-bezier(0.16, 1, 0.3, 1)';
        setTimeout(function () {
          if (draggedCard) draggedCard.style.animation = '';
        }, 320);

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
