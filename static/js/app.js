// Quotex Trading Journal & P&L Tracker Frontend Logic

let currentCurrency = localStorage.getItem('quotex_currency') || '₹';
function getActiveCurrencyCode() {
  return currentCurrency === '$' ? 'USD' : 'INR';
}
let equityChart = null;
let donutChart = null;
let dailyBarChart = null;

let currentHistoryPage = 0;
const HISTORY_PAGE_SIZE = 50;
let currentBreakdownType = 'daily';

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initCurrencySelector();
  initEquityPills();
  initAnalyticsPills();
  initDropzone();
  initSlider();
  initNewTradeModal();
  initHeatmapNav();

  // Load initial data
  loadDashboardData();
  fetchLatestRateInfo();
});

// Currency formatting & Switching
function initCurrencySelector() {
  const select = document.getElementById('currency-select');
  if (select) {
    select.value = currentCurrency;
    select.addEventListener('change', (e) => {
      setCurrency(e.target.value);
    });
  }
  updateCurrencyToggleButtons();
}

function setCurrency(curr) {
  currentCurrency = curr;
  localStorage.setItem('quotex_currency', curr);
  
  const select = document.getElementById('currency-select');
  if (select) select.value = curr;
  
  updateCurrencyToggleButtons();
  refreshCurrentView();
}

function updateCurrencyToggleButtons() {
  const btnInr = document.getElementById('btn-curr-inr');
  const btnUsd = document.getElementById('btn-curr-usd');
  const ratePill = document.getElementById('usd-rate-pill');
  if (btnInr) btnInr.classList.toggle('active', currentCurrency === '₹');
  if (btnUsd) btnUsd.classList.toggle('active', currentCurrency === '$');
  if (ratePill) {
    ratePill.style.display = currentCurrency === '$' ? 'inline-flex' : 'none';
  }
}

// Fetch live USD/INR exchange rate on load
async function fetchLatestRateInfo() {
  try {
    const res = await fetch('/api/exchange-rates').then(r => r.json());
    if (res.success && res.latest) {
      const valEl = document.getElementById('live-usd-rate-val');
      if (valEl) valEl.textContent = Number(res.latest).toFixed(2);
    }
  } catch (e) {
    // silently ignore
  }
}

function formatAmount(val, showSign = true) {
  if (val === null || val === undefined || isNaN(val)) return `${currentCurrency}0.00`;
  const num = parseFloat(val);
  const absFormatted = Math.abs(num).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (num > 0) {
    return showSign ? `+${currentCurrency}${absFormatted}` : `${currentCurrency}${absFormatted}`;
  } else if (num < 0) {
    return showSign ? `-${currentCurrency}${absFormatted}` : `-${currentCurrency}${absFormatted}`;
  } else {
    return `${currentCurrency}0.00`;
  }
}

// Toast notification
function showToast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${type === 'success' ? '✅' : '⚠️'}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// Navigation between tabs
function initNavigation() {
  const navItems = document.querySelectorAll('.nav-item[data-tab]');
  navItems.forEach(item => {
    item.addEventListener('click', () => {
      const tabName = item.getAttribute('data-tab');
      switchTab(tabName);

      // Close mobile sidebar if open
      const sidebar = document.querySelector('.sidebar');
      const backdrop = document.getElementById('sidebar-backdrop');
      if (sidebar) sidebar.classList.remove('open');
      if (backdrop) backdrop.classList.remove('active');
    });
  });
}

function toggleSidebar() {
  const sidebar = document.querySelector('.sidebar');
  const backdrop = document.getElementById('sidebar-backdrop');
  if (sidebar) sidebar.classList.toggle('open');
  if (backdrop) backdrop.classList.toggle('active');
}

function switchTab(tabName) {
  // Always scroll to top when changing tabs so header sits cleanly
  window.scrollTo({ top: 0, behavior: 'instant' });

  // Update sidebar active class
  document.querySelectorAll('.sidebar-nav .nav-item').forEach(el => {
    el.classList.toggle('active', el.getAttribute('data-tab') === tabName);
  });

  // Update tab content
  document.querySelectorAll('.tab-content').forEach(el => {
    el.classList.remove('active');
  });

  const targetTab = document.getElementById(`tab-${tabName}`);
  if (targetTab) {
    targetTab.classList.add('active');
  }

  // Update page header
  const titleEl = document.getElementById('page-title-text');
  const descEl = document.getElementById('page-desc-text');
  
  if (tabName === 'dashboard') {
    titleEl.textContent = 'Dashboard';
    descEl.textContent = 'Deep dive into your Quotex trading performance';
    loadDashboardData();
  } else if (tabName === 'analytics') {
    titleEl.textContent = 'Analytics';
    descEl.textContent = 'Statistical analysis, win rate, expectancy, and daily distribution';
    loadAnalyticsData('all');
  } else if (tabName === 'breakdown') {
    titleEl.textContent = 'P&L Breakdown';
    descEl.textContent = 'Daily, Weekly, Monthly, 3-Month, and 1-Year performance tables';
    loadBreakdownData(currentBreakdownType);
  } else if (tabName === 'heatmap-tab') {
    titleEl.textContent = 'Calendar Heatmap';
    descEl.textContent = 'Visual day-by-day profit and loss trading calendar';
    loadFullHeatmap(currentHeatmapMonth);
  } else if (tabName === 'history') {
    titleEl.textContent = 'Trade History';
    descEl.textContent = 'Full log of all imported Quotex options and OTC trades';
    loadTradeHistory(0);
  } else if (tabName === 'import-csv') {
    titleEl.textContent = 'Files & CSV Import';
    descEl.textContent = 'Upload, download, manage trade CSV files and bulk import';
    loadUploadedFiles();
  }
}

function refreshCurrentView() {
  const activeTab = document.querySelector('.tab-content.active');
  if (!activeTab) return;
  const tabId = activeTab.id.replace('tab-', '');
  if (tabId === 'dashboard') loadDashboardData();
  else if (tabId === 'analytics') {
    const activePill = document.querySelector('#analytics-timeframe-pills .pill-btn.active');
    loadAnalyticsData(activePill ? activePill.dataset.tf : 'all');
  }
  else if (tabId === 'breakdown') loadBreakdownData(currentBreakdownType);
  else if (tabId === 'heatmap-tab') loadFullHeatmap(currentHeatmapMonth);
  else if (tabId === 'history') loadTradeHistory(currentHistoryPage);
  else if (tabId === 'import-csv') loadUploadedFiles();
}

