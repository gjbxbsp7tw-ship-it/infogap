import re

with open('/tmp/infogap.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Add rates CSS before </style> (inserts alongside existing news_css)
rates_css = """
/* ===== Global Rates ===== */
.rates-dashboard { display: none; }
.rates-dashboard.active { display: block; }
.rates-summary { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; margin-bottom: 24px; }
.rate-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 16px; transition: all .2s; }
.rate-card:hover { border-color: var(--accent); transform: translateY(-2px); box-shadow: 0 4px 20px rgba(0,212,170,0.1); }
.rate-card .currency-code { font-size: 12px; color: var(--text3); margin-bottom: 4px; }
.rate-card .currency-name { font-size: 13px; color: var(--text2); margin-bottom: 8px; }
.rate-card .rate-value { font-size: 24px; font-weight: 700; color: var(--text); }
.rate-card .rate-change { font-size: 12px; margin-top: 6px; }
.rate-up { color: #22c55e; }
.rate-down { color: #ef4444; }
.rates-chart-container { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 24px; margin-bottom: 24px; }
.rates-chart-container h3 { margin: 0 0 16px; font-size: 16px; color: var(--text); }
.rates-chart-wrapper { position: relative; width: 100%; height: 400px; }
.rates-currency-selector { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
.rates-currency-btn { padding: 4px 10px; border-radius: 14px; border: 1px solid var(--border); background: var(--bg); color: var(--text2); cursor: pointer; font-size: 12px; transition: all .15s; }
.rates-currency-btn:hover { border-color: var(--accent); color: var(--text); }
.rates-currency-btn.active { background: var(--accent); color: #000; border-color: var(--accent); font-weight: 600; }
.rates-prediction { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 24px; margin-bottom: 24px; }
.rates-prediction h3 { margin: 0 0 12px; font-size: 16px; color: var(--text); }
.rates-prediction p { color: var(--text2); font-size: 14px; line-height: 1.8; }
.rates-prediction .pred-tag { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; margin-right: 6px; }
.pred-bullish { background: rgba(34,197,94,0.15); color: #22c55e; }
.pred-bearish { background: rgba(239,68,68,0.15); color: #ef4444; }
.pred-neutral { background: rgba(148,163,184,0.15); color: #94a3b8; }
.rates-loading { text-align: center; padding: 40px; color: var(--text3); }
"""

html = html.replace('</style>', rates_css + '\n</style>')

# 2. Add Chart.js CDN before </head>
html = html.replace('</head>', '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>\n</head>')

# 3. Add 全球汇率 category button after 全球新闻 button
html = html.replace(
    '<button class="cat-btn" data-cat="news">全球新闻</button>',
    '<button class="cat-btn" data-cat="news">全球新闻</button>\n    <button class="cat-btn" data-cat="rates">全球汇率</button>'
)

# 4. Add rates dashboard HTML after news-filters div
html = html.replace(
    '</div>\n  <div class="news-filters" id="newsFilters" style="display:none;">'
    '<span class="news-filters-label">选择国家/地区：</span>'
    '<span id="newsCountryBtns"></span>'
    '</div>\n  <div class="stats-row">',
    '</div>\n  <div class="news-filters" id="newsFilters" style="display:none;">'
    '<span class="news-filters-label">选择国家/地区：</span>'
    '<span id="newsCountryBtns"></span>'
    '</div>\n'
    '<div class="rates-dashboard" id="ratesDashboard">'
    '<div class="rates-chart-container">'
    '<h3>人民币汇率走势（近3年）</h3>'
    '<div class="rates-currency-selector" id="ratesCurrencySelector"></div>'
    '<div class="rates-chart-wrapper"><canvas id="ratesChart"></canvas></div>'
    '</div>'
    '<h3 style="margin-bottom:12px;color:var(--text);">最新汇率（1 CNY = ）</h3>'
    '<div class="rates-summary" id="ratesSummary"></div>'
    '<div class="rates-prediction" id="ratesPrediction"></div>'
    '</div>\n'
    '  <div class="stats-row">'
)

# 5. Add rates JS before renderCards function
rates_js = """
// ===== Global Rates =====
const RATES_BASE = 'https://gjbxbsp7tw-ship-it.github.io/infogap/rates';
let ratesData = null;
let ratesChart = null;
let selectedRateCurrency = 'USD';

const CURRENCY_NAMES = {"USD":"美元","EUR":"欧元","JPY":"日元","GBP":"英镑","AUD":"澳元","CAD":"加元","CHF":"瑞郎","HKD":"港元","KRW":"韩元","SGD":"新元","NZD":"纽元","THB":"泰铢"};

async function fetchRates() {
  try {
    var resp = await fetch(RATES_BASE + '/cny_rates.json');
    ratesData = await resp.json();
    renderRatesUI();
  } catch(e) {
    document.getElementById('ratesSummary').innerHTML = '<div class="rates-loading">汇率数据加载失败：' + e.message + '</div>';
  }
}

function renderRatesUI() {
  var currencies = Object.keys(ratesData.latest);
  var btnHtml = currencies.map(function(c) {
    var active = c === selectedRateCurrency ? ' active' : '';
    return '<button class="rates-currency-btn' + active + '" data-currency="' + c + '">' + (CURRENCY_NAMES[c] || c) + '</button>';
  }).join('');
  document.getElementById('ratesCurrencySelector').innerHTML = btnHtml;
  renderRatesSummary();
  renderRatesChart();
  renderRatesPrediction();
}

function renderRatesSummary() {
  var currencies = Object.keys(ratesData.latest);
  var html = currencies.map(function(c) {
    var rate = ratesData.latest[c];
    var history = ratesData.history;
    var prevRate = null;
    if (history.length >= 2) {
      var prev = history[history.length - 2];
      if (prev && prev.rates && prev.rates[c]) prevRate = prev.rates[c];
    }
    var changeHtml = '';
    if (prevRate) {
      var changePct = ((rate - prevRate) / prevRate * 100).toFixed(2);
      var cls = changePct >= 0 ? 'rate-up' : 'rate-down';
      var sign = changePct >= 0 ? '+' : '';
      changeHtml = '<div class="rate-change ' + cls + '">' + sign + changePct + '% (月)</div>';
    }
    return '<div class="rate-card">'
      + '<div class="currency-code">' + c + '</div>'
      + '<div class="currency-name">' + (CURRENCY_NAMES[c] || c) + '</div>'
      + '<div class="rate-value">' + rate.toFixed(4) + '</div>'
      + changeHtml
      + '</div>';
  }).join('');
  document.getElementById('ratesSummary').innerHTML = html;
}

function renderRatesChart() {
  var ctx = document.getElementById('ratesChart').getContext('2d');
  if (ratesChart) ratesChart.destroy();
  var history = ratesData.history;
  var labels = history.map(function(h) { return h.date.substring(0, 7); });
  var data = history.map(function(h) { return h.rates[selectedRateCurrency] || null; });
  var sma = [];
  for (var i = 0; i < data.length; i++) {
    if (i < 2) { sma.push(null); continue; }
    sma.push((data[i] + data[i-1] + data[i-2]) / 3);
  }
  var n = data.length;
  var sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;
  var validN = 0;
  for (var i = 0; i < n; i++) {
    if (data[i] === null) continue;
    sumX += i; sumY += data[i]; sumXY += i * data[i]; sumX2 += i * i;
    validN++;
  }
  var slope = (validN * sumXY - sumX * sumY) / (validN * sumX2 - sumX * sumX);
  var intercept = (sumY - slope * sumX) / validN;
  var predictLabels = [];
  var predictData = [];
  var lastDate = new Date(history[history.length-1].date);
  for (var i = 1; i <= 3; i++) {
    var nextMonth = new Date(lastDate);
    nextMonth.setMonth(nextMonth.getMonth() + i);
    var dateStr = nextMonth.toISOString().substring(0, 7);
    predictLabels.push(dateStr);
    predictData.push(intercept + slope * (n + i));
  }
  var residuals = [];
  for (var i = 0; i < n; i++) {
    if (data[i] === null) continue;
    var predicted = intercept + slope * i;
    residuals.push(Math.abs(data[i] - predicted));
  }
  residuals.sort(function(a,b) { return a - b; });
  var mad = residuals[Math.floor(residuals.length / 2)] * 1.4826;
  var upper = predictData.map(function(v) { return v + mad * 1.5; });
  var lower = predictData.map(function(v) { return v - mad * 1.5; });
  ratesChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels.concat(predictLabels),
      datasets: [
        { label: '实际汇率', data: data.concat(Array(predictLabels.length).fill(null)), borderColor: '#00d4aa', backgroundColor: 'rgba(0,212,170,0.1)', fill: true, tension: 0.3, pointRadius: 2, borderWidth: 2 },
        { label: '3月均线', data: sma.concat(Array(predictLabels.length).fill(null)), borderColor: '#60a5fa', borderWidth: 1.5, borderDash: [4,4], pointRadius: 0, fill: false },
        { label: '趋势预测', data: Array(labels.length).fill(null).concat(predictData), borderColor: '#f59e0b', borderWidth: 2, borderDash: [6,3], pointRadius: 3, pointBackgroundColor: '#f59e0b', fill: false },
        { label: '预测上界', data: Array(labels.length).fill(null).concat(upper), borderColor: 'rgba(245,158,11,0.3)', borderWidth: 1, borderDash: [2,4], pointRadius: 0, fill: false },
        { label: '预测下界', data: Array(labels.length).fill(null).concat(lower), borderColor: 'rgba(245,158,11,0.3)', borderWidth: 1, borderDash: [2,4], pointRadius: 0, fill: false }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { position: 'bottom', labels: { color: '#94a3b8', usePointStyle: true, padding: 20, font: { size: 11 } } },
        tooltip: { callbacks: { label: function(ctx) { return ctx.dataset.label + ': ' + (ctx.parsed.y ? ctx.parsed.y.toFixed(4) : 'N/A'); } } }
      },
      scales: {
        x: { ticks: { color: '#64748b', maxTicksLimit: 12, font: { size: 10 } }, grid: { color: 'rgba(148,163,184,0.1)' } },
        y: { ticks: { color: '#64748b', font: { size: 10 }, callback: function(v) { return v.toFixed(4); } }, grid: { color: 'rgba(148,163,184,0.1)' } }
      }
    }
  });
}

function renderRatesPrediction() {
  var history = ratesData.history;
  var data = history.map(function(h) { return h.rates[selectedRateCurrency]; }).filter(function(v) { return v !== null && v !== undefined; });
  var n = data.length;
  var sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;
  for (var i = 0; i < n; i++) { sumX += i; sumY += data[i]; sumXY += i * data[i]; sumX2 += i * i; }
  var slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
  var recentAvg = 0, olderAvg = 0;
  var halfN = Math.floor(n / 2);
  for (var i = halfN; i < n; i++) recentAvg += data[i];
  for (var i = 0; i < halfN; i++) olderAvg += data[i];
  recentAvg /= (n - halfN); olderAvg /= halfN;
  var trendPct = ((recentAvg - olderAvg) / olderAvg * 100);
  var currencyName = CURRENCY_NAMES[selectedRateCurrency] || selectedRateCurrency;
  var trendTag, trendLabel;
  if (trendPct > 1) { trendTag = 'pred-bullish'; trendLabel = '看涨'; }
  else if (trendPct < -1) { trendTag = 'pred-bearish'; trendLabel = '看跌'; }
  else { trendTag = 'pred-neutral'; trendLabel = '震荡'; }
  var latestRate = ratesData.latest[selectedRateCurrency];
  var predictRate = latestRate * (1 + trendPct / 100 / 3);
  var html = '<h3>趋势预测与分析 <span class="pred-tag ' + trendTag + '">' + trendLabel + '</span></h3>';
  html += '<p>';
  html += '<strong>' + currencyName + '（' + selectedRateCurrency + '）</strong>近半年较前半年变动 <strong>' + (trendPct > 0 ? '+' : '') + trendPct.toFixed(2) + '%</strong>。<br>';
  html += '当前汇率：<strong>1 CNY = ' + latestRate.toFixed(4) + ' ' + selectedRateCurrency + '</strong>。<br>';
  if (Math.abs(trendPct) > 0.5) {
    html += '基于线性回归模型，未来1个月预计汇率约 <strong>' + predictRate.toFixed(4) + '</strong>，';
    html += '整体呈<span class="' + trendTag + '">' + trendLabel + '</span>趋势。<br>';
  } else {
    html += '近期走势平稳，预计未来1个月维持窄幅震荡。<br>';
  }
  var factors = getCurrencyFactors(selectedRateCurrency);
  html += '<br><strong>影响因素：</strong><br>' + factors;
  html += '</p>';
  document.getElementById('ratesPrediction').innerHTML = html;
}

function getCurrencyFactors(code) {
  var factors = {
    'USD': '美联储货币政策（利率决议、缩表进程）、美国通胀数据（CPI/PCE）、中美贸易关系、美国大选及财政政策走向。',
    'EUR': '欧央行利率政策、欧元区通胀与经济增长数据、能源价格（天然气）、地缘政治风险（乌克兰局势）。',
    'JPY': '日本央行货币政策正常化进程（YCC调整）、日美利差、日本通胀数据、全球避险情绪。',
    'GBP': '英国央行利率决策、英国经济数据（GDP/CPI）、脱欧后贸易协定进展、英国财政政策。',
    'AUD': '澳洲联储利率政策、大宗商品价格（铁矿石/煤炭）、中国经济数据（最大贸易伙伴）、全球风险偏好。',
    'CAD': '加拿大央行利率决策、原油价格、加拿大经济数据、美加贸易关系。',
    'CHF': '瑞士央行政策利率、全球避险需求、瑞士通胀水平、欧元区经济溢出效应。',
    'HKD': '联系汇率制度（7.75-7.85区间）、美联储政策传导、香港经济与房市、内地与香港资本流动。',
    'KRW': '韩国央行利率、半导体出口数据、中美贸易摩擦间接影响、韩元国际化程度。',
    'SGD': '新加坡金管局汇率政策（NEER篮子）、新加坡经济增速、区域贸易环境、全球金融中心地位。',
    'NZD': '新西兰联储利率、乳制品出口价格、全球农业大宗商品走势、亚太区域经济。',
    'THB': '泰国央行利率、旅游业恢复程度、出口数据、东南亚地缘政治、泰铢国际化。'
  };
  return factors[code] || '该货币受全球经济环境、本国央行政策及贸易状况综合影响。';
}

document.getElementById('ratesCurrencySelector').addEventListener('click', function(e) {
  if (!e.target.classList.contains('rates-currency-btn')) return;
  var currency = e.target.dataset.currency;
  if (!currency) return;
  document.querySelectorAll('.rates-currency-btn').forEach(function(b) { b.classList.remove('active'); });
  e.target.classList.add('active');
  selectedRateCurrency = currency;
  renderRatesChart();
  renderRatesPrediction();
});
"""

# Insert rates_js before renderCards (news_js is already there from previous build)
html = html.replace(
    'function renderCards() {',
    rates_js + '\nfunction renderCards() {'
)

# 6. Modify renderCards to handle rates category (already modified for news)
# The original renderCards now starts with news handling. We need to add rates handling.
html = html.replace(
    "function renderCards() {\n  var grid = document.getElementById('feedGrid');\n  var filtersDiv = document.getElementById('newsFilters');\n  // 全球新闻走独立渲染\n  if (activeCat === 'news') {",
    "function renderCards() {\n  var grid = document.getElementById('feedGrid');\n  var filtersDiv = document.getElementById('newsFilters');\n  var ratesDashboard = document.getElementById('ratesDashboard');\n  // 全球新闻走独立渲染\n  if (activeCat === 'news') {\n    if (ratesDashboard) ratesDashboard.classList.remove('active');"
)

# Also need to add rates handling block before the news' "if (filtersDiv) filtersDiv.style.display = 'none';" line
html = html.replace(
    "  if (filtersDiv) filtersDiv.style.display = 'none';\n  let filtered = DATA;",
    "  // 全球汇率走独立渲染\n  if (activeCat === 'rates') {\n    if (filtersDiv) filtersDiv.style.display = 'none';\n    if (ratesDashboard) ratesDashboard.classList.add('active');\n    if (!ratesData) { fetchRates(); }\n    document.getElementById('feedGrid').innerHTML = '';\n    document.getElementById('totalCount').textContent = '0';\n    document.getElementById('todayCount').textContent = '0';\n    document.getElementById('resultHint').textContent = '';\n    return;\n  }\n  if (filtersDiv) filtersDiv.style.display = 'none';\n  if (ratesDashboard) ratesDashboard.classList.remove('active');\n  let filtered = DATA;"
)

# 7. Add chart resize handler before </body>
html = html.replace(
    '</body>',
    '<script>window.addEventListener("resize",function(){if(ratesChart&&document.getElementById("ratesDashboard").classList.contains("active")){ratesChart.resize();}});</script>\n</body>'
)

with open('/tmp/infogap.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Done. File updated.")
