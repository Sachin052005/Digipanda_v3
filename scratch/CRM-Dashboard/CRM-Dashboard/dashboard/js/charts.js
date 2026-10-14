/**
 * Charts
 * 1. Leads by Channel (Donut + custom legend, with distinct Google Ad and SEO, Problem 7)
 * 2. Branch Wise Lead Distribution (Stacked bars with distinct Google Ad and SEO, Problem 8)
 * 3. Call Outcomes & Lead Quality (Horizontal bars from the sheet's outcome columns)
 */

const DashboardCharts = (() => {
  let channelDonut = null, branchStacked = null, outcomesBar = null;
  const esc = (s) => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // Distinct palette for all 7 canonical channels
  const channelColors = {
    'Meta WhatsApp': '#059669',
    'Meta Lead Form': '#0284c7',
    'Website (Google Ad)': '#f59e0b',
    'Website (Google SEO)': '#8b5cf6',
    'Instagram': '#ec4899',
    'Google Calls': '#10b981',
    'Influencer': '#6366f1',
  };
  const colorOf = (c) => channelColors[c] || '#94a3b8';

  // Outcome colours: green for positive, red for missed/not connected, amber/purple for quality flags
  const outcomeColor = (name) => {
    const l = name.toLowerCase();
    if (/not\s*connect|missed|no answer|not\s*reach|rnr|not\s*interest/.test(l)) return '#ef4444';
    if (/connect|call taken|answered|qualified/.test(l)) return '#059669';
    if (/prospect|interest|admission/.test(l)) return '#0284c7';
    if (/irrelev|junk|spam|wrong/.test(l)) return '#94a3b8';
    if (/out of|hindi|language/.test(l)) return '#f59e0b';
    return '#8b5cf6';
  };

  const renderChannelDonut = (channels, total) => {
    const ctx = document.getElementById('channelDonutChart');
    if (!ctx) return;
    const center = document.getElementById('donutChannelTotal');
    if (center) center.textContent = (total || 0).toLocaleString();

    const labels = channels.map(c => c.channel);
    const values = channels.map(c => c.count);
    const colors = labels.map(colorOf);

    const legend = document.getElementById('channelCustomLegend');
    if (legend) {
      legend.innerHTML = channels.map(c => `
        <div class="legend-item">
          <div class="legend-label-wrap">
            <span class="legend-dot" style="background-color:${colorOf(c.channel)};"></span>
            <span>${esc(c.channel)}</span>
          </div>
          <span class="legend-val">${c.count.toLocaleString()} (${c.percentage}%)</span>
        </div>`).join('');
    }

    if (channelDonut) {
      channelDonut.data.labels = labels;
      channelDonut.data.datasets[0].data = values;
      channelDonut.data.datasets[0].backgroundColor = colors;
      channelDonut.update();
      return;
    }

    channelDonut = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: colors,
          borderWidth: 2,
          borderColor: '#ffffff',
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
              label: (c) => ` ${c.label}: ${c.raw.toLocaleString()}`,
            },
          },
        },
      },
    });
  };

  const renderBranchStacked = (rows, channelNames) => {
    const ctx = document.getElementById('branchStackedChart');
    if (!ctx) return;

    const labels = rows.map(r => r.branch);
    const datasets = channelNames.map((c, i) => ({
      label: c,
      data: rows.map(r => r.channels[i] || 0),
      backgroundColor: colorOf(c),
      stack: 's',
      maxBarThickness: 48,
    }));

    const legend = document.getElementById('branchStackedLegend');
    if (legend) {
      legend.innerHTML = datasets.map(d => `
        <div style="display:flex;align-items:center;gap:5px;font-size:0.73rem;color:#4b5563;">
          <span style="width:8px;height:8px;border-radius:50%;background-color:${d.backgroundColor};"></span>
          <span>${esc(d.label)}</span>
        </div>`).join('');
    }

    if (branchStacked) {
      branchStacked.$rows = rows;
      branchStacked.data.labels = labels;
      branchStacked.data.datasets = datasets;
      branchStacked.update();
      return;
    }

    const topLabels = {
      id: 'topLabels',
      afterDatasetsDraw(chart) {
        const { ctx: c, scales: { x, y } } = chart;
        (chart.$rows || []).forEach((r, i) => {
          c.save();
          c.font = 'bold 11px Inter, -apple-system, "Segoe UI", Roboto, sans-serif';
          c.fillStyle = '#111827';
          c.textAlign = 'center';
          const totalVal = r.total_leads || 0;
          const yPos = totalVal > 0 ? y.getPixelForValue(totalVal) - 6 : y.getPixelForValue(0) - 6;
          c.fillText(totalVal.toLocaleString(), x.getPixelForValue(i), yPos);
          c.restore();
        });
      },
    };

    branchStacked = new Chart(ctx, {
      type: 'bar',
      data: { labels, datasets },
      plugins: [topLabels],
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { mode: 'index', intersect: false },
        },
        scales: {
          x: {
            stacked: true,
            grid: { display: false },
            ticks: { font: { size: 10, family: 'Inter' }, color: '#374151' },
          },
          y: {
            stacked: true,
            beginAtZero: true,
            grace: '12%',
            ticks: { precision: 0, font: { size: 10, family: 'Inter' }, color: '#6b7280' },
            grid: { color: '#f3f4f6' },
          },
        },
      },
    });
    branchStacked.$rows = rows;
  };

  const renderOutcomes = (res) => {
    const ctx = document.getElementById('outcomesChart');
    const note = document.getElementById('outcomesNote');
    if (!ctx) return;
    const items = res.items;

    if (note) {
      note.textContent = !items.length
        ? 'No outcome columns found in the sheet'
        : !res.available
        ? 'Not split by channel. Choose "All Channels" to view'
        : '% of total leads';
    }

    const labels = items.map(i => i.name);
    const values = items.map(i => (res.available ? i.value : 0));
    const colors = labels.map(outcomeColor);
    const wrap = ctx.parentElement;
    if (wrap) wrap.style.height = `${Math.max(160, items.length * 30 + 20)}px`;

    if (outcomesBar) {
      outcomesBar.$items = res.available ? items : [];
      outcomesBar.data.labels = labels;
      outcomesBar.data.datasets[0].data = values;
      outcomesBar.data.datasets[0].backgroundColor = colors;
      outcomesBar.update();
      return;
    }

    const endLabels = {
      id: 'endLabels',
      afterDatasetsDraw(chart) {
        const { ctx: c } = chart;
        const meta = chart.getDatasetMeta(0);
        (chart.$items || []).forEach((it, i) => {
          const bar = meta.data[i];
          if (!bar) return;
          c.save();
          c.font = '600 11px Inter, -apple-system, "Segoe UI", Roboto, sans-serif';
          c.fillStyle = '#111827';
          c.textBaseline = 'middle';
          c.fillText(`${it.value.toLocaleString()} (${it.percentage}%)`, bar.x + 6, bar.y);
          c.restore();
        });
      },
    };

    outcomesBar = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: colors,
          borderRadius: 4,
          maxBarThickness: 18,
        }],
      },
      plugins: [endLabels],
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { right: 75 } },
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (c) => ` ${c.raw.toLocaleString()}` } },
        },
        scales: {
          x: {
            beginAtZero: true,
            ticks: { precision: 0, font: { size: 10, family: 'Inter' }, color: '#6b7280' },
            grid: { color: '#f3f4f6' },
          },
          y: {
            grid: { display: false },
            ticks: { font: { size: 11, family: 'Inter' }, color: '#374151' },
          },
        },
      },
    });
    outcomesBar.$items = res.available ? items : [];
  };

  return { renderChannelDonut, renderBranchStacked, renderOutcomes, colorOf };
})();