// -------------------------------------------------------------------------
// DASHBOARD
// -------------------------------------------------------------------------
async function loadDashboardData() {
  try {
    const curr = getActiveCurrencyCode();
    const [statsRes, recentTradesRes] = await Promise.all([
      fetch(`/api/stats?timeframe=all&currency=${curr}`).then(r => r.json()),
      fetch(`/api/trades?limit=8&offset=0&currency=${curr}`).then(r => r.json())
    ]);

    if (statsRes.success) {
      updateDashboardKPIs(statsRes.stats);
      updateWinRateDonut(statsRes.stats);
    }

    if (recentTradesRes.success) {
      renderRecentTrades(recentTradesRes.data.trades);
      const badge = document.getElementById('sidebar-total-badge');
      if (badge) badge.textContent = recentTradesRes.data.total;
    }

    const activeTf = document.querySelector('#equity-timeframe-pills .pill-btn.active');
    loadEquityCurve(activeTf ? activeTf.dataset.tf : 'all');
    loadDashboardHeatmap();
  } catch (err) {
    console.error('Error loading dashboard data:', err);
  }
}

function updateDashboardKPIs(stats) {
  const pnlEl = document.getElementById('kpi-total-pnl');
  const pnlSub = document.getElementById('kpi-pnl-sub');
  const winRateEl = document.getElementById('kpi-win-rate');
  const winSub = document.getElementById('kpi-win-sub');
  const pfEl = document.getElementById('kpi-profit-factor');
  const totalTradesEl = document.getElementById('kpi-total-trades');

  if (pnlEl) {
    pnlEl.textContent = formatAmount(stats.total_pnl);
    pnlEl.className = 'kpi-value ' + (stats.total_pnl > 0 ? 'text-win' : stats.total_pnl < 0 ? 'text-loss' : '');
  }
  if (pnlSub) {
    const arrow = stats.total_pnl >= 0 ? '↑' : '↓';
    pnlSub.textContent = `${arrow} ${stats.total_trades} trades`;
  }
  if (winRateEl) {
    winRateEl.textContent = `${stats.win_rate}%`;
  }
  if (winSub) {
    winSub.textContent = `↑ ${stats.wins}W / ${stats.losses}L / ${stats.refunds}R`;
  }
  if (pfEl) {
    pfEl.textContent = stats.profit_factor.toFixed(2);
  }
  if (totalTradesEl) {
    totalTradesEl.textContent = stats.total_trades.toLocaleString();
  }
  const tradesSub = document.getElementById('kpi-trades-sub');
  if (tradesSub) {
    tradesSub.textContent = `${stats.trading_days || 1} trading days`;
  }

  // 5th KPI Card: Traded Volume
  const volEl = document.getElementById('kpi-total-volume');
  const volSub = document.getElementById('kpi-volume-sub');
  if (volEl) {
    volEl.textContent = formatAmount(stats.total_volume || 0, false);
  }
  if (volSub) {
    const avgVol = stats.avg_daily_volume || 0;
    volSub.textContent = `Avg ${formatAmount(avgVol, false)} / day`;
  }
}

function initEquityPills() {
  const pills = document.querySelectorAll('#equity-timeframe-pills .pill-btn');
  pills.forEach(pill => {
    pill.addEventListener('click', () => {
      pills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      loadEquityCurve(pill.dataset.tf);
    });
  });
}

async function loadEquityCurve(timeframe) {
  try {
    const curr = getActiveCurrencyCode();
    const res = await fetch(`/api/equity-curve?timeframe=${timeframe}&currency=${curr}`).then(r => r.json());
    if (!res.success) return;

    const data = res.data;
    const labels = data.map(d => d.date_time.slice(5, 16)); // MM-DD HH:MM
    const balances = data.map(d => d.balance);

    const canvas = document.getElementById('equityCurveChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    // Create gradient fill
    const gradient = ctx.createLinearGradient(0, 0, 0, 320);
    const lastBalance = balances.length > 0 ? balances[balances.length - 1] : 0;
    const isUp = lastBalance >= 0;
    
    if (isUp) {
      gradient.addColorStop(0, 'rgba(16, 185, 129, 0.35)');
      gradient.addColorStop(1, 'rgba(16, 185, 129, 0.00)');
    } else {
      gradient.addColorStop(0, 'rgba(239, 68, 68, 0.35)');
      gradient.addColorStop(1, 'rgba(239, 68, 68, 0.00)');
    }

    const lineColor = isUp ? '#10b981' : '#ef4444';

    if (equityChart) {
      equityChart.destroy();
    }

    equityChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: 'Account Equity',
          data: balances,
          borderColor: lineColor,
          borderWidth: 2.5,
          backgroundColor: gradient,
          fill: true,
          tension: 0.3,
          pointRadius: balances.length > 60 ? 0 : 3,
          pointHoverRadius: 6,
          pointBackgroundColor: lineColor,
          pointBorderColor: '#fff',
          pointBorderWidth: 1.5
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: 'index',
          intersect: false
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#151a2e',
            titleColor: '#94a3b8',
            bodyColor: '#fff',
            borderColor: '#242c4c',
            borderWidth: 1,
            padding: 12,
            callbacks: {
              label: (context) => `Balance: ${formatAmount(context.raw)}`
            }
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              color: '#64748b',
              maxTicksLimit: 8,
              font: { size: 11 }
            }
          },
          y: {
            grid: {
              color: 'rgba(36, 44, 76, 0.4)'
            },
            ticks: {
              color: '#64748b',
              font: { size: 11 },
              callback: (val) => `${currentCurrency}${val}`
            }
          }
        }
      }
    });
  } catch (err) {
    console.error('Error rendering equity curve:', err);
  }
}

