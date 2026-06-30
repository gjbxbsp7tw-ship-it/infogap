"""Fetch global news from Google News RSS, translate to Chinese, save as JSON."""
import feedparser
import json
import os
import re
from datetime import datetime
from deep_translator import GoogleTranslator

COUNTRIES = {
    'US': 'https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en',
    'GB': 'https://news.google.com/rss?hl=en-GB&gl=GB&ceid=GB:en',
    'CN': 'https://news.google.com/rss?hl=zh-CN&gl=CN&ceid=CN:zh',
    'JP': 'https://news.google.com/rss?hl=ja&gl=JP&ceid=JP:ja',
    'KR': 'https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko',
    'DE': 'https://news.google.com/rss?hl=de&gl=DE&ceid=DE:de',
    'FR': 'https://news.google.com/rss?hl=fr&gl=FR&ceid=FR:fr',
    'IN': 'https://news.google.com/rss?hl=en&gl=IN&ceid=IN:en',
    'BR': 'https://news.google.com/rss?hl=pt-BR&gl=BR&ceid=BR:pt',
    'AU': 'https://news.google.com/rss?hl=en&gl=AU&ceid=AU:en',
    'CA': 'https://news.google.com/rss?hl=en&gl=CA&ceid=CA:en',
    'RU': 'https://news.google.com/rss?hl=ru&gl=RU&ceid=RU:ru',
    'IT': 'https://news.google.com/rss?hl=it&gl=IT&ceid=IT:it',
    'ES': 'https://news.google.com/rss?hl=es&gl=ES&ceid=ES:es',
    'MX': 'https://news.google.com/rss?hl=es&gl=MX&ceid=MX:es',
    'SG': 'https://news.google.com/rss?hl=en&gl=SG&ceid=SG:en',
    'AE': 'https://news.google.com/rss?hl=en&gl=AE&ceid=AE:en',
    'ZA': 'https://news.google.com/rss?hl=en&gl=ZA&ceid=ZA:en',
    'TR': 'https://news.google.com/rss?hl=tr&gl=TR&ceid=TR:tr',
}


def translate_text(text):
    """Translate text to Chinese, return original on failure."""
    if not text or not text.strip():
        return text
    try:
        result = GoogleTranslator(source='auto', target='zh-CN').translate(text)
        return result if result else text
    except Exception:
        return text


os.makedirs('news', exist_ok=True)

for code, url in COUNTRIES.items():
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:20]:
            title = entry.get('title', '')
            summary = entry.get('summary', '')
            desc_clean = re.sub(r'<[^>]+>', '', summary).strip()[:300]
            if not desc_clean:
                desc_clean = summary[:300]

            title_cn = translate_text(title)
            description_cn = translate_text(desc_clean)

            items.append({
                'title': title,
                'title_cn': title_cn,
                'link': entry.get('link', ''),
                'pubDate': entry.get('published', ''),
                'source': entry.get('source', {}).get('title', '') if hasattr(entry, 'source') else '',
                'description': desc_clean,
                'description_cn': description_cn,
            })

        data = {
            'country': code,
            'updated': datetime.utcnow().isoformat() + 'Z',
            'count': len(items),
            'items': items,
        }

        with open(f'news/{code}.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)

        print(f'{code}: {len(items)} items')
    except Exception as e:
        print(f'{code}: ERROR - {e}')

print(f'\nDone at {datetime.utcnow().isoformat()}Z')
