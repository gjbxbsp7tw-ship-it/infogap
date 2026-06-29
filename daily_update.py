#!/usr/bin/env python3
"""
InfoGap 每日自动信息差更新脚本
功能：从多个信息源获取最新信息差内容，追加到 index.html 的 DATA 数组中。

使用方式：
  1. 手动执行：python3 daily_update.py
  2. 定时任务（macOS launchd / Linux cron）：
     # 每天上午9点执行
     0 9 * * * cd /path/to/infogap && python3 daily_update.py >> logs/update.log 2>&1

环境要求：
  - Python 3.9+
  - pip install feedparser requests beautifulsoup4
  - Git 已配置并可推送

信息源（可扩展）：
  - Hacker News API (news.ycombinator.com)
  - Reddit r/digitalnomad, r/SaaS, r/Entrepreneur
  - Product Hunt
  - 各移民局官网 RSS
"""

import json
import os
import re
import sys
import time
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# ==================== 配置 ====================
REPO_DIR = Path(__file__).parent.resolve()
INDEX_FILE = REPO_DIR / "index.html"
LOG_DIR = REPO_DIR / "logs"
BACKUP_DIR = REPO_DIR / "backups"

# GitHub 配置（建议使用环境变量存放 Token）
GITHUB_REMOTE = os.environ.get("INFOGAP_GITHUB_REMOTE", "origin")
GITHUB_BRANCH = os.environ.get("INFOGAP_GITHUB_BRANCH", "main")

# 信息源配置
RSS_FEEDS = {
    "tech": [
        "https://hnrss.org/frontpage?points=50",
        "https://www.producthunt.com/feed",
    ],
    "money": [
        "https://www.reddit.com/r/SaaS/.rss",
        "https://www.reddit.com/r/Entrepreneur/.rss",
    ],
    "life": [
        "https://www.reddit.com/r/digitalnomad/.rss",
    ],
}

# 分类关键词映射
CATEGORY_KEYWORDS = {
    "money": [
        "赚钱", "副业", "套利", "变现", "创业", "收入", "利润", "跨境电商",
        "自由职业", "数字游民收入", "被动收入", "投资回报", "affiliate",
        "dropshipping", "side hustle", "passive income", "SaaS", "freelance",
        "arbitrage", "monetize", "revenue", "profit",
    ],
    "immigration": [
        "移民", "签证", "绿卡", "护照", "入籍", "永居", "工签", "居留",
        "visa", "immigration", "green card", "citizenship", "residency",
        "work permit", "digital nomad visa", "golden visa",
    ],
    "tech": [
        "AI", "人工智能", "量子", "区块链", "生物科技", "新能源", "太空",
        "脑机", "基因编辑", "核聚变", "机器人", "自动驾驶", "Web3",
        "artificial intelligence", "quantum", "blockchain", "biotech",
        "fusion", "robotics", "LLM", "GPT", "neural",
    ],
    "arbitrage": [
        "价差", "套利", "信息差", "汇率", "地域套利", "税收洼地", "监管套利",
        "arbitrage", "spread", "tax haven", "regulatory arbitrage",
        "geo-arbitrage", "interest rate differential",
    ],
    "life": [
        "海外生活", "数字游民", "生活成本", "城市推荐", "海外就医",
        "国际教育", "海外置业", "银行开户", "expat", "nomad",
        "cost of living", "relocation", "retire abroad",
    ],
    "breakthrough": [
        "出海", "本土化", "国际化", "海外市场", "跨国", "出口",
        "global expansion", "market entry", "localization",
        "international", "cross-border", "overseas",
    ],
}

TAG_MAP = {
    "money": "赚钱机会",
    "immigration": "移民政策",
    "tech": "科技前沿",
    "arbitrage": "信息套利",
    "life": "海外生活",
    "breakthrough": "市场破局",
}


# ==================== 工具函数 ====================