function updateWinRateDonut(stats) {
  const canvas = document.getElementById('winRateDonutChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  const wins = stats.wins || 0;
  const losses = stats.losses || 0;
  const refunds = stats.refunds || 0;
  const total = wins + losses + refunds;

  document.getElementById('donut-percentage').textContent = `${stats.win_rate}%`;
  document.getElementById('donut-wins-label').textContent = `Wins: ${wins}`;
  document.getElementById('donut-losses-label').textContent = `Losses: ${losses}`;
  document.getElementById('donut-refunds-label').textContent = `Refunds: ${refunds}`;

  if (donutChart) {
    donutChart.destroy();
  }

  donutChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Wins', 'Losses', 'Refunds / Ties'],
      datasets: [{
        data: total > 0 ? [wins, losses, refunds] : [1, 0, 0],
        backgroundColor: total > 0 ? ['#10b981', '#ef4444', '#f59e0b'] : ['#242c4c'],
        borderWidth: 0,
        hoverOffset: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '76%',
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#151a2e',
          borderColor: '#242c4c',
          borderWidth: 1,
          padding: 10
        }
      }
    }
  });
}

function renderRecentTrades(trades) {
  const container = document.getElementById('dashboard-recent-trades');
  if (!container) return;

  if (!trades || trades.length === 0) {
    container.innerHTML = `<div style="text-align: center; color: var(--text-dim); padding: 40px;">No trades logged yet.</div>`;
    return;
  }

  container.innerHTML = trades.map(t => {
    const isUp = t.direction === 'UP';
    const isWin = t.result === 'WIN';
    const isLoss = t.result === 'LOSS';
    const isRefund = t.result === 'REFUND';

    let badgeClass = 'badge-refund';
    let badgeText = 'REFUND';
    let pnlClass = 'text-refund';
    if (isWin) {
      badgeClass = 'badge-win';
      badgeText = 'WIN';
      pnlClass = 'text-win';
    } else if (isLoss) {
      badgeClass = 'badge-loss';
      badgeText = 'LOSS';
      pnlClass = 'text-loss';
    }

    return `
      <div class="trade-item">
        <div class="trade-left">
          <div class="trade-dir-icon ${isUp ? 'trade-dir-up' : 'trade-dir-down'}">
            ${isUp ? '↗' : '↘'}
          </div>
          <div class="trade-meta">
            <span class="trade-pair">${t.asset}</span>
            <span class="trade-time">${t.date_time}</span>
          </div>
        </div>
        <div class="trade-right">
          <span class="${badgeClass}">${badgeText}</span>
          <span class="trade-pnl ${pnlClass}">${formatAmount(t.profit)}</span>
        </div>
      </div>
    `;
  }).join('');
}

// -------------------------------------------------------------------------
// HEATMAP CALENDAR (1 Month, 3 Months, 12 Months Support)
// -------------------------------------------------------------------------
let currentHeatmapMonth = null;
let currentHeatmapRange = '1m';

function initHeatmapNav() {
  document.getElementById('btn-prev-month')?.addEventListener('click', () => changeHeatmapPeriod(-1));
  document.getElementById('btn-next-month')?.addEventListener('click', () => changeHeatmapPeriod(1));
  document.getElementById('full-btn-prev')?.addEventListener('click', () => changeHeatmapPeriod(-1));
  document.getElementById('full-btn-next')?.addEventListener('click', () => changeHeatmapPeriod(1));

  // Dashboard range pills
  document.querySelectorAll('#heatmap-range-pills .pill-btn').forEach(pill => {
    pill.addEventListener('click', () => {
      setHeatmapRange(pill.dataset.range);
    });
  });

  // Full tab range pills
  document.querySelectorAll('#full-heatmap-range-pills .pill-btn').forEach(pill => {
    pill.addEventListener('click', () => {
      setHeatmapRange(pill.dataset.range);
    });
  });
}

function setHeatmapRange(range) {
  currentHeatmapRange = range;
  
  // Sync pill active states
  document.querySelectorAll('#heatmap-range-pills .pill-btn, #full-heatmap-range-pills .pill-btn').forEach(p => {
    p.classList.toggle('active', p.dataset.range === range);
  });
  
  updateHeatmapNavLabels();
  loadDashboardHeatmap(currentHeatmapMonth);
  loadFullHeatmap(currentHeatmapMonth);
}

function updateHeatmapNavLabels() {
  const prevBtn = document.getElementById('btn-prev-month');
  const nextBtn = document.getElementById('btn-next-month');
  const fullPrev = document.getElementById('full-btn-prev');
  const fullNext = document.getElementById('full-btn-next');

  let prevText = '‹ Prev Month';
  let nextText = 'Next Month ›';
  if (currentHeatmapRange === '3m') {
    prevText = '‹ Prev 3 Months';
    nextText = 'Next 3 Months ›';
  } else if (currentHeatmapRange === '12m') {
    prevText = '‹ Prev Year';
    nextText = 'Next Year ›';
  }

  if (prevBtn) prevBtn.textContent = prevText;
  if (nextBtn) nextBtn.textContent = nextText;
  if (fullPrev) fullPrev.textContent = prevText;
  if (fullNext) fullNext.textContent = nextText;
}

function changeHeatmapPeriod(direction) {
  if (!currentHeatmapMonth) {
    const now = new Date();
    currentHeatmapMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  }
  const [yearStr, monthStr] = currentHeatmapMonth.split('-');
  let y = parseInt(yearStr, 10);
  let m = parseInt(monthStr, 10);

  let step = 1;
  if (currentHeatmapRange === '3m') step = 3;
  else if (currentHeatmapRange === '12m') step = 12;

  m += (direction * step);
  while (m < 1) {
    m += 12;
    y -= 1;
  }
  while (m > 12) {
    m -= 12;
    y += 1;
  }

  currentHeatmapMonth = `${y}-${String(m).padStart(2, '0')}`;
  loadDashboardHeatmap(currentHeatmapMonth);
  loadFullHeatmap(currentHeatmapMonth);
}

