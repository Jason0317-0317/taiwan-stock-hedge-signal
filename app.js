const state = {
  data: null,
  filter: 'all',
  search: '',
  charts: {}
};

const palette = {
  ink: '#172026',
  muted: '#687783',
  line: '#d8e0e6',
  green: '#15855f',
  red: '#b3261e',
  amber: '#996515',
  blue: '#166c8c',
  steel: '#24323d'
};

const formatPercent = (value, options = {}) => {
  if (typeof value !== 'number' || Number.isNaN(value)) return '-';
  const sign = options.sign && value > 0 ? '+' : '';
  return `${sign}${(value * 100).toFixed(options.digits ?? 1)}%`;
};

const clampPercent = (value) => {
  if (typeof value !== 'number' || Number.isNaN(value)) return 0;
  return Math.max(0, Math.min(100, value * 100));
};

const loadReportData = async () => {
  const candidates = ['api/report', 'report-data.json'];
  let lastError;
  for (const url of candidates) {
    try {
      const response = await fetch(url, { cache: 'no-store' });
      if (!response.ok) throw new Error(`${url} returned ${response.status}`);
      return await response.json();
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError || new Error('Report data is not available');
};

const visibleStocks = () => {
  if (!state.data) return [];
  const q = state.search.trim().toLowerCase();
  return state.data.stocks.filter((stock) => {
    const matchesFilter = state.filter === 'all'
      || (state.filter === 'hedge' && stock.signal)
      || (state.filter === 'hold' && !stock.signal);
    const matchesSearch = !q
      || stock.ticker.toLowerCase().includes(q)
      || stock.name.toLowerCase().includes(q);
    return matchesFilter && matchesSearch;
  });
};

const renderHeader = () => {
  document.getElementById('latest-date').textContent = state.data.latestDate;
  document.getElementById('stock-count').textContent = state.data.stockCount;
  document.getElementById('hedge-count').textContent = state.data.hedgeCount;
  document.getElementById('market-code').textContent = state.data.market;
  document.getElementById('disclaimer').textContent = state.data.disclaimer;
};

const chartDefaults = () => {
  if (!window.Chart) return;
  Chart.defaults.font.family = 'Noto Sans TC, system-ui, sans-serif';
  Chart.defaults.color = palette.muted;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.tooltip.backgroundColor = palette.steel;
  Chart.defaults.plugins.tooltip.padding = 12;
  Chart.defaults.plugins.tooltip.cornerRadius = 6;
};

const destroyChart = (key) => {
  if (state.charts[key]) {
    state.charts[key].destroy();
    state.charts[key] = null;
  }
};

const isSmallViewport = () => window.matchMedia('(max-width: 560px)').matches;

const renderRiskRankingChart = (stocks) => {
  destroyChart('riskRanking');
  const ctx = document.getElementById('risk-ranking-chart');
  const sorted = [...stocks].sort((a, b) => b.riskProbability - a.riskProbability);
  const small = isSmallViewport();

  state.charts.riskRanking = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: sorted.map((stock) => small ? stock.name : `${stock.name} ${stock.ticker}`),
      datasets: [
        {
          label: '風險機率',
          data: sorted.map((stock) => stock.riskProbability * 100),
          backgroundColor: sorted.map((stock) => stock.signal ? palette.red : palette.blue),
          borderRadius: 6,
          barThickness: small ? 14 : 18
        },
        {
          label: '機率門檻',
          data: sorted.map((stock) => stock.probabilityThreshold * 100),
          backgroundColor: 'rgba(153, 101, 21, 0.34)',
          borderRadius: 6,
          barThickness: small ? 14 : 18
        }
      ]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          beginAtZero: true,
          grid: { color: 'rgba(216, 224, 230, 0.8)' },
          ticks: { callback: (value) => `${value}%`, maxTicksLimit: small ? 4 : 8 }
        },
        y: { grid: { display: false }, ticks: { font: { size: small ? 11 : 12 } } }
      },
      plugins: {
        legend: { position: small ? 'bottom' : 'top' },
        tooltip: {
          callbacks: {
            label: (context) => `${context.dataset.label}: ${context.parsed.x.toFixed(1)}%`
          }
        }
      }
    }
  });
};

