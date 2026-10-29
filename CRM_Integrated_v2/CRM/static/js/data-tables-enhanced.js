/**
 * TECHPANDA CRM - Enhanced Data Tables & Floating Bulk Actions Dock
 * Multi-select row tracking, persistent cross-page selection via sessionStorage,
 * optimistic UI updates, and atomic backend bulk operations.
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'crm_bulk_selected_lead_ids';

  var CRMSelectionManager = {
    getStoredIds: function () {
      try {
        var raw = sessionStorage.getItem(STORAGE_KEY);
        if (!raw) return [];
        var parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          return parsed.map(function (id) { return parseInt(id, 10); }).filter(function (id) { return !isNaN(id); });
        }
      } catch (e) {
        console.warn('Failed to parse selected lead IDs from sessionStorage', e);
      }
      return [];
    },
    saveStoredIds: function (ids) {
      try {
        var unique = [];
        var seen = {};
        for (var i = 0; i < ids.length; i++) {
          var num = parseInt(ids[i], 10);
          if (!isNaN(num) && !seen[num]) {
            seen[num] = true;
            unique.push(num);
          }
        }
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(unique));
        return unique;
      } catch (e) {
        console.warn('Failed to save selected lead IDs to sessionStorage', e);
        return ids;
      }
    },
    addId: function (id) {
      var ids = this.getStoredIds();
      var num = parseInt(id, 10);
      if (!isNaN(num) && ids.indexOf(num) === -1) {
        ids.push(num);
        this.saveStoredIds(ids);
      }
      return ids;
    },
    removeId: function (id) {
      var ids = this.getStoredIds();
      var num = parseInt(id, 10);
      var filtered = ids.filter(function (item) { return item !== num; });
      this.saveStoredIds(filtered);
      return filtered;
    },
    addMultiple: function (newIds) {
      var ids = this.getStoredIds();
      for (var i = 0; i < newIds.length; i++) {
        var num = parseInt(newIds[i], 10);
        if (!isNaN(num) && ids.indexOf(num) === -1) {
          ids.push(num);
        }
      }
      this.saveStoredIds(ids);
      return ids;
    },
    removeMultiple: function (delIds) {
      var ids = this.getStoredIds();
      var delMap = {};
      for (var i = 0; i < delIds.length; i++) {
        delMap[parseInt(delIds[i], 10)] = true;
      }
      var filtered = ids.filter(function (item) { return !delMap[item]; });
      this.saveStoredIds(filtered);
      return filtered;
    },
    clear: function () {
      try {
        sessionStorage.removeItem(STORAGE_KEY);
      } catch (e) {}
    },
    getCount: function () {
      return this.getStoredIds().length;
    }
  };

  // Expose globally
  window.CRMSelectionManager = CRMSelectionManager;
  window.getSelectedLeadIds = function () {
    return CRMSelectionManager.getStoredIds();
  };

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

    if (!rowCheckboxes.length && !dock) return;

    // Synchronize page checkboxes with sessionStorage
    var storedIds = CRMSelectionManager.getStoredIds();
    var storedSet = {};
    for (var s = 0; s < storedIds.length; s++) {
      storedSet[storedIds[s]] = true;
    }

    rowCheckboxes.forEach(function (cb) {
      var id = parseInt(cb.value, 10);
      if (storedSet[id]) {
        cb.checked = true;
      }
    });

    function updateDock() {
      var currentStored = CRMSelectionManager.getStoredIds();
      var totalCount = currentStored.length;

      var checkedOnPage = 0;
      rowCheckboxes.forEach(function (cb) {
        if (cb.checked) checkedOnPage++;
      });

      if (countEl) {
        if (window.selectAllMatchingFilters) {
          // Keep filtered count displayed
        } else {
          countEl.textContent = totalCount;
        }
      }

      var banner = document.getElementById('select-all-matching-banner');
      if (banner) {
        if (checkedOnPage === rowCheckboxes.length && rowCheckboxes.length > 0) {
          banner.style.display = 'block';
        } else {
          banner.style.display = 'none';
          if (window.toggleSelectAllMatching) window.toggleSelectAllMatching(false);
        }
      }

      if (dock) {
        if (totalCount > 0 || window.selectAllMatchingFilters) {
          dock.style.display = 'flex';
        } else {
          dock.style.display = 'none';
        }
      }

      if (selectAll) {
        selectAll.checked = (checkedOnPage === rowCheckboxes.length && rowCheckboxes.length > 0);
        selectAll.indeterminate = (checkedOnPage > 0 && checkedOnPage < rowCheckboxes.length);
      }
    }

    // Initial dock update on page render
    updateDock();

    if (selectAll) {
      selectAll.addEventListener('change', function () {
        var isChecked = selectAll.checked;
        var pageIds = [];
        rowCheckboxes.forEach(function (cb) {
          cb.checked = isChecked;
          var num = parseInt(cb.value, 10);
          if (!isNaN(num)) pageIds.push(num);
        });
        if (isChecked) {
          CRMSelectionManager.addMultiple(pageIds);
        } else {
          CRMSelectionManager.removeMultiple(pageIds);
        }
        updateDock();
      });
    }

    rowCheckboxes.forEach(function (cb) {
      cb.addEventListener('change', function () {
        var id = parseInt(cb.value, 10);
        if (cb.checked) {
          CRMSelectionManager.addId(id);
        } else {
          CRMSelectionManager.removeId(id);
        }
        updateDock();
      });
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
        CRMSelectionManager.clear();
        if (window.toggleSelectAllMatching) window.toggleSelectAllMatching(false);
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

        var ids = CRMSelectionManager.getStoredIds();
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