async function loadDashboardHeatmap(month) {
  try {
    const targetMonth = month || currentHeatmapMonth || '';
    const curr = getActiveCurrencyCode();
    const url = `/api/heatmap?month=${targetMonth}&range=${currentHeatmapRange}&currency=${curr}`;
    const res = await fetch(url).then(r => r.json());
    if (!res.success) return;

    const data = res.heatmap;
    currentHeatmapMonth = data.year_month;

    // Header title
    const labelEl = document.getElementById('calendar-current-month-label');
    if (labelEl) {
      if (currentHeatmapRange === '1m') {
        const [y, m] = currentHeatmapMonth.split('-');
        const dateObj = new Date(parseInt(y), parseInt(m) - 1, 1);
        labelEl.textContent = dateObj.toLocaleString('default', { month: 'long', year: 'numeric' });
      } else if (currentHeatmapRange === '3m' && data.months && data.months.length > 0) {
        labelEl.textContent = `${data.months[0].month_name} — ${data.months[data.months.length - 1].month_name}`;
      } else if (currentHeatmapRange === '12m') {
        labelEl.textContent = `Year ${currentHeatmapMonth.slice(0, 4)} (Full 12 Months)`;
      }
    }

    const totalEl = document.getElementById('heatmap-total-badge');
    if (totalEl) {
      totalEl.textContent = formatAmount(data.overall_pnl);
      totalEl.className = data.overall_pnl > 0 ? 'text-win' : data.overall_pnl < 0 ? 'text-loss' : '';
    }

    renderHeatmapContent('calendar-months-view', data);
  } catch (err) {
    console.error('Error loading dashboard heatmap:', err);
  }
}

async function loadFullHeatmap(month) {
  try {
    const targetMonth = month || currentHeatmapMonth || '';
    const curr = getActiveCurrencyCode();
    const url = `/api/heatmap?month=${targetMonth}&range=${currentHeatmapRange}&currency=${curr}`;
    const res = await fetch(url).then(r => r.json());
    if (!res.success) return;

    const data = res.heatmap;
    currentHeatmapMonth = data.year_month;

    const labelEl = document.getElementById('full-heatmap-month-label');
    if (labelEl) {
      if (currentHeatmapRange === '1m') {
        const [y, m] = currentHeatmapMonth.split('-');
        const dateObj = new Date(parseInt(y), parseInt(m) - 1, 1);
        labelEl.textContent = dateObj.toLocaleString('default', { month: 'long', year: 'numeric' });
      } else if (currentHeatmapRange === '3m' && data.months && data.months.length > 0) {
        labelEl.textContent = `${data.months[0].month_name} — ${data.months[data.months.length - 1].month_name}`;
      } else if (currentHeatmapRange === '12m') {
        labelEl.textContent = `Year ${currentHeatmapMonth.slice(0, 4)} (Full 12 Months)`;
      }
    }

    const totalEl = document.getElementById('full-heatmap-pnl');
    if (totalEl) {
      totalEl.textContent = formatAmount(data.overall_pnl);
      totalEl.className = data.overall_pnl > 0 ? 'text-win' : data.overall_pnl < 0 ? 'text-loss' : '';
    }
    const volEl = document.getElementById('full-heatmap-volume');
    if (volEl) {
      volEl.textContent = `Total Vol: ${formatAmount(data.overall_volume || 0, false)}`;
    }

    renderHeatmapContent('full-calendar-months-view', data, true);
  } catch (err) {
    console.error('Error loading full heatmap:', err);
  }
}

function renderHeatmapContent(containerId, heatmapData, isFull = false) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';

  if (heatmapData.range_type === '1m') {
    // 1 Month View
    const monthObj = (heatmapData.months && heatmapData.months.length > 0) ? heatmapData.months[0] : { days: heatmapData.days, year_month: heatmapData.year_month };
    const [y, m] = monthObj.year_month.split('-');

    const wrapper = document.createElement('div');
    wrapper.className = 'single-month-wrapper';
    wrapper.innerHTML = `
      <div class="calendar-weekdays">
        <div>Sun</div><div>Mon</div><div>Tue</div><div>Wed</div><div>Thu</div><div>Fri</div><div>Sat</div>
      </div>
      <div class="calendar-grid" id="${containerId}-single-grid"></div>
    `;
    container.appendChild(wrapper);
    buildCalendarDaysGrid(`${containerId}-single-grid`, y, m, monthObj.days, false, isFull);
  } else {
    // 3 Months or 12 Months Multi-Month Grid
    const gridClass = heatmapData.range_type === '3m' ? 'multi-months-grid grid-3m' : 'multi-months-grid grid-12m';
    const gridWrapper = document.createElement('div');
    gridWrapper.className = gridClass;

    heatmapData.months.forEach((mObj, idx) => {
      const [y, m] = mObj.year_month.split('-');
      const cardEl = document.createElement('div');
      cardEl.className = 'month-block';

      const pnlClass = mObj.month_pnl > 0 ? 'text-win' : mObj.month_pnl < 0 ? 'text-loss' : '';
      const gridId = `${containerId}-grid-${idx}`;
      const volTag = (isFull && mObj.month_volume) ? ` • Vol: ${formatAmount(mObj.month_volume, false)}` : '';

      cardEl.innerHTML = `
        <div class="month-block-header">
          <span class="month-block-title">${mObj.month_name}</span>
          <span class="month-block-badge ${pnlClass}">${formatAmount(mObj.month_pnl)}${volTag}</span>
        </div>
        <div class="calendar-weekdays">
          <div>S</div><div>M</div><div>T</div><div>W</div><div>T</div><div>F</div><div>S</div>
        </div>
        <div class="calendar-grid" id="${gridId}"></div>
      `;
      gridWrapper.appendChild(cardEl);
      
      // Delay slightly for DOM insertion
      setTimeout(() => {
        buildCalendarDaysGrid(gridId, y, m, mObj.days, true, isFull);
      }, 0);
    });

    container.appendChild(gridWrapper);
  }
}

