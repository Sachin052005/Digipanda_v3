/**
 * TECHPANDA CRM - Modern Chart.js Theme & Visual Elevation Engine
 * Provides lush gradients, glossy floating tooltips, center doughnut stats,
 * rounded bar geometry, and zero-flicker light/dark mode adaptation.
 */
(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.TPCharts = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var chartRegistry = [];

  // Modern Enterprise Gradients & Palettes
  var PALETTE = [
    { start: '#4f46e5', end: '#818cf8', solid: '#6366f1' }, // Indigo
    { start: '#059669', end: '#34d399', solid: '#10b981' }, // Emerald
    { start: '#d97706', end: '#fbbf24', solid: '#f59e0b' }, // Amber
    { start: '#7c3aed', end: '#c084fc', solid: '#8b5cf6' }, // Purple
    { start: '#0284c7', end: '#38bdf8', solid: '#06b6d4' }, // Cyan / Sky
    { start: '#db2777', end: '#f472b6', solid: '#ec4899' }, // Rose / Pink
    { start: '#ea580c', end: '#fb923c', solid: '#f97316' }, // Orange
    { start: '#475569', end: '#94a3b8', solid: '#64748b' }  // Slate
  ];

  function isDarkTheme() {
    return document.documentElement.getAttribute('data-theme') === 'dark' ||
           document.body.classList.contains('dark-theme');
  }

  function getThemeColors() {
    var dark = isDarkTheme();
    return {
      isDark: dark,
      textColor: dark ? '#cbd5e1' : '#475569',
      textMuted: dark ? '#94a3b8' : '#64748b',
      gridColor: dark ? 'rgba(255, 255, 255, 0.06)' : 'rgba(226, 232, 240, 0.8)',
      borderColor: dark ? '#151d2f' : '#ffffff',
      tooltipBg: dark ? 'rgba(15, 23, 42, 0.92)' : 'rgba(255, 255, 255, 0.96)',
      tooltipText: dark ? '#f8fafc' : '#0f172a',
      tooltipBorder: dark ? 'rgba(255, 255, 255, 0.12)' : 'rgba(226, 232, 240, 0.9)'
    };
  }

  function createLinearGradient(ctx, startColor, endColor, isHorizontal) {
    if (!ctx) return startColor;
    var canvas = ctx.canvas || ctx;
    var h = canvas.height || 300;
    var w = canvas.width || 300;
    var grad;
    if (isHorizontal) {
      grad = (canvas.getContext ? canvas.getContext('2d') : ctx).createLinearGradient(0, 0, w, 0);
    } else {
      grad = (canvas.getContext ? canvas.getContext('2d') : ctx).createLinearGradient(0, 0, 0, h);
    }
    grad.addColorStop(0, startColor);
    grad.addColorStop(1, endColor);
    return grad;
  }

  // Common Glossy Tooltip Configuration
  function getGlossyTooltipOptions() {
    var theme = getThemeColors();
    return {
      backgroundColor: theme.tooltipBg,
      titleColor: theme.tooltipText,
      bodyColor: theme.textColor,
      borderColor: theme.tooltipBorder,
      borderWidth: 1,
      padding: { top: 10, bottom: 10, left: 14, right: 14 },
      cornerRadius: 10,
      displayColors: true,
      boxWidth: 9,
      boxHeight: 9,
      usePointStyle: true,
      boxPadding: 6,
      titleFont: { size: 12, weight: '700', family: "'Inter', sans-serif" },
      bodyFont: { size: 12, weight: '500', family: "'Inter', sans-serif" },
      shadowOffsetX: 0,
      shadowOffsetY: 8,
      shadowBlur: 20,
      shadowColor: 'rgba(0, 0, 0, 0.25)'
    };
  }

  // Center Text Plugin for Chart.js Doughnut Charts
  var centerTextPlugin = {
    id: 'centerTextPlugin',
    beforeDraw: function (chart) {
      if (chart.config.type !== 'doughnut') return;
      var centerConfig = chart.config.options.plugins.centerText;
      if (!centerConfig || centerConfig.display === false) return;

      var ctx = chart.ctx;
      var width = chart.width;
      var height = chart.height;

      ctx.save();

      var theme = getThemeColors();
      var value = centerConfig.value;
      if (value === undefined) {
        // Automatically sum up dataset values
        var ds = chart.data.datasets[0];
        if (ds && ds.data) {
          value = ds.data.reduce(function (a, b) { return a + (Number(b) || 0); }, 0);
        } else {
          value = 0;
        }
      }

      var label = centerConfig.label || 'TOTAL';
      var valueStr = typeof value === 'number' ? value.toLocaleString() : String(value);

      var centerY = (chart.chartArea.top + chart.chartArea.bottom) / 2;
      var centerX = (chart.chartArea.left + chart.chartArea.right) / 2;

      // Draw Value
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = theme.isDark ? '#f8fafc' : '#0f172a';
      ctx.font = '800 ' + (centerConfig.valueFontSize || '22px') + " 'Inter', sans-serif";
      ctx.fillText(valueStr, centerX, centerY - 8);

      // Draw Sub-label
      ctx.fillStyle = theme.textMuted;
      ctx.font = '700 ' + (centerConfig.labelFontSize || '11px') + " 'Inter', sans-serif";
      ctx.letterSpacing = '1px';
      ctx.fillText(label.toUpperCase(), centerX, centerY + 14);

      ctx.restore();
    }
  };

  // Register the plugin if Chart is available
  if (typeof Chart !== 'undefined' && Chart.register) {
    Chart.register(centerTextPlugin);
  }

  /**
   * Builds an ultra-modern Doughnut chart with center KPI stat and specular slices
   */
  function createDoughnut(canvasIdOrEl, config) {
    if (typeof Chart === 'undefined') {
      console.warn('Chart.js is not loaded.');
      return null;
    }

    var canvas = typeof canvasIdOrEl === 'string' ? document.getElementById(canvasIdOrEl) : canvasIdOrEl;
    if (!canvas) return null;

    var theme = getThemeColors();
    var labels = config.labels || [];
    var rawData = config.data || [];

    // Fallback if empty data
    if (labels.length === 0 || rawData.every(function (v) { return Number(v) === 0; })) {
      labels = labels.length ? labels : ['No Data'];
      rawData = [0];
    }

    // Generate colors
    var colors = config.colors || labels.map(function (_, i) {
      return PALETTE[i % PALETTE.length].solid;
    });

    var chartConfig = {
      type: 'doughnut',
      data: {
        labels: labels,
        datasets: [{
          data: rawData,
          backgroundColor: colors,
          borderWidth: 2,
          borderColor: theme.borderColor,
          hoverBorderColor: theme.borderColor,
          hoverOffset: 6,
          spacing: 1
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: config.cutout || '74%',
        animation: {
          animateScale: true,
          animateRotate: true,
          duration: 900,
          easing: 'easeOutQuart'
        },
        plugins: {
          legend: config.legend !== undefined ? config.legend : {
            position: config.legendPosition || 'bottom',
            labels: {
              boxWidth: 10,
              boxHeight: 10,
              usePointStyle: true,
              pointStyle: 'circle',
              font: { size: 11, weight: '600', family: "'Inter', sans-serif" },
              color: theme.textColor,
              padding: 12
            }
          },
          tooltip: Object.assign(getGlossyTooltipOptions(), config.tooltip || {}),
          centerText: Object.assign({
            display: true,
            label: config.centerLabel || 'TOTAL',
            value: config.centerValue
          }, config.centerText || {})
        }
      }
    };

    var chartInstance = new Chart(canvas, chartConfig);
    chartRegistry.push(chartInstance);
    return chartInstance;
  }

  /**
   * Builds a sleek modern Bar chart with rounded bars and vertical canvas gradients
   */
  function createBar(canvasIdOrEl, config) {
    if (typeof Chart === 'undefined') {
      console.warn('Chart.js is not loaded.');
      return null;
    }

    var canvas = typeof canvasIdOrEl === 'string' ? document.getElementById(canvasIdOrEl) : canvasIdOrEl;
    if (!canvas) return null;

    var theme = getThemeColors();
    var ctx = canvas.getContext('2d');

    // Build datasets with rounded corners
    var datasets = (config.datasets || []).map(function (ds, idx) {
      var colorDef = PALETTE[idx % PALETTE.length];
      var startCol = ds.gradientStart || colorDef.start;
      var endCol = ds.gradientEnd || colorDef.end;
      var bg = ds.backgroundColor || createLinearGradient(canvas, startCol, endCol, false);

      return Object.assign({
        label: ds.label || 'Series ' + (idx + 1),
        data: ds.data || [],
        backgroundColor: bg,
        borderRadius: ds.borderRadius !== undefined ? ds.borderRadius : 8,
        borderSkipped: false,
        maxBarThickness: ds.maxBarThickness || 32,
        barPercentage: ds.barPercentage || 0.75,
        categoryPercentage: ds.categoryPercentage || 0.75
      }, ds);
    });

    var chartConfig = {
      type: 'bar',
      data: {
        labels: config.labels || [],
        datasets: datasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          duration: 900,
          easing: 'easeOutQuart'
        },
        plugins: {
          legend: config.legend !== undefined ? config.legend : {
            position: config.legendPosition || 'top',
            labels: {
              boxWidth: 10,
              boxHeight: 10,
              usePointStyle: true,
              pointStyle: 'circle',
              font: { size: 11, weight: '600', family: "'Inter', sans-serif" },
              color: theme.textColor,
              padding: 14
            }
          },
          tooltip: Object.assign(getGlossyTooltipOptions(), config.tooltip || {})
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              font: { size: 11, family: "'Inter', sans-serif" },
              color: theme.textMuted
            },
            border: { display: false }
          },
          y: {
            beginAtZero: true,
            grid: {
              color: theme.gridColor,
              drawBorder: false
            },
            ticks: {
              font: { size: 11, family: "'Inter', sans-serif" },
              color: theme.textMuted,
              precision: 0
            },
            border: { display: false }
          }
        }
      }
    };

    var chartInstance = new Chart(canvas, chartConfig);
    chartRegistry.push(chartInstance);
    return chartInstance;
  }

  /**
   * Dynamic Theme Adaptation: updates all tracked charts when light/dark theme toggles
   */
  function refreshAllCharts() {
    var theme = getThemeColors();
    chartRegistry.forEach(function (chart) {
      if (!chart || !chart.ctx) return;

      // Update tooltip options
      if (chart.options.plugins && chart.options.plugins.tooltip) {
        Object.assign(chart.options.plugins.tooltip, getGlossyTooltipOptions());
      }

      // Update legends
      if (chart.options.plugins && chart.options.plugins.legend && chart.options.plugins.legend.labels) {
        chart.options.plugins.legend.labels.color = theme.textColor;
      }

      // Update scales
      if (chart.options.scales) {
        if (chart.options.scales.x && chart.options.scales.x.ticks) {
          chart.options.scales.x.ticks.color = theme.textMuted;
        }
        if (chart.options.scales.y) {
          if (chart.options.scales.y.ticks) chart.options.scales.y.ticks.color = theme.textMuted;
          if (chart.options.scales.y.grid) chart.options.scales.y.grid.color = theme.gridColor;
        }
      }

      // Update doughnut border
      if (chart.config.type === 'doughnut') {
        chart.data.datasets.forEach(function (ds) {
          ds.borderColor = theme.borderColor;
          ds.hoverBorderColor = theme.borderColor;
        });
      }

      chart.update('none'); // Update without full re-animation to avoid jarring flashes
    });
  }

  // Observe HTML data-theme changes
  var observer = new MutationObserver(function (mutations) {
    mutations.forEach(function (m) {
      if (m.type === 'attributes' && m.attributeName === 'data-theme') {
        refreshAllCharts();
      }
    });
  });

  if (document.documentElement) {
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  }

  return {
    PALETTE: PALETTE,
    isDarkTheme: isDarkTheme,
    getThemeColors: getThemeColors,
    createLinearGradient: createLinearGradient,
    getGlossyTooltipOptions: getGlossyTooltipOptions,
    createDoughnut: createDoughnut,
    createBar: createBar,
    refreshAllCharts: refreshAllCharts,
    track: function (instance) {
      if (instance && chartRegistry.indexOf(instance) === -1) {
        chartRegistry.push(instance);
      }
    }
  };
});
