import re

with open('/tmp/infogap.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Add news CSS before </style>
news_css = """
/* ===== Global News ===== */
.tag-news { background: rgba(0,212,170,0.15); color: var(--accent); }
.news-filters {
  display: flex; gap: 8px; flex-wrap: wrap; margin: 0 0 24px;
  padding: 12px 16px; background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 12px; align-items: center;
}
.news-filters-label { color: var(--text3); font-size: 13px; margin-right: 4px; white-space: nowrap; }
.news-filter-btn {
  padding: 5px 12px; border-radius: 16px; border: 1px solid var(--border);
  background: var(--bg); color: var(--text2); cursor: pointer; font-size: 12px;
  transition: all .15s; white-space: nowrap;
}
.news-filter-btn:hover { border-color: var(--accent); color: var(--text); }
.news-filter-btn.active { background: var(--accent); color: #000; border-color: var(--accent); font-weight: 600; }
/* 新闻卡片元信息行：复用 .card .meta 风格，来源靠左、时间靠右 */
.news-meta {
  display: flex; justify-content: space-between; align-items: center;
}
.news-loading { text-align: center; padding: 40px; color: var(--text3); grid-column: 1/-1; }
.news-updated { text-align: right; color: var(--text3); font-size: 11px; margin-bottom: 8px; }
"""

html = html.replace('</style>', news_css + '\n</style>')

# 2. Add 全球新闻 category button
html = html.replace(
    '<button class="cat-btn" data-cat="breakthrough">市场破局</button>',
    '<button class="cat-btn" data-cat="breakthrough">市场破局</button>\n    <button class="cat-btn" data-cat="news">全球新闻</button>'
)

# 3. Add news filters div after categories div
html = html.replace(
    '</div>\n  <div class="stats-row">',
    '</div>\n  <div class="news-filters" id="newsFilters" style="display:none;">'
    '<span class="news-filters-label">选择国家/地区：</span>'
    '<span id="newsCountryBtns"></span>'
    '</div>\n  <div class="stats-row">'
)

# 4. Add news JS before renderCards function
news_js = """
// ===== Global News =====
const NEWS_BASE = 'https://gjbxbsp7tw-ship-it.github.io/infogap/news';
let newsData = [];
let newsCountry = 'US';
let newsLoading = false;

const NEWS_COUNTRIES = [
  { code: 'US', name: '美国' },
  { code: 'GB', name: '英国' },
  { code: 'CN', name: '中国' },
  { code: 'JP', name: '日本' },
  { code: 'KR', name: '韩国' },
  { code: 'DE', name: '德国' },
  { code: 'FR', name: '法国' },
  { code: 'IN', name: '印度' },
  { code: 'BR', name: '巴西' },
  { code: 'AU', name: '澳大利亚' },
  { code: 'CA', name: '加拿大' },
  { code: 'RU', name: '俄罗斯' },
  { code: 'IT', name: '意大利' },
  { code: 'ES', name: '西班牙' },
  { code: 'MX', name: '墨西哥' },
  { code: 'SG', name: '新加坡' },
  { code: 'AE', name: '阿联酋' },
  { code: 'ZA', name: '南非' },
  { code: 'TR', name: '土耳其' },
];

function renderCountryFilters() {
  var html = NEWS_COUNTRIES.map(function(c) {
    var active = c.code === newsCountry ? ' active' : '';
    return '<button class="news-filter-btn' + active + '" data-country="' + c.code + '">' + c.name + '</button>';
  }).join('');
  document.getElementById('newsCountryBtns').innerHTML = html;
}

async function fetchNews(country) {
  if (newsLoading) return;
  newsLoading = true;
  newsCountry = country;
  var grid = document.getElementById('feedGrid');
  grid.innerHTML = '<div class="news-loading">正在加载最新新闻...</div>';
  try {
    var resp = await fetch(NEWS_BASE + '/' + country + '.json');
    var data = await resp.json();
    if (!data.items) throw new Error('No news data');
    newsData = data.items || [];
    document.getElementById('resultHint').textContent = '更新于 ' + new Date(data.updated).toLocaleString('zh-CN');
    renderNewsCards();
  } catch (e) {
    grid.innerHTML = '<div class="news-loading">加载失败：' + e.message + '，<a href="javascript:fetchNews(\\'' + country + '\\')" style="color:var(--accent)">点击重试</a></div>';
  }
  newsLoading = false;
}

function renderNewsCards() {
  var grid = document.getElementById('feedGrid');
  document.getElementById('totalCount').textContent = newsData.length;
  document.getElementById('todayCount').textContent = newsData.length;
  if (!newsData.length) {
    grid.innerHTML = '<div class="no-result">暂无新闻数据</div>';
    return;
  }
  grid.innerHTML = newsData.map(function(d, i) {
    var titleText = d.title_cn || d.title || '';
    var descText = d.description_cn || d.description || '';
    var pubDate = d.pubDate ? new Date(d.pubDate).toLocaleString('zh-CN', { hour12: false }) : '';
    return '<div class="card" onclick="window.open(\\'' + d.link + '\\',\\'_blank\\')">'
      + '<span class="card-tag tag-news">全球新闻</span>'
      + '<h3>' + titleText + '</h3>'
      + '<p>' + descText + '</p>'
      + '<div class="meta news-meta"><span>来源：' + (d.source || '未知') + '</span><span>' + pubDate + '</span></div>'
      + '<div class="cta-hint">在新标签页阅读原文 →</div>'
      + '</div>';
  }).join('');
}

document.getElementById('newsCountryBtns').addEventListener('click', function(e) {
  if (!e.target.classList.contains('news-filter-btn')) return;
  var country = e.target.dataset.country;
  if (!country) return;
  document.querySelectorAll('.news-filter-btn').forEach(function(b) { b.classList.remove('active'); });
  e.target.classList.add('active');
  fetchNews(country);
});
"""

# Insert before the renderCards function
html = html.replace(
    'function renderCards() {',
    news_js + '\nfunction renderCards() {'
)

# 5. Modify renderCards to handle news category
html = html.replace(
    "function renderCards() {\n  const grid = document.getElementById('feedGrid');\n  let filtered = DATA;\n  if (activeCat !== 'all') filtered = filtered.filter(d => d.tag === activeCat);",
    "function renderCards() {\n  var grid = document.getElementById('feedGrid');\n  var filtersDiv = document.getElementById('newsFilters');\n  // 全球新闻走独立渲染\n  if (activeCat === 'news') {\n    if (filtersDiv) filtersDiv.style.display = 'flex';\n    renderCountryFilters();\n    if (!newsData.length) { fetchNews(newsCountry); }\n    else { renderNewsCards(); }\n    return;\n  }\n  if (filtersDiv) filtersDiv.style.display = 'none';\n  let filtered = DATA;\n  if (activeCat !== 'all') filtered = filtered.filter(d => d.tag === activeCat);"
)

# 6. Update data-cat mapping in filter handler for the label mapping
# The existing tag mapping doesn't have 'news', which is fine since news uses its own rendering

with open('/tmp/infogap.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Done. File updated.")