function buildCalendarDaysGrid(containerId, year, month, daysData, isCompact = false, isFull = false) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';

  const y = parseInt(year);
  const m = parseInt(month) - 1; // 0-indexed

  const firstDay = new Date(y, m, 1).getDay(); // 0 = Sun
  const daysInMonth = new Date(y, m + 1, 0).getDate();

  // Blank leading slots
  for (let i = 0; i < firstDay; i++) {
    const blank = document.createElement('div');
    blank.className = 'calendar-day empty';
    container.appendChild(blank);
  }

  // Days of the month
  for (let d = 1; d <= daysInMonth; d++) {
    const dayStr = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    const dayInfo = daysData[dayStr];

    const dayEl = document.createElement('div');
    dayEl.className = 'calendar-day';

    if (dayInfo) {
      const pnl = dayInfo.pnl;
      const isWin = pnl > 0;
      const isLoss = pnl < 0;
      const isBreakeven = pnl === 0;

      if (isWin) dayEl.classList.add('day-win');
      else if (isLoss) dayEl.classList.add('day-loss');
      else dayEl.classList.add('day-refund');

      const pnlColorClass = isWin ? 'text-win' : isLoss ? 'text-loss' : 'text-refund';
      const pnlFormatted = isBreakeven ? '0.00' : formatAmount(pnl, true);

      // On dashboard (isFull = false): DO NOT show volume inside cell so it never gets choppy!
      // In full heatmap tab (isFull = true): show volume if available
      const volStr = (isFull && dayInfo.volume) ? `<div class="day-vol text-muted" style="font-size: 0.63rem; font-family: var(--font-mono); opacity: 0.85; margin-top: 2px;">Vol: ${formatAmount(dayInfo.volume, false)}</div>` : '';

      dayEl.innerHTML = `
        <div class="day-number">${d}</div>
        <div class="day-pnl ${pnlColorClass}">${pnlFormatted}</div>
        ${volStr}
      `;
      dayEl.title = `${dayStr}\nP&L: ${formatAmount(pnl)}${isBreakeven ? ' (Breakeven: No Loss No Gain)' : ''}\nTraded Volume: ${dayInfo.volume ? formatAmount(dayInfo.volume, false) : formatAmount(0, false)}\nTrades: ${dayInfo.trades_count} (${dayInfo.wins}W / ${dayInfo.losses}L / ${dayInfo.refunds}R)\nClick to view trades for this day`;
      dayEl.style.cursor = 'pointer';
      dayEl.addEventListener('click', () => {
        switchTab('history');
        const searchInput = document.getElementById('history-search-input');
        if (searchInput) {
          searchInput.value = dayStr;
          loadTradeHistory(0);
        }
      });
    } else {
      dayEl.innerHTML = `<div class="day-number">${d}</div>`;
    }

    container.appendChild(dayEl);
  }
}

// -------------------------------------------------------------------------
// ANALYTICS (Image 1)
// -------------------------------------------------------------------------
function initAnalyticsPills() {
  const pills = document.querySelectorAll('#analytics-timeframe-pills .pill-btn');
  pills.forEach(pill => {
    pill.addEventListener('click', () => {
      pills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      loadAnalyticsData(pill.dataset.tf);
    });
  });
}

async function loadAnalyticsData(timeframe) {
  try {
    const curr = getActiveCurrencyCode();
    const [statsRes, barRes] = await Promise.all([
      fetch(`/api/stats?timeframe=${timeframe}&currency=${curr}`).then(r => r.json()),
      fetch(`/api/daily-pnl?timeframe=${timeframe}&currency=${curr}`).then(r => r.json())
    ]);

    if (statsRes.success) {
      const s = statsRes.stats;
      const pnlEl = document.getElementById('ana-total-pnl');
      pnlEl.textContent = formatAmount(s.total_pnl);
      pnlEl.className = 'kpi-value ' + (s.total_pnl > 0 ? 'text-win' : s.total_pnl < 0 ? 'text-loss' : '');

      document.getElementById('ana-win-rate').textContent = `${s.win_rate}%`;
      document.getElementById('ana-win-sub').textContent = `${s.wins}W / ${s.losses}L / ${s.refunds}R`;
      document.getElementById('ana-profit-factor').textContent = s.profit_factor.toFixed(2);
      
      const expEl = document.getElementById('ana-expectancy');
      expEl.textContent = formatAmount(s.expectancy);
      expEl.className = 'kpi-value ' + (s.expectancy > 0 ? 'text-win' : s.expectancy < 0 ? 'text-loss' : '');

      document.getElementById('ana-avg-win').textContent = formatAmount(s.avg_win, false);
      document.getElementById('ana-avg-loss').textContent = formatAmount(s.avg_loss, false);
      document.getElementById('ana-best-trade').textContent = formatAmount(s.best_trade);
      document.getElementById('ana-worst-trade').textContent = formatAmount(s.worst_trade);
    }

    if (barRes.success) {
      renderDailyPnlBarChart(barRes.data);
    }
  } catch (err) {
    console.error('Error loading analytics:', err);
  }
}

function renderDailyPnlBarChart(dailyData) {
  const canvas = document.getElementById('dailyPnlBarChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  const labels = dailyData.map(d => d.date.slice(5)); // MM-DD
  const values = dailyData.map(d => d.pnl);
  const colors = values.map(v => v >= 0 ? '#10b981' : '#ef4444');

  if (dailyBarChart) {
    dailyBarChart.destroy();
  }

  dailyBarChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Daily P&L',
        data: values,
        backgroundColor: colors,
        borderRadius: 4,
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#151a2e',
          borderColor: '#242c4c',
          borderWidth: 1,
          padding: 12,
          callbacks: {
            title: (items) => dailyData[items[0].dataIndex].date,
            label: (item) => {
              const d = dailyData[item.dataIndex];
              return [
                `P&L: ${formatAmount(d.pnl)}`,
                `Traded Volume: ${formatAmount(d.volume || 0, false)}`,
                `Trades: ${d.trades_count} (${d.wins}W / ${d.losses}L / ${d.refunds}R)`
              ];
            }
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: '#64748b',
            maxTicksLimit: 14,
            font: { size: 10 }
          }
        },
        y: {
          grid: { color: 'rgba(36, 44, 76, 0.4)' },
          ticks: {
            color: '#64748b',
            font: { size: 11 },
            callback: (v) => `${currentCurrency}${v}`
          }
        }
      }
    }
  });
}

