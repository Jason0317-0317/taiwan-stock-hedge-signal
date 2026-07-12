const state = {
  data: null,
  filter: 'all',
  search: ''
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
      <td>${stock.ticker}<br><span class="muted">${stock.name}</span></td>
      <td class="${stock.signal ? 'danger' : ''}">${formatPercent(stock.riskProbability)}</td>
      <td>${formatPercent(stock.probabilityThreshold)}</td>
      <td class="danger">${stock.downsideThresholdText}</td>
      <td class="${stock.weeklyReturn >= 0 ? 'positive' : 'negative'}">${formatPercent(stock.weeklyReturn, { sign: true })}</td>
      <td><span class="badge ${stock.signal ? 'hedge' : 'hold'}">${stock.action}</span></td>
    </tr>
  `).join('');
};

const render = () => {
  const stocks = visibleStocks();
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
};

fetch('/api/report')
  .then((response) => {
    if (!response.ok) throw new Error('Report data is not available');
    return response.json();
  })
  .then((data) => {
    state.data = data;
    renderHeader();
    bindEvents();
    render();
  })
  .catch(() => {
    document.getElementById('stock-grid').innerHTML = '<div class="empty">目前沒有可讀取的週報資料。</div>';
  });