def log(msg: str, level: str = "INFO"):
    """日志输出"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)


def ensure_dirs():
    """创建必要目录"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def backup_html():
    """备份当前 index.html"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"index_{ts}.html"
    if INDEX_FILE.exists():
        backup_path.write_text(INDEX_FILE.read_text(), encoding="utf-8")
        log(f"已备份到 {backup_path}")
    return backup_path


def get_next_id(html_content: str) -> int:
    """从 HTML 中解析当前最大 ID，返回下一个可用 ID"""
    ids = re.findall(r'id:\s*(\d+)', html_content)
    if ids:
        return max(int(i) for i in ids) + 1
    return 1


def get_entry_count(html_content: str) -> int:
    """统计当前条目数"""
    return len(re.findall(r'id:\s*\d+', html_content))


def insert_entries(html_content: str, entries: list) -> str:
    """将新条目插入 DATA 数组末尾（在 ]; 之前）"""
    # 找到 DATA 数组的结束位置: "];\n\nfunction renderCards"
    end_marker = '];\n\nfunction renderCards()'
    end_pos = html_content.find(end_marker)
    if end_pos < 0:
        # 尝试宽松匹配
        end_marker = '];\n\nlet activeCat'
        end_pos = html_content.find(end_marker)
    if end_pos < 0:
        end_marker = '];\n\nfunction '
        end_pos = html_content.find(end_marker)
    if end_pos < 0:
        raise ValueError("无法找到 DATA 数组结束位置")

    # 构建新增条目的 JS 代码
    new_entries_js = build_entries_js(entries)

    # 在 ]; 之前插入
    new_html = html_content[:end_pos] + new_entries_js + '\n' + html_content[end_pos:]
    return new_html


def build_entries_js(entries: list) -> str:
    """将条目列表转换为 JS 对象字符串"""
    def esc_sq(s):
        return s.replace('\\', '\\\\').replace("'", "\\'")

    def esc_bt(s):
        return s.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')

    lines = []
    for i, entry in enumerate(entries):
        is_last = (i == len(entries) - 1)
        comma = '' if is_last else ','

        lines.append('  {')
        lines.append(
            f'    id: {entry["id"]}, tag: \'{entry["tag"]}\', '
            f'date: \'{entry["date"]}\', isNew: true,'
        )
        lines.append(f'    title: \'{esc_sq(entry["title"])}\',')
        lines.append(f'    summary: \'{esc_sq(entry["summary"])}\',')
        lines.append(f'    detail: `{esc_bt(entry["detail"])}`,')
        lines.append(f'    source: \'{esc_sq(entry["source"])}\'')
        lines.append(f'  }}{comma}')

    return '\n'.join(lines)


def git_commit_and_push():
    """提交并推送到 GitHub"""
    try:
        subprocess.run(
            ["git", "add", "index.html"],
            cwd=REPO_DIR, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m",
             f"auto: 每日信息差更新 {datetime.now().strftime('%Y-%m-%d')}"],
            cwd=REPO_DIR, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "push", GITHUB_REMOTE, GITHUB_BRANCH],
            cwd=REPO_DIR, check=True, capture_output=True, timeout=60
        )
        log("Git 提交并推送成功")
        return True
    except subprocess.CalledProcessError as e:
        log(f"Git 操作失败: {e.stderr.decode() if e.stderr else str(e)}", "ERROR")
        return False
    except subprocess.TimeoutExpired:
        log("Git push 超时", "ERROR")
        return False


# ==================== 信息采集模块 ====================

def fetch_rss_feeds() -> list:
    """从 RSS 源获取最新信息"""
    try:
        import feedparser
    except ImportError:
        log("feedparser 未安装，跳过 RSS 采集。安装: pip install feedparser", "WARN")
        return []

    results = []
    for category, feeds in RSS_FEEDS.items():
        for url in feeds:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:10]:  # 每个源取最新10条
                    results.append({
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "summary": entry.get("summary", ""),
                        "published": entry.get("published", ""),
                        "source_feed": url,
                        "category_hint": category,
                    })
                log(f"RSS {url}: 获取 {len(feed.entries[:10])} 条")
            except Exception as e:
                log(f"RSS {url} 失败: {e}", "WARN")
                continue

    return results


def fetch_hackernews() -> list:
    """从 Hacker News API 获取热门内容"""
    try:
        import requests
    except ImportError:
        log("requests 未安装，跳过 HN 采集。安装: pip install requests", "WARN")
        return []

    results = []
    try:
        # 获取热门 stories
        resp = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            timeout=15
        )
        story_ids = resp.json()[:30]

        for sid in story_ids:
            try:
                story = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",
                    timeout=10
                ).json()
                if story and story.get("score", 0) >= 50:
                    results.append({
                        "title": story.get("title", ""),
                        "link": story.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                        "summary": f"HN Score: {story.get('score', 0)} | Comments: {story.get('descendants', 0)}",
                        "published": datetime.fromtimestamp(
                            story.get("time", 0), tz=timezone.utc
                        ).isoformat(),
                        "source_feed": "HackerNews",
                        "category_hint": "tech",
                    })
                time.sleep(0.1)  # 速率限制
            except Exception:
                continue

        log(f"HackerNews: 获取 {len(results)} 条高分内容")
    except Exception as e:
        log(f"HackerNews 失败: {e}", "WARN")

    return results


# ==================== 信息分类与过滤 ====================

def classify_entry(item: dict) -> str or None:
    """根据标题和摘要分类"""
    text = f"{item.get('title', '')} {item.get('summary', '')}".lower()

    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > 0:
            scores[category] = score

    if not scores:
        return None

    # 返回得分最高的分类
    return max(scores, key=scores.get)


def filter_duplicates(new_entries: list, existing_titles: set) -> list:
    """去除与已有条目标题相似的重复项"""
    filtered = []
    for entry in new_entries:
        title_hash = hashlib.md5(entry["title"].encode()).hexdigest()[:12]
        if title_hash not in existing_titles and entry["title"] not in existing_titles:
            filtered.append(entry)
            existing_titles.add(title_hash)
            existing_titles.add(entry["title"])
    return filtered


def get_existing_titles(html_content: str) -> set:
    """从已有 HTML 中提取所有标题"""
    titles = set()
    for match in re.finditer(r"title:\s*'(.+?)'", html_content):
        titles.add(match.group(1))
    return titles


# ==================== 条目生成 ====================

def build_entry(raw_item: dict, entry_id: int) -> dict:
    """将原始信息构建为标准条目格式"""
    tag = classify_entry(raw_item)
    if not tag:
        tag = raw_item.get("category_hint", "tech")

    today = datetime.now().strftime("%Y-%m-%d")
    title = raw_item.get("title", "未知标题")[:80]
    summary = raw_item.get("summary", "")

    # 清理摘要
    if isinstance(summary, str):
        # 去除 HTML 标签
        summary = re.sub(r'<[^>]+>', '', summary)
        summary = summary[:150].strip()
    else:
        summary = ""

    if not summary:
        summary = f"来自 {raw_item.get('source_feed', '公开信息')} 的最新资讯"

    # 构建详情
    detail = f"""<h3>信息来源</h3>