// -------------------------------------------------------------------------
// P&L BREAKDOWN (Daily, Weekly, Monthly, 3 Months, 1 Year)
// -------------------------------------------------------------------------
function loadBreakdownView(type, btnEl) {
  currentBreakdownType = type;
  document.querySelectorAll('.breakdown-pill').forEach(el => el.classList.remove('active'));
  if (btnEl) btnEl.classList.add('active');
  loadBreakdownData(type);
}

async function loadBreakdownData(periodType) {
  try {
    const titles = {
      'daily': '📅 Daily P&L Breakdown',
      'weekly': '📆 Weekly P&L Breakdown',
      'monthly': '🗓️ Monthly P&L Breakdown',
      '3month': '📊 3-Month / Quarterly P&L Breakdown',
      '1year': '📈 1-Year / Annual P&L Breakdown'
    };
    document.getElementById('breakdown-table-title').innerHTML = `<span>${titles[periodType] || 'P&L Breakdown'}</span>`;

    const curr = getActiveCurrencyCode();
    const res = await fetch(`/api/breakdown?type=${periodType}&currency=${curr}`).then(r => r.json());
    const tbody = document.getElementById('breakdown-table-body');
    if (!tbody) return;

    if (!res.success || !res.breakdown || res.breakdown.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-dim); padding: 40px;">No trade data available for this timeframe.</td></tr>`;
      document.getElementById('breakdown-summary-badge').textContent = '';
      return;
    }

    let netSum = 0;
    let volSum = 0;
    tbody.innerHTML = res.breakdown.map(item => {
      netSum += item.net_pnl;
      volSum += (item.total_volume || 0);
      const isPos = item.net_pnl > 0;
      const isNeg = item.net_pnl < 0;
      const pnlClass = isPos ? 'text-win' : isNeg ? 'text-loss' : 'text-refund';
      
      return `
        <tr>
          <td style="font-weight: 700;">${item.period_label}</td>
          <td style="text-align: center; font-weight: 600;">${item.total_trades}</td>
          <td style="text-align: center;"><span class="badge-win">${item.wins}</span></td>
          <td style="text-align: center;"><span class="badge-loss">${item.losses}</span></td>
          <td style="text-align: center;"><span class="badge-refund">${item.refunds}</span></td>
          <td style="text-align: center; font-weight: 600;">${item.win_rate}%</td>
          <td style="text-align: right; color: var(--text-muted); font-family: var(--font-mono);">${formatAmount(item.total_volume, false)}</td>
          <td style="text-align: right; font-weight: 800; font-family: var(--font-mono); font-size: 1rem;" class="${pnlClass}">
            ${formatAmount(item.net_pnl)}
          </td>
        </tr>
      `;
    }).join('');

    const sumBadge = document.getElementById('breakdown-summary-badge');
    if (sumBadge) {
      sumBadge.textContent = `Period Net P&L: ${formatAmount(netSum)}  •  Total Volume: ${formatAmount(volSum, false)}`;
      sumBadge.className = netSum > 0 ? 'text-win' : netSum < 0 ? 'text-loss' : '';
    }
  } catch (err) {
    console.error('Error loading breakdown:', err);
  }
}

// -------------------------------------------------------------------------
// TRADE HISTORY
// -------------------------------------------------------------------------
async function loadTradeHistory(page = 0) {
  currentHistoryPage = page;
  const offset = page * HISTORY_PAGE_SIZE;

  const resultFilter = document.getElementById('history-result-filter')?.value || '';
  const assetFilter = document.getElementById('history-asset-filter')?.value || '';
  const search = document.getElementById('history-search-input')?.value || '';

  const params = new URLSearchParams({
    limit: HISTORY_PAGE_SIZE,
    offset: offset,
    result: resultFilter,
    asset: assetFilter,
    search: search,
    currency: getActiveCurrencyCode()
  });

  try {
    const res = await fetch(`/api/trades?${params.toString()}`).then(r => r.json());
    if (!res.success) return;

    const { trades, total, assets } = res.data;

    // Populate asset dropdown if not already populated
    const assetSelect = document.getElementById('history-asset-filter');
    if (assetSelect && assetSelect.options.length <= 1) {
      assets.forEach(a => {
        const opt = document.createElement('option');
        opt.value = a;
        opt.textContent = a;
        assetSelect.appendChild(opt);
      });
    }

    const tbody = document.getElementById('history-table-body');
    if (!trades || trades.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-dim); padding: 40px;">No trades found matching criteria.</td></tr>`;
    } else {
      tbody.innerHTML = trades.map(t => {
        const isUp = t.direction === 'UP';
        const isWin = t.result === 'WIN';
        const isLoss = t.result === 'LOSS';

        let badgeClass = 'badge-refund';
        let pnlClass = 'text-refund';
        if (isWin) {
          badgeClass = 'badge-win';
          pnlClass = 'text-win';
        } else if (isLoss) {
          badgeClass = 'badge-loss';
          pnlClass = 'text-loss';
        }

        return `
          <tr>
            <td style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-dim);">${t.trade_id}</td>
            <td style="font-size: 0.82rem;">${t.date_time}</td>
            <td style="font-weight: 600;">${t.asset}</td>
            <td>
              <span style="display: inline-flex; align-items: center; gap: 4px; font-weight: 600; color: ${isUp ? 'var(--color-win)' : 'var(--color-loss)'};">
                ${isUp ? '▲ CALL' : '▼ PUT'}
              </span>
            </td>
            <td style="text-align: right; font-family: var(--font-mono);">${formatAmount(t.investment, false)}</td>
            <td style="text-align: center; color: var(--text-muted);">${t.payout_rate}%</td>
            <td style="text-align: center;"><span class="${badgeClass}">${t.result}</span></td>
            <td style="text-align: right; font-weight: 800; font-family: var(--font-mono);" class="${pnlClass}">
              ${formatAmount(t.profit)}
            </td>
            <td style="text-align: center; white-space: nowrap;">
              <button class="btn btn-secondary btn-sm" style="padding: 4px 8px; margin-right: 4px;" onclick="openEditTradeModal(${t.id})" title="Edit trade">✏️</button>
              <button class="btn btn-danger btn-sm" style="padding: 4px 8px;" onclick="deleteTrade(${t.id})" title="Delete trade">✕</button>
            </td>
          </tr>
        `;
      }).join('');
    }

    // Pagination info
    const startIdx = total === 0 ? 0 : offset + 1;
    const endIdx = Math.min(offset + HISTORY_PAGE_SIZE, total);
    document.getElementById('history-pagination-info').textContent = `Showing ${startIdx} to ${endIdx} of ${total} trades`;

    document.getElementById('btn-history-prev').disabled = page <= 0;
    document.getElementById('btn-history-next').disabled = endIdx >= total;

  } catch (err) {
    console.error('Error loading trade history:', err);
  }
}