const renderSignalDonutChart = (stocks) => {
  destroyChart('signalDonut');
  const ctx = document.getElementById('signal-donut-chart');
  const hedge = stocks.filter((stock) => stock.signal).length;
  const hold = stocks.length - hedge;

  state.charts.signalDonut = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['建議對沖', '正常持有'],
      datasets: [{
        data: [hedge, hold],
        backgroundColor: [palette.red, palette.green],
        borderColor: '#ffffff',
        borderWidth: 4,
        hoverOffset: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '62%',
      plugins: {
        legend: { position: 'bottom' },
        tooltip: {
          callbacks: {
            label: (context) => `${context.label}: ${context.parsed} 檔`
          }
        }
      }
    }
  });
};

const renderRiskReturnChart = (stocks) => {
  destroyChart('riskReturn');
  const ctx = document.getElementById('risk-return-chart');
  const small = isSmallViewport();

  state.charts.riskReturn = new Chart(ctx, {
    type: 'scatter',
    data: {
      datasets: [
        {
          label: '正常持有',
          data: stocks.filter((stock) => !stock.signal).map((stock) => ({
            x: stock.weeklyReturn * 100,
            y: stock.riskProbability * 100,
            stock
          })),
          backgroundColor: palette.green,
          pointRadius: small ? 5 : 6,
          pointHoverRadius: 8
        },
        {
          label: '建議對沖',
          data: stocks.filter((stock) => stock.signal).map((stock) => ({
            x: stock.weeklyReturn * 100,
            y: stock.riskProbability * 100,
            stock
          })),
          backgroundColor: palette.red,
          pointRadius: small ? 6 : 7,
          pointHoverRadius: 9
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          title: { display: !small, text: '上週報酬' },
          grid: { color: 'rgba(216, 224, 230, 0.8)' },
          ticks: { callback: (value) => `${value}%`, maxTicksLimit: small ? 5 : 8 }
        },
        y: {
          beginAtZero: true,
          title: { display: !small, text: '風險機率' },
          grid: { color: 'rgba(216, 224, 230, 0.8)' },
          ticks: { callback: (value) => `${value}%`, maxTicksLimit: small ? 5 : 8 }
        }
      },
      plugins: {
        legend: { position: 'bottom' },
        tooltip: {
          callbacks: {
            title: (items) => {
              const stock = items[0].raw.stock;
              return `${stock.name} ${stock.ticker}`;
            },
            label: (context) => [
              `風險機率: ${context.raw.y.toFixed(1)}%`,
              `上週報酬: ${context.raw.x.toFixed(1)}%`,
              `建議行動: ${context.raw.stock.action}`
            ]
          }
        }
      }
    }
  });
};

const renderTrendChart = (stocks) => {
  destroyChart('trend');
  const ctx = document.getElementById('trend-chart');
  const small = isSmallViewport();
  const selected = [...stocks]
    .sort((a, b) => b.riskProbability - a.riskProbability)
    .slice(0, small ? 3 : 5);
  const labels = selected[0]?.history?.slice().reverse().map((item) => item.date.slice(5)) || [];
  const colors = [palette.red, palette.blue, palette.green, palette.amber, palette.steel];

  state.charts.trend = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: selected.map((stock, index) => ({
        label: small ? stock.name : `${stock.name} ${stock.ticker}`,
        data: (stock.history || []).slice().reverse().map((item) => item.riskProbability * 100),
        borderColor: colors[index % colors.length],
        backgroundColor: colors[index % colors.length],
        borderWidth: 2,
        tension: 0.28,
        pointRadius: small ? 2 : 3,
        pointHoverRadius: 6
      }))
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { grid: { display: false } },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(216, 224, 230, 0.8)' },
          ticks: { callback: (value) => `${value}%`, maxTicksLimit: small ? 5 : 8 }
        }
      },
      plugins: {
        legend: { position: 'bottom' },
        tooltip: {
          callbacks: {
            label: (context) => `${context.dataset.label}: ${context.parsed.y.toFixed(1)}%`
          }
        }
      }
    }
  });
};

const renderCharts = (stocks) => {
  if (!window.Chart) return;
  renderRiskRankingChart(stocks);
  renderSignalDonutChart(stocks);
  renderRiskReturnChart(stocks);
  renderTrendChart(stocks);
};

