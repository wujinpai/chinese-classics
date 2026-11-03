#!/usr/bin/env python3
"""Bulk CSV -> chinese-classics (v2).

Input : /tmp/csv_src/*.csv  (MIT, )
Output: merges into ~/workspace/work/classics/<朝代>/<作者>.json
Dedups against v1 by (title, author, first-20-chars).
Excludes modern files (copyright): 当代/民国末当代初/近现代末当代初/近现代/清末近现代初/清末民国初.
"""
import csv, json, os, re
from collections import defaultdict

SRC = '/tmp/csv_src'
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# file -> (dir, ) ; dynasty label taken from CSV 朝代 field
FILEMAP = {
    '先秦.csv': '先秦',
    '秦.csv': '秦汉',
    '汉.csv': '秦汉',
    '魏晋.csv': '魏晋南北朝',
    '魏晋末南北朝初.csv': '魏晋南北朝',
    '南北朝.csv': '魏晋南北朝',
    '隋.csv': '隋',
    '隋末唐初.csv': '隋',
    '唐.csv': '唐',
    '唐末宋初.csv': '五代十国',
    '宋_1.csv': '宋', '宋_2.csv': '宋', '宋_3.csv': '宋', '宋_4.csv': '宋',
    '宋末元初.csv': '宋',
    '宋末金初.csv': '辽金',
    '辽.csv': '辽金',
    '金.csv': '辽金',
    '金末元初.csv': '辽金',
    '元.csv': '元',
    '元末明初.csv': '元',
    '明_1.csv': '明', '明_2.csv': '明', '明_3.csv': '明', '明_4.csv': '明',
    '明末清初.csv': '明',
    '清_1.csv': '清', '清_2.csv': '清',
}
EXCLUDE = {'当代.csv', '民国末当代初.csv', '近现代末当代初.csv',
           '近现代.csv', '清末近现代初.csv', '清末民国初.csv'}
# anthology attributions, not real authors; content already in v1 books
SKIP_AUTHORS = {'诗经'}

def norm(s):
    return re.sub(r'\s+', '', s or '')

PUNCT = '，。！？；：、…—·「」『』（）()《》〈〉【】\"\'‘’“”　,.!?;:'

def text_key(paragraphs):
    t = re.sub(r'\s+', '', ''.join(paragraphs or ''))
    t = t.translate(str.maketrans('', '', PUNCT))
    return t[:15]

def split_paras(text):
    text = (text or '').strip()
    if not text:
        return []
    parts = re.split(r'(?<=[。！？；])', text)
    out = [p.strip() for p in parts if p.strip()]
    return out or [text]

def safe_name(s):
    return re.sub(r'[\\/:*?"<>|]', '_', (s or '').strip()) or '无名氏'

def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)

def save(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False)

# ---------- build v1 index for dedup ----------
print('indexing v1...', flush=True)
v1 = set()
for root, dirs, files in os.walk(OUT):
    if '名篇索引' in root or 'scripts' in root:
        continue
    for fn in files:
        if not fn.endswith('.json'):
            continue
        try:
            d = load(os.path.join(root, fn))
        except Exception:
            continue
        works = d.get('works', [])
        au = d.get('author', '')
        for w in works:
            v1.add((norm(w.get('title', '')), norm(au),
                    text_key(w.get('paragraphs'))))
        for c in d.get('chapters', []):
            v1.add((norm(c.get('chapter', '') or d.get('title', '')),
                    norm(d.get('author', '')),
                    text_key(c.get('paragraphs'))))
print(f'v1 index: {len(v1)}', flush=True)

# ---------- convert ----------
buckets = defaultdict(list)  # (dir, author) -> [works]
seen = set()
stats = defaultdict(lambda: [0, 0])  # file -> [total, added]
for fname, ddir in FILEMAP.items():
    p = os.path.join(SRC, fname)
    if not os.path.exists(p):
        print(f'missing {fname}'); continue
    with open(p, encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            stats[fname][0] += 1
            title = (row.get('题目') or '').strip() or '无题'
            author = (row.get('author') or row.get('作者') or '').strip() or '无名氏'
            if author in SKIP_AUTHORS:
                continue
            dyn = (row.get('朝代') or '').strip()
            ps = split_paras(row.get('内容'))
            if not ps:
                continue
            key = (norm(title), norm(author), text_key(ps))
            if key in v1 or key in seen:
                continue
            seen.add(key)
            buckets[(ddir, dyn, author)].append(
                {'title': title, 'paragraphs': ps, 'annotations': []})
            stats[fname][1] += 1
    print(f'{fname}: total {stats[fname][0]}, new {stats[fname][1]}', flush=True)

# ---------- write / merge ----------
n_files = 0
for (ddir, dyn, author), works in buckets.items():
    path = os.path.join(OUT, ddir, safe_name(author) + '.json')
    if os.path.exists(path):
        d = load(path)
        if 'works' not in d:
            # book file collision; disambiguate
            path = os.path.join(OUT, ddir, safe_name(author) + '.作品.json')
            d = load(path) if os.path.exists(path) else None
        if d is None:
            d = {'dynasty': dyn, 'author': author, 'author_desc': '', 'works': []}
        have = set((norm(w.get('title', '')), text_key(w.get('paragraphs')))
                   for w in d['works'])
        for w in works:
            k = (norm(w['title']), text_key(w['paragraphs']))
            if k not in have:
                d['works'].append(w)
                have.add(k)
        save(path, d)
    else:
        save(path, {'dynasty': dyn, 'author': author, 'author_desc': '',
                    'works': works})
    n_files += 1

new_total = sum(v[1] for v in stats.values())
print(f'DONE: {new_total} new works into {n_files} author files')