function historyPrevPage() {
  if (currentHistoryPage > 0) {
    loadTradeHistory(currentHistoryPage - 1);
  }
}

function historyNextPage() {
  loadTradeHistory(currentHistoryPage + 1);
}

async function deleteTrade(id) {
  if (!confirm('Are you sure you want to delete this trade?')) return;
  try {
    const res = await fetch(`/api/trades/delete/${id}`, { method: 'POST' }).then(r => r.json());
    if (res.success) {
      showToast('Trade deleted successfully.');
      loadTradeHistory(currentHistoryPage);
    }
  } catch (err) {
    console.error(err);
  }
}

async function confirmClearTrades() {
  if (!confirm('WARNING: Are you sure you want to delete ALL trades? This cannot be undone.')) return;
  try {
    const res = await fetch('/api/trades/clear', { method: 'POST' }).then(r => r.json());
    if (res.success) {
      showToast('All trades cleared from database.');
      refreshCurrentView();
    }
  } catch (err) {
    console.error(err);
  }
}

async function confirmClearSampleTrades() {
  if (!confirm('Remove demo/sample trades? This will keep all your uploaded Quotex trades.')) return;
  try {
    const res = await fetch('/api/trades/clear-sample', { method: 'POST' }).then(r => r.json());
    if (res.success) {
      showToast(res.message || 'Demo trades purged successfully.');
      refreshCurrentView();
    }
  } catch (err) {
    showToast('Error removing demo trades: ' + err.message, 'error');
  }
}

// -------------------------------------------------------------------------
// CSV UPLOAD & SAMPLE DATA (Image 3)
// -------------------------------------------------------------------------
function initSlider() {
  const slider = document.getElementById('payout-slider');
  const badge = document.getElementById('slider-payout-val');
  const preview = document.getElementById('slider-preview-text');
  if (slider) {
    slider.addEventListener('input', (e) => {
      const val = e.target.value;
      if (badge) badge.textContent = `${val}%`;
      const profitSample = (1000 * (val / 100)).toFixed(0);
      if (preview) preview.textContent = `Example: $1,000 investment × ${val}% = +$${profitSample} profit on a win`;
    });
  }
}

function initDropzone() {
  const dropzone = document.getElementById('csv-dropzone');
  const fileInput = document.getElementById('csv-file-input');

  if (!dropzone || !fileInput) return;

  dropzone.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileUpload(e.target.files[0]);
    }
  });
}

async function handleFileUpload(file) {
  if (!file.name.endsWith('.csv') && file.type !== 'text/csv') {
    showToast('Please select a valid CSV file.', 'error');
    return;
  }

  const payout = document.getElementById('payout-slider')?.value || 90;
  const formData = new FormData();
  formData.append('file', file);
  formData.append('payout', payout);

  showToast('Parsing and importing Quotex trades...', 'success');

  try {
    const res = await fetch('/api/upload-csv', {
      method: 'POST',
      body: formData
    }).then(r => r.json());

    if (res.success) {
      showToast(res.message, 'success');
      loadUploadedFiles();
      switchTab('dashboard');
    } else {
      showToast(res.error || 'Failed to parse CSV.', 'error');
    }
  } catch (err) {
    showToast('Error uploading file: ' + err.message, 'error');
  }
}

async function loadSampleData() {
  try {
    showToast('Generating 320 realistic Quotex trades...', 'success');
    const res = await fetch('/api/load-sample', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ count: 320 })
    }).then(r => r.json());

    if (res.success) {
      showToast(res.message, 'success');
      switchTab('dashboard');
      loadDashboardData();
    }
  } catch (err) {
    showToast('Error loading sample data: ' + err.message, 'error');
  }
}

function exportSampleCSV() {
  window.location.href = '/api/export-sample-csv';
}

function exportAllTrades() {
  window.location.href = '/api/export-trades';
}

function backupDatabase() {
  window.location.href = '/api/backup-db';
}

// -------------------------------------------------------------------------
// NEW SINGLE TRADE MODAL
// -------------------------------------------------------------------------
function initNewTradeModal() {
  const btnOpen = document.getElementById('btn-open-new-trade');
  if (btnOpen) {
    btnOpen.addEventListener('click', () => {
      openNewTradeModal();
    });
  }
}

function openNewTradeModal() {
  const modal = document.getElementById('modal-new-trade');
  if (!modal) return;
  
  // Set default current time
  const now = new Date();
  const isoLocal = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  const dateInput = document.getElementById('new-trade-date');
  if (dateInput) dateInput.value = isoLocal;

  modal.classList.add('active');
}

function closeNewTradeModal() {
  const modal = document.getElementById('modal-new-trade');
  if (modal) modal.classList.remove('active');
}