const renderCards = (stocks) => {
  const grid = document.getElementById('stock-grid');
  if (!stocks.length) {
    grid.innerHTML = '<div class="empty">沒有符合條件的股票。</div>';
    return;
  }

  grid.innerHTML = stocks.map((stock) => {
    const riskWidth = clampPercent(stock.riskProbability);
    const history = (stock.history || []).slice(0, 6).reverse();
    const historyBars = history.length
      ? history.map((item) => {
          const height = Math.max(8, clampPercent(item.riskProbability) * 0.72);
          const date = item.date.slice(5);
          return `<div class="history-bar ${item.signal ? 'hedge' : ''}" title="${item.date} 風險機率 ${formatPercent(item.riskProbability)}">
            <i style="height:${height}px"></i>
            <span>${date}</span>
          </div>`;
        }).join('')
      : '<div class="empty">等待歷史資料</div>';

    return `<article class="stock-card">
      <div class="card-head">
        <div class="identity">
          <strong>${stock.name}</strong>
          <span>${stock.ticker}</span>
        </div>
        <span class="badge ${stock.signal ? 'hedge' : 'hold'}">${stock.action}</span>
      </div>
      <div class="probability">
        <div class="value">
          <strong class="${stock.signal ? 'danger' : ''}">${formatPercent(stock.riskProbability)}</strong>
          <span>門檻 ${formatPercent(stock.probabilityThreshold)}</span>
        </div>
        <div class="risk-track"><div class="risk-fill" style="width:${riskWidth}%"></div></div>
      </div>
      <div class="card-metrics">
        <div class="metric-cell">
          <span>尾部跌幅門檻</span>
          <strong class="danger">${stock.downsideThresholdText}</strong>
        </div>
        <div class="metric-cell">
          <span>上週報酬</span>
          <strong class="${stock.weeklyReturn >= 0 ? 'positive' : 'negative'}">${formatPercent(stock.weeklyReturn, { sign: true })}</strong>
        </div>
        <div class="metric-cell">
          <span>資料週次</span>
          <strong>${stock.latestDate}</strong>
        </div>
      </div>
      <div class="history">
        <div class="history-title">近 6 週風險機率</div>
        <div class="history-bars">${historyBars}</div>
      </div>
    </article>`;
  }).join('');
};

const renderTable = (stocks) => {
  document.getElementById('table-count').textContent = `${stocks.length} 檔`;
  document.getElementById('summary-body').innerHTML = stocks.map((stock) => `
    <tr>
      <td data-label="股票">${stock.ticker}<br><span class="muted">${stock.name}</span></td>
      <td data-label="風險機率" class="${stock.signal ? 'danger' : ''}">${formatPercent(stock.riskProbability)}</td>
      <td data-label="機率門檻">${formatPercent(stock.probabilityThreshold)}</td>
      <td data-label="尾部跌幅門檻" class="danger">${stock.downsideThresholdText}</td>
      <td data-label="上週報酬" class="${stock.weeklyReturn >= 0 ? 'positive' : 'negative'}">${formatPercent(stock.weeklyReturn, { sign: true })}</td>
      <td data-label="建議行動"><span class="badge ${stock.signal ? 'hedge' : 'hold'}">${stock.action}</span></td>
    </tr>
  `).join('');
};

const render = () => {
  const stocks = visibleStocks();
  renderCharts(stocks);
  renderCards(stocks);
  renderTable(stocks);
};

const bindEvents = () => {
  document.querySelectorAll('.tab').forEach((button) => {
    button.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach((item) => item.classList.remove('active'));
      button.classList.add('active');
      state.filter = button.dataset.filter;
      render();
    });
  });

  document.getElementById('stock-search').addEventListener('input', (event) => {
    state.search = event.target.value;
    render();
  });

  window.addEventListener('resize', () => {
    clearTimeout(state.resizeTimer);
    state.resizeTimer = setTimeout(render, 150);
  });
};

loadReportData()
  .then((data) => {
    state.data = data;
    chartDefaults();
    renderHeader();
    bindEvents();
    render();
  })
  .catch(() => {
    document.getElementById('stock-grid').innerHTML = '<div class="empty">目前沒有可讀取的週報資料。</div>';
  });