<ul>
<li>原始链接：<a href="{raw_item.get('link', '#')}" target="_blank">{raw_item.get('link', '无')}</a></li>
<li>采集时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} UTC</li>
<li>信息源：{raw_item.get('source_feed', '公开信息')}</li>
</ul>
<h3>内容摘要</h3>
<p>{summary}</p>
<div class="highlight-box"><strong>注意</strong>：本条为自动采集信息，仅供参考。具体操作前请自行验证信息的准确性和时效性。</div>"""

    return {
        "id": entry_id,
        "tag": tag,
        "title": title,
        "summary": summary,
        "date": today,
        "source": f"自动采集自 {raw_item.get('source_feed', '公开信息')}",
        "detail": detail,
    }


# ==================== 主流程 ====================

def main():
    """每日更新主流程"""
    log("===== InfoGap 每日更新开始 =====")
    ensure_dirs()

    # 1. 备份当前 HTML
    backup_html()

    # 2. 读取当前 HTML
    if not INDEX_FILE.exists():
        log("index.html 不存在，跳过更新", "ERROR")
        return

    html_content = INDEX_FILE.read_text(encoding="utf-8")
    entry_count = get_entry_count(html_content)
    next_id = get_next_id(html_content)
    existing_titles = get_existing_titles(html_content)

    log(f"当前条目数: {entry_count}, 下一个 ID: {next_id}")

    # 3. 采集信息
    raw_items = []

    # RSS 源
    raw_items.extend(fetch_rss_feeds())

    # Hacker News
    raw_items.extend(fetch_hackernews())

    log(f"采集到 {len(raw_items)} 条原始信息")

    # 4. 分类和去重
    classified = []
    for item in raw_items:
        tag = classify_entry(item)
        if tag:
            classified.append(item)

    log(f"分类后: {len(classified)} 条")

    # 5. 构建条目
    new_entries = []
    for item in classified:
        entry = build_entry(item, next_id)
        new_entries.append(entry)

    # 6. 去重
    new_entries = filter_duplicates(new_entries, existing_titles)
    log(f"去重后: {len(new_entries)} 条新条目")

    if not new_entries:
        log("没有新的信息差条目，跳过更新")
        return

    # 7. 限制每次最多添加 10 条（避免一次更新太多）
    new_entries = new_entries[:10]
    log(f"最终添加: {len(new_entries)} 条")

    # 8. 插入 HTML
    try:
        new_html = insert_entries(html_content, new_entries)
    except ValueError as e:
        log(f"插入失败: {e}", "ERROR")
        return

    # 9. 统计分类分布
    from collections import Counter
    tag_dist = Counter(e["tag"] for e in new_entries)
    for tag, cnt in sorted(tag_dist.items()):
        log(f"  新增 {TAG_MAP.get(tag, tag)}: {cnt} 条")

    # 10. 写入文件
    INDEX_FILE.write_text(new_html, encoding="utf-8")
    log(f"已更新 index.html，新增 {len(new_entries)} 条")

    # 11. 更新日志
    log_file = LOG_DIR / f"update_{datetime.now().strftime('%Y%m%d')}.json"
    log_file.write_text(
        json.dumps({
            "date": datetime.now().isoformat(),
            "total_before": entry_count,
            "total_after": entry_count + len(new_entries),
            "added": len(new_entries),
            "entries": [
                {"id": e["id"], "tag": e["tag"], "title": e["title"]}
                for e in new_entries
            ],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 12. Git 提交和推送
    success = git_commit_and_push()
    if success:
        log(f"===== 更新完成: 新增 {len(new_entries)} 条，总计 {entry_count + len(new_entries)} 条 =====")
    else:
        log("HTML 已更新但 Git 推送失败，请手动推送", "WARN")


# ==================== 手动添加条目 ====================

def add_manual_entry(tag: str, title: str, summary: str, detail_html: str, source: str = "综合整理自公开信息"):
    """
    手动添加一条信息差条目（用于人工审核后添加高质量内容）

    使用示例：
        python3 daily_update.py --add money "标题" "摘要" "详情HTML" "来源"
    """
    if not INDEX_FILE.exists():
        log("index.html 不存在", "ERROR")
        return

    html_content = INDEX_FILE.read_text(encoding="utf-8")
    next_id = get_next_id(html_content)
    today = datetime.now().strftime("%Y-%m-%d")

    entry = {
        "id": next_id,
        "tag": tag,
        "title": title,
        "summary": summary,
        "date": today,
        "source": source,
        "detail": detail_html,
    }

    new_html = insert_entries(html_content, [entry])
    INDEX_FILE.write_text(new_html, encoding="utf-8")
    log(f"已手动添加条目: [{tag}] {title} (id={next_id})")

    git_commit_and_push()


# ==================== 已知去重列表（历史案例库） ====================
# 维护一个已记录的案例分析列表，确保不重复添加
KNOWN_CASES_FILE = REPO_DIR / "known_cases.json"

def load_known_cases() -> set:
    """加载已记录的案例"""
    if KNOWN_CASES_FILE.exists():
        data = json.loads(KNOWN_CASES_FILE.read_text(encoding="utf-8"))
        return set(data.get("titles", []))
    return set()

def save_known_case(title: str):
    """保存新案例标题"""
    cases = load_known_cases()
    cases.add(title)
    KNOWN_CASES_FILE.write_text(
        json.dumps({"titles": list(cases), "updated": datetime.now().isoformat()},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--add":
        # 手动添加模式
        if len(sys.argv) < 6:
            print("用法: python3 daily_update.py --add <tag> <title> <summary> <detail_html> [source]")
            print(f"可用 tag: {list(TAG_MAP.keys())}")
            sys.exit(1)
        tag = sys.argv[2]
        title = sys.argv[3]
        summary = sys.argv[4]
        detail_html = sys.argv[5]
        source = sys.argv[6] if len(sys.argv) > 6 else "综合整理自公开信息"

        if tag not in TAG_MAP:
            print(f"无效 tag: {tag}，可用: {list(TAG_MAP.keys())}")
            sys.exit(1)

        add_manual_entry(tag, title, summary, detail_html, source)
    else:
        main()
