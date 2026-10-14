/**
 * TECHPANDA CRM - Enhanced Data Tables & Floating Bulk Actions Dock
 * Multi-select row tracking, optimistic UI updates, and atomic backend bulk operations.
 */
(function () {
  'use strict';

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

  function initEnhancedTables() {
    var selectAll = document.getElementById('select-all-leads');
    var rowCheckboxes = document.querySelectorAll('.lead-row-select');
    var dock = document.getElementById('tp-bulk-actions-dock');
    var countEl = document.getElementById('selected-leads-count');
    var clearBtn = document.getElementById('btn-clear-selection');
    var applyStatusBtn = document.getElementById('btn-apply-bulk-status');
    var statusSelect = document.getElementById('bulk-status-select');

    if (!rowCheckboxes.length) return;

    function getSelectedIds() {
      var ids = [];
      rowCheckboxes.forEach(function (cb) {
        if (cb.checked) {
          ids.push(parseInt(cb.value, 10));
        }
      });
      return ids;
    }

    function updateDock() {
      var ids = getSelectedIds();
      if (countEl) {
        if (window.selectAllMatchingFilters) {
          // Keep filtered count displayed
        } else {
          countEl.textContent = ids.length;
        }
      }

      var banner = document.getElementById('select-all-matching-banner');
      if (banner) {
        if (ids.length === rowCheckboxes.length && rowCheckboxes.length > 0) {
          banner.style.display = 'block';
        } else {
          banner.style.display = 'none';
          if (window.toggleSelectAllMatching) window.toggleSelectAllMatching(false);
        }
      }

      if (dock) {
        if (ids.length > 0 || window.selectAllMatchingFilters) {
          dock.style.display = 'flex';
        } else {
          dock.style.display = 'none';
        }
      }

      if (selectAll) {
        selectAll.checked = (ids.length === rowCheckboxes.length && rowCheckboxes.length > 0);
        selectAll.indeterminate = (ids.length > 0 && ids.length < rowCheckboxes.length);
      }
    }

    if (selectAll) {
      selectAll.addEventListener('change', function () {
        var isChecked = selectAll.checked;
        rowCheckboxes.forEach(function (cb) {
          cb.checked = isChecked;
        });
        updateDock();
      });
    }

    rowCheckboxes.forEach(function (cb) {
      cb.addEventListener('change', updateDock);
    });

    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        rowCheckboxes.forEach(function (cb) {
          cb.checked = false;
        });
        if (selectAll) {
          selectAll.checked = false;
          selectAll.indeterminate = false;
        }
        updateDock();
      });
    }

    if (applyStatusBtn && statusSelect) {
      applyStatusBtn.addEventListener('click', function () {
        var newStatus = statusSelect.value;
        if (!newStatus) {
          alert('Please select a target status from the dropdown.');
          return;
        }

        var ids = getSelectedIds();
        if (ids.length === 0) {
          alert('No leads selected.');
          return;
        }

        applyStatusBtn.disabled = true;
        applyStatusBtn.textContent = 'Updating...';

        var csrfToken = getCookie('csrftoken') || '';

        fetch('/leads/api/bulk-action/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest'
          },
          body: JSON.stringify({
            action: 'status_update',
            lead_ids: ids,
            new_status: newStatus
          })
        })
        .then(function (res) {
          return res.json().then(function (data) {
            return { ok: res.ok, status: res.status, data: data };
          });
        })
        .then(function (result) {
          applyStatusBtn.disabled = false;
          applyStatusBtn.textContent = 'Apply Status';

          if (!result.ok || !result.data.success) {
            throw new Error(result.data.error || 'Bulk update failed');
          }

          showToast('Updated ' + result.data.updated_count + ' leads to ' + newStatus, false);

          // Update badges in table for checked rows
          rowCheckboxes.forEach(function (cb) {
            if (cb.checked) {
              var tr = cb.closest('tr');
              if (tr) {
                var badge = tr.querySelector('.badge[class*="badge-"]');
                if (badge) {
                  badge.textContent = newStatus;
                }
              }
            }
          });

          // Reset selection
          if (clearBtn) clearBtn.click();
        })
        .catch(function (err) {
          applyStatusBtn.disabled = false;
          applyStatusBtn.textContent = 'Apply Status';
          showToast(err.message || 'Error executing bulk action', true);
        });
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initEnhancedTables);
  } else {
    initEnhancedTables();
  }
})();
