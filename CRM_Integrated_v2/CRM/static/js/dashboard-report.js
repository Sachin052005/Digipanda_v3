/**
 * TELE CRM - Marketing Performance Dashboard Client Orchestrator
 * Coordinates real-time Chart.js visualisations, asynchronous filter updates,
 * CSV export, and server-side Google Sheets synchronization.
 */
(function () {
  'use strict';

  var channelDonut = null;
  var branchStacked = null;
  var outcomesBar = null;

  var CHANNEL_COLORS = {
    'Meta WhatsApp': '#059669',
    'Meta Lead Form': '#0284c7',
    'Website (Google Ad)': '#f59e0b',
    'Website (Google SEO)': '#8b5cf6',
    'Instagram': '#ec4899',
    'Google Calls': '#10b981',
    'Influencer': '#6366f1',
    'Other': '#64748b',
  };

  function colorOf(channelName) {
    return CHANNEL_COLORS[channelName] || '#94a3b8';
  }

  function esc(s) {
    return String(s || '').replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function isDarkMode() {
    return document.documentElement.getAttribute('data-theme') === 'dark' ||
           document.body.classList.contains('dark-theme');
  }

  // =========================================================================
  // Chart.js Renderers
  // =========================================================================

  function renderChannelDonut(data) {
    var canvas = document.getElementById('channelDonutChart');
    if (!canvas) return;

    var center = document.getElementById('donutChannelTotal');
    if (center) center.textContent = (data.total || 0).toLocaleString();

    var labels = data.labels || [];
    var values = data.values || [];
    var colors = data.colors || labels.map(colorOf);

    // Render custom legend
    var legend = document.getElementById('channelCustomLegend');
    if (legend) {
      var html = '';
      for (var i = 0; i < labels.length; i++) {
        var chan = labels[i];
        var val = values[i] || 0;
        var pct = data.percentages && data.percentages[i] !== undefined ? data.percentages[i] : 0;
        html += '<div class="tp-legend-item">' +
          '<div class="tp-legend-label-wrap">' +
            '<span class="tp-legend-dot" style="background-color:' + colorOf(chan) + ';"></span>' +
            '<span>' + esc(chan) + '</span>' +
          '</div>' +
          '<span class="tp-legend-val">' + val.toLocaleString() + ' (' + pct + '%)</span>' +
        '</div>';
      }
      legend.innerHTML = html;
    }

    if (channelDonut) {
      channelDonut.data.labels = labels;
      channelDonut.data.datasets[0].data = values;
      channelDonut.data.datasets[0].backgroundColor = colors;
      channelDonut.update();
      return;
    }

    channelDonut = new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels: labels,
        datasets: [{
          data: values,
          backgroundColor: colors,
          borderWidth: 2,
          borderColor: isDarkMode() ? '#1e293b' : '#ffffff',
          hoverOffset: 4,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '72%',
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return ' ' + ctx.label + ': ' + (ctx.raw || 0).toLocaleString();
              },
            },
          },
        },
      },
    });
  }

  function renderBranchStacked(data) {
    var canvas = document.getElementById('branchStackedChart');
    if (!canvas) return;

    var labels = data.labels || [];
    var datasets = data.datasets || [];

    // Render bottom legend chips
    var legend = document.getElementById('branchStackedLegend');
    if (legend && datasets.length) {
      var html = '';
      for (var i = 0; i < datasets.length; i++) {
        var ds = datasets[i];
        html += '<div class="tp-stacked-legend-chip">' +
          '<span class="tp-legend-dot" style="background-color:' + ds.backgroundColor + ';"></span>' +
          '<span>' + esc(ds.label) + '</span>' +
        '</div>';
      }
      legend.innerHTML = html;
    }

    var textColor = isDarkMode() ? '#cbd5e1' : '#475569';
    var gridColor = isDarkMode() ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.05)';

    if (branchStacked) {
      branchStacked.data.labels = labels;
      branchStacked.data.datasets = datasets;
      branchStacked.update();
      return;
    }

    branchStacked = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: datasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            mode: 'index',
            intersect: false,
          },
        },
        scales: {
          x: {
            stacked: true,
            ticks: { color: textColor, font: { size: 11, weight: '500' } },
            grid: { display: false },
          },
          y: {
            stacked: true,
            beginAtZero: true,
            ticks: { color: textColor, precision: 0 },
            grid: { color: gridColor },
          },
        },
      },
    });
  }

  function renderOutcomesBar(data) {
    var canvas = document.getElementById('outcomesChart');
    if (!canvas) return;

    var labels = data.labels || [];
    var values = data.values || [];

    var bgColors = labels.map(function (label) {
      var l = label.toLowerCase();
      if (/not\s*connect|missed|no answer|not\s*reach|lost/.test(l)) return '#ef4444';
      if (/connect|completed|interested|converted/.test(l)) return '#10b981';
      if (/follow-up|callback/.test(l)) return '#f59e0b';
      return '#6366f1';
    });

    var textColor = isDarkMode() ? '#cbd5e1' : '#475569';
    var gridColor = isDarkMode() ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.05)';

    if (outcomesBar) {
      outcomesBar.data.labels = labels;
      outcomesBar.data.datasets[0].data = values;
      outcomesBar.data.datasets[0].backgroundColor = bgColors;
      outcomesBar.update();
      return;
    }

    outcomesBar = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          data: values,
          backgroundColor: bgColors,
          borderRadius: 4,
          maxBarThickness: 24,
        }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                var total = data.total || 0;
                var pct = total > 0 ? Math.round((ctx.raw / total) * 100) : 0;
                return ' ' + (ctx.raw || 0).toLocaleString() + ' (' + pct + '%)';
              },
            },
          },
        },
        scales: {
          x: {
            beginAtZero: true,
            ticks: { color: textColor, precision: 0 },
            grid: { color: gridColor },
          },
          y: {
            ticks: { color: textColor, font: { size: 11, weight: '500' } },
            grid: { display: false },
          },
        },
      },
    });
  }

  // =========================================================================
  // DOM Updates from State
  // =========================================================================

  function updateDashboardUI(data) {
    // 1. Period labels
    var periodEls = document.querySelectorAll('[data-period]');
    periodEls.forEach(function (el) {
      el.textContent = '(' + (data.period_label || 'Today') + ')';
    });

    // 2. Filter Pills labels
    var datePillLabel = document.getElementById('datePillLabel');
    if (datePillLabel) datePillLabel.textContent = data.period_label || 'Today';

    var branchPillText = document.getElementById('branchPillText');
    if (branchPillText) {
      var branchSelect = document.getElementById('branchFilter');
      var selectedText = branchSelect && branchSelect.selectedIndex >= 0 ?
                         branchSelect.options[branchSelect.selectedIndex].text : 'All Branches';
      branchPillText.textContent = selectedText;
    }

    var channelPillText = document.getElementById('channelPillText');
    if (channelPillText) {
      var channelSelect = document.getElementById('channelFilter');
      var selChan = channelSelect && channelSelect.selectedIndex >= 0 ?
                    channelSelect.options[channelSelect.selectedIndex].text : 'All Channels';
      channelPillText.textContent = selChan;
    }

    // 3. Top 4 Pastel KPI Cards
    var elTotal = document.getElementById('kpiTotalLeads');
    if (elTotal) elTotal.textContent = (data.kpi_total_leads || 0).toLocaleString();

    var elTotalPct = document.getElementById('kpiTotalPct');
    if (elTotalPct) {
      var change = data.kpi_total_change_pct || 0;
      elTotalPct.textContent = (change >= 0 ? '+' : '') + change + '%';
    }

    var elVal1 = document.getElementById('kpiVal1');
    if (elVal1) elVal1.textContent = (data.kpi_connected_leads || 0).toLocaleString();
    var elPct1 = document.getElementById('kpiPct1');
    if (elPct1) elPct1.textContent = (data.kpi_connected_pct || 0) + '%';

    var elVal2 = document.getElementById('kpiVal2');
    if (elVal2) elVal2.textContent = (data.kpi_prospected_leads || 0).toLocaleString();
    var elPct2 = document.getElementById('kpiPct2');
    if (elPct2) elPct2.textContent = (data.kpi_prospected_pct || 0) + '%';

    var elVal3 = document.getElementById('kpiVal3');
    if (elVal3) elVal3.textContent = (data.kpi_not_connected_leads || 0).toLocaleString();
    var elPct3 = document.getElementById('kpiPct3');
    if (elPct3) elPct3.textContent = (data.kpi_not_connected_pct || 0) + '%';

    // 4. Leads by Channel Cards
    if (data.channels && data.channels.length) {
      data.channels.forEach(function (c) {
        var countEl = document.querySelector('[data-chan-count="' + c.channel + '"]');
        if (countEl) countEl.textContent = (c.count || 0).toLocaleString();
        var pctEl = document.querySelector('[data-chan-pct="' + c.channel + '"]');
        if (pctEl) pctEl.textContent = (c.percentage || 0) + '%';
      });
    }

    // 5. Branch Wise Lead Summary Table Body
    var tbody = document.getElementById('branchTableBody');
    if (tbody && data.branch_rows) {
      var tbodyHtml = '';
      data.branch_rows.forEach(function (r) {
        tbodyHtml += '<tr>' +
          '<td class="td-branch">' + esc(r.branch) + '</td>' +
          '<td class="td-total">' + (r.total_leads || 0).toLocaleString() + '</td>' +
          '<td class="td-whatsapp">' + (r.channels[0] || 0) + '</td>' +
          '<td class="td-meta-form">' + (r.channels[1] || 0) + '</td>' +
          '<td class="td-ad">' + (r.channels[2] || 0) + '</td>' +
          '<td class="td-seo">' + (r.channels[3] || 0) + '</td>' +
          '<td class="td-ig">' + (r.channels[4] || 0) + '</td>' +
          '<td class="td-call">' + (r.channels[5] || 0) + '</td>' +
          '<td class="td-influencer">' + (r.channels[6] || 0) + '</td>' +
          '<td class="td-status-normal">' + (r.new_leads || 0) + '</td>' +
          '<td class="td-status-normal">' + (r.contacted_leads || 0) + '</td>' +
          '<td class="td-status-normal">' + (r.missed_leads || 0) + '</td>' +
        '</tr>';
      });
      tbody.innerHTML = tbodyHtml;
    }

    // 6. Branch Table Footer (Totals)
    var tfoot = document.getElementById('branchTableFooter');
    if (tfoot && data.branch_totals) {
      var bt = data.branch_totals;
      tfoot.innerHTML = '<td class="td-branch">Total</td>' +
        '<td class="td-total">' + (bt.total_leads || 0).toLocaleString() + '</td>' +
        '<td class="td-whatsapp">' + (bt.channels[0] || 0) + '</td>' +
        '<td class="td-meta-form">' + (bt.channels[1] || 0) + '</td>' +
        '<td class="td-ad">' + (bt.channels[2] || 0) + '</td>' +
        '<td class="td-seo">' + (bt.channels[3] || 0) + '</td>' +
        '<td class="td-ig">' + (bt.channels[4] || 0) + '</td>' +
        '<td class="td-call">' + (bt.channels[5] || 0) + '</td>' +
        '<td class="td-influencer">' + (bt.channels[6] || 0) + '</td>' +
        '<td class="td-status-normal">' + (bt.new_leads || 0) + '</td>' +
        '<td class="td-status-normal">' + (bt.contacted_leads || 0) + '</td>' +
        '<td class="td-status-normal">' + (bt.missed_leads || 0) + '</td>';
    }

    // 7. Update Charts
    if (data.donut_chart) renderChannelDonut(data.donut_chart);
    if (data.stacked_chart) renderBranchStacked(data.stacked_chart);
    if (data.outcomes_chart) renderOutcomesBar(data.outcomes_chart);
  }

  // =========================================================================
  // Asynchronous Fetch & Filter Handling
  // =========================================================================

  function fetchDashboardData() {
    var dateSelect = document.getElementById('dateFilter');
    var branchSelect = document.getElementById('branchFilter');
    var channelSelect = document.getElementById('channelFilter');
    var customStartDate = document.getElementById('customStartDate');
    var customEndDate = document.getElementById('customEndDate');

    var dateFilter = dateSelect ? dateSelect.value : 'today';
    var branch = branchSelect ? branchSelect.value : '';
    var channel = channelSelect ? channelSelect.value : '';
    var startDate = customStartDate ? customStartDate.value : '';
    var endDate = customEndDate ? customEndDate.value : '';

    var url = '/reports/api/data/?date_filter=' + encodeURIComponent(dateFilter) +
              '&branch=' + encodeURIComponent(branch) +
              '&channel=' + encodeURIComponent(channel) +
              '&start_date=' + encodeURIComponent(startDate) +
              '&end_date=' + encodeURIComponent(endDate);

    var syncText = document.getElementById('lastSyncText');
    if (syncText) syncText.textContent = 'Updating metrics…';

    fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP error ' + res.status);
        return res.json();
      })
      .then(function (data) {
        updateDashboardUI(data);
        if (syncText) syncText.textContent = 'Live CRM Database Active · ' + new Date().toLocaleTimeString();
      })
      .catch(function (err) {
        console.error('Failed to load dashboard data:', err);
        if (syncText) syncText.textContent = 'Update error. Retrying…';
      });
  }

  // =========================================================================
  // CSV Table Export
  // =========================================================================

  function exportTableToCSV() {
    var table = document.getElementById('branchSummaryTable');
    if (!table) return;

    var csv = [];
    var rows = table.querySelectorAll('tr');

    for (var i = 0; i < rows.length; i++) {
      var row = [], cols = rows[i].querySelectorAll('td, th');
      for (var j = 0; j < cols.length; j++) {
        var clean = cols[j].innerText.replace(/(\r\n|\n|\r)/gm, '').replace(/"/g, '""').trim();
        row.push('"' + clean + '"');
      }
      csv.push(row.join(','));
    }

    var csvFile = new Blob([csv.join('\n')], { type: 'text/csv' });
    var downloadLink = document.createElement('a');
    downloadLink.download = 'Branch_Wise_Lead_Summary_' + new Date().toISOString().slice(0, 10) + '.csv';
    downloadLink.href = window.URL.createObjectURL(csvFile);
    downloadLink.style.display = 'none';
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
  }

  // =========================================================================
  // CRM Database Refresh
  // =========================================================================

  function triggerSync() {
    var icon = document.getElementById('syncIcon');
    if (icon) icon.classList.add('fa-spin');

    var syncText = document.getElementById('lastSyncText');
    if (syncText) syncText.textContent = 'Querying CRM Application Database…';

    fetchDashboardData();

    setTimeout(function () {
      if (icon) icon.classList.remove('fa-spin');
    }, 600);
  }

  function getCsrfToken() {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      var cookies = document.cookie.split(';');
      for (var i = 0; i < cookies.length; i++) {
        var cookie = cookies[i].trim();
        if (cookie.substring(0, 10) === 'csrftoken=') {
          cookieValue = decodeURIComponent(cookie.substring(10));
          break;
        }
      }
    }
    return cookieValue || '';
  }

  // =========================================================================
  // Initialization
  // =========================================================================

  function init() {
    // 1. Render initial data from embedded JSON if present
    var dataScript = document.getElementById('initial-report-data');
    if (dataScript) {
      try {
        var initialData = JSON.parse(dataScript.textContent);
        if (initialData.donut_chart) renderChannelDonut(initialData.donut_chart);
        if (initialData.stacked_chart) renderBranchStacked(initialData.stacked_chart);
        if (initialData.outcomes_chart) renderOutcomesBar(initialData.outcomes_chart);
      } catch (e) {
        console.error('Error parsing initial report data:', e);
      }
    }

    // 2. Filter bindings
    var dateSelect = document.getElementById('dateFilter');
    if (dateSelect) {
      dateSelect.addEventListener('change', function () {
        if (this.value === 'custom') {
          var modal = document.getElementById('customDateModal');
          if (modal) modal.style.display = 'flex';
        } else {
          fetchDashboardData();
        }
      });
    }

    var branchSelect = document.getElementById('branchFilter');
    if (branchSelect) {
      branchSelect.addEventListener('change', fetchDashboardData);
    }

    var channelSelect = document.getElementById('channelFilter');
    if (channelSelect) {
      channelSelect.addEventListener('change', fetchDashboardData);
    }

    // 3. Action buttons
    var btnSync = document.getElementById('btnRefreshSync');
    if (btnSync) btnSync.addEventListener('click', triggerSync);

    var btnExport = document.getElementById('btnExportCsv');
    if (btnExport) btnExport.addEventListener('click', exportTableToCSV);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.CRMReportDashboard = {
    fetch: fetchDashboardData,
    sync: triggerSync,
    exportCSV: exportTableToCSV,
  };
})();