async function submitNewTrade(e) {
  e.preventDefault();
  const asset = document.getElementById('new-trade-asset').value.trim();
  const direction = document.getElementById('new-trade-direction').value;
  const result = document.getElementById('new-trade-result').value;
  const investment = parseFloat(document.getElementById('new-trade-investment').value);
  const payoutRate = parseFloat(document.getElementById('new-trade-payout').value);
  const dateTimeRaw = document.getElementById('new-trade-date').value.replace('T', ' ') + ':00';

  let profit = 0;
  if (result === 'WIN') {
    profit = +(investment * (payoutRate / 100)).toFixed(2);
  } else if (result === 'LOSS') {
    profit = -investment;
  } else {
    profit = 0;
  }

  const payload = {
    trade_id: `QX-M${Date.now().toString().slice(-6)}`,
    date_time: dateTimeRaw,
    asset: asset,
    direction: direction,
    investment: investment,
    payout_rate: payoutRate,
    profit: profit,
    result: result
  };

  try {
    const res = await fetch('/api/trades/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(r => r.json());

    if (res.success) {
      showToast('Trade added successfully!');
      closeNewTradeModal();
      refreshCurrentView();
    } else {
      showToast(res.error || 'Failed to add trade', 'error');
    }
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

// -------------------------------------------------------------------------
// EDIT TRADE MODAL (Requirement 2)
// -------------------------------------------------------------------------
async function openEditTradeModal(tradeId) {
  const modal = document.getElementById('modal-edit-trade');
  if (!modal) return;

  try {
    const res = await fetch(`/api/trades/${tradeId}`).then(r => r.json());
    if (!res.success) {
      showToast(res.error || 'Failed to fetch trade details', 'error');
      return;
    }

    const t = res.trade;
    document.getElementById('edit-trade-id').value = t.id;
    document.getElementById('edit-trade-ticket').value = t.trade_id || '';
    document.getElementById('edit-trade-datetime').value = t.date_time || '';
    document.getElementById('edit-trade-asset').value = t.asset || '';
    document.getElementById('edit-trade-direction').value = t.direction || 'UP';
    document.getElementById('edit-trade-result').value = t.result || 'WIN';
    document.getElementById('edit-trade-investment').value = t.investment != null ? t.investment : '';
    document.getElementById('edit-trade-payout').value = t.payout_rate != null ? t.payout_rate : 85;
    document.getElementById('edit-trade-profit').value = t.profit != null ? t.profit : '';

    modal.classList.add('active');
  } catch (err) {
    showToast('Error loading trade: ' + err.message, 'error');
  }
}

function closeEditTradeModal() {
  const modal = document.getElementById('modal-edit-trade');
  if (modal) modal.classList.remove('active');
}

function autoCalculateEditProfit() {
  const result = document.getElementById('edit-trade-result')?.value;
  const investment = parseFloat(document.getElementById('edit-trade-investment')?.value) || 0;
  const payout = parseFloat(document.getElementById('edit-trade-payout')?.value) || 85;
  const profitInput = document.getElementById('edit-trade-profit');

  if (!profitInput) return;

  if (result === 'WIN') {
    profitInput.value = (investment * (payout / 100)).toFixed(2);
  } else if (result === 'LOSS') {
    profitInput.value = (-investment).toFixed(2);
  } else {
    profitInput.value = '0.00';
  }
}

async function submitEditTrade(e) {
  e.preventDefault();
  const id = document.getElementById('edit-trade-id').value;
  if (!id) return;

  const payload = {
    date_time: document.getElementById('edit-trade-datetime').value.trim(),
    asset: document.getElementById('edit-trade-asset').value.trim(),
    direction: document.getElementById('edit-trade-direction').value,
    result: document.getElementById('edit-trade-result').value,
    investment: parseFloat(document.getElementById('edit-trade-investment').value) || 0,
    payout_rate: parseFloat(document.getElementById('edit-trade-payout').value) || 0,
    profit: parseFloat(document.getElementById('edit-trade-profit').value) || 0
  };

  try {
    const res = await fetch(`/api/trades/update/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(r => r.json());

    if (res.success) {
      showToast('Trade updated successfully!');
      closeEditTradeModal();
      loadTradeHistory(currentHistoryPage);
      if (typeof loadDashboardData === 'function') loadDashboardData();
    } else {
      showToast(res.error || 'Failed to update trade', 'error');
    }
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

// -------------------------------------------------------------------------
// STORED FILES MANAGER (Requirement 2)
// -------------------------------------------------------------------------
function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

async function loadUploadedFiles() {
  const tbody = document.getElementById('files-table-body');
  if (!tbody) return;

  try {
    const res = await fetch('/api/files').then(r => r.json());
    if (!res.success) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--color-loss); padding: 24px;">Failed to load files: ${res.error || 'Unknown error'}</td></tr>`;
      return;
    }

    const files = res.files || [];
    if (files.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-dim); padding: 30px;">No stored files found. Upload a CSV to view it here.</td></tr>`;
      return;
    }

    tbody.innerHTML = files.map(f => `
      <tr>
        <td style="font-weight: 600; color: var(--text-bright);">
          <span style="margin-right: 6px;">📄</span>${escapeHtml(f.original_name || f.filename)}
        </td>
        <td style="font-size: 0.82rem; color: var(--text-muted);">${f.uploaded_at || '—'}</td>
        <td style="text-align: right; font-family: var(--font-mono); font-size: 0.82rem;">${formatFileSize(f.file_size)}</td>
        <td style="text-align: center;">
          <span class="badge" style="background: rgba(33, 150, 243, 0.15); color: #64b5f6; font-size: 0.75rem; padding: 3px 8px; border-radius: 4px;">
            ${f.trades_count} trades
          </span>
        </td>
        <td style="text-align: center; white-space: nowrap;">
          <button class="btn btn-secondary btn-sm" style="padding: 4px 10px; margin-right: 6px;" onclick="downloadUploadedFile(${f.id})" title="Download file">
            ⬇️ Download
          </button>
          <button class="btn btn-danger btn-sm" style="padding: 4px 10px;" onclick="deleteUploadedFile(${f.id})" title="Delete file">
            🗑️ Delete
          </button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Error loading files:', err);
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--color-loss); padding: 24px;">Error: ${err.message}</td></tr>`;
  }
}

function downloadUploadedFile(fileId) {
  window.location.href = `/api/files/download/${fileId}`;
}

async function deleteUploadedFile(fileId) {
  if (!confirm('Are you sure you want to delete this file from storage?')) return;
  try {
    const res = await fetch(`/api/files/delete/${fileId}`, { method: 'POST' }).then(r => r.json());
    if (res.success) {
      showToast('File deleted successfully.');
      loadUploadedFiles();
    } else {
      showToast(res.error || 'Failed to delete file', 'error');
    }
  } catch (err) {
    showToast('Error deleting file: ' + err.message, 'error');
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/[&<>"']/g, function(m) {
    return {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    }[m];
  });
}

