#!/usr/bin/env python3
"""chinese-poetry -> chinese-classics: reorganize by dynasty/author.

Input : /tmp/chpo  (chinese-poetry repo)
Output: ~/workspace/work/classics/
Schema: see ../schema.md
"""
import json, os, re, glob
from collections import defaultdict

SRC = '/tmp/chpo'
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)

def save(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False)

def paras(e):
    for k in ('paragraphs', 'para', 'content'):
        v = e.get(k)
        if isinstance(v, list) and v and all(isinstance(x, str) for x in v):
            return v
    return []

def safe_name(s):
    return re.sub(r'[\\/:*?"<>|]', '_', (s or '').strip()) or '无名氏'

def annotations_from(e, default_source='chinese-poetry'):
    ann = []
    notes = e.get('notes')
    if notes:
        ann.append({'source': default_source, 'notes': notes if isinstance(notes, list) else [notes]})
    return ann

def write_author(dynasty_dir, dynasty_label, author, works, desc=''):
    author = (author or '').strip() or '无名氏'
    path = os.path.join(OUT, dynasty_dir, safe_name(author) + '.json')
    # merge if author already has a file (e.g. 花间集 + 南唐同作者)
    existing = None
    if os.path.exists(path):
        existing = load(path)
    if existing:
        seen = set((w.get('title'),) for w in existing['works'])
        for w in works:
            if (w.get('title'),) not in seen:
                existing['works'].append(w)
        save(path, existing)
        return len(works)
    save(path, {
        'dynasty': dynasty_label,
        'author': author,
        'author_desc': desc,
        'works': works,
    })
    return len(works)

def write_book(dynasty_dir, dynasty_label, title, author, chapters):
    path = os.path.join(OUT, dynasty_dir, safe_name(title) + '.json')
    save(path, {
        'title': title,
        'dynasty': dynasty_label,
        'author': author,
        'chapters': chapters,
    })

def book_chapters_from_dict(d):
    """Handle {title,author,paragraphs} or {title,content:[...]} shapes."""
    if paras(d):
        return [{'chapter': d.get('title', ''), 'paragraphs': paras(d), 'annotations': []}]
    chs = []
    for c in (d.get('content') or []):
        if isinstance(c, dict):
            chs.append({
                'chapter': c.get('chapter') or c.get('title') or '',
                'paragraphs': paras(c),
                'annotations': annotations_from(c),
            })
    return chs

stats = defaultdict(int)

# ---------- 全唐诗 -> 唐/作者.json ----------
tang_bios = {}
for a in load(f'{SRC}/全唐诗/authors.tang.json'):
    # entries are {desc: ...} keyed oddly; find name field
    name = a.get('name') or ''
    if not name:
        # fallback: desc starts with name like "李白：..."
        m = re.match(r'^([^：:\s]{2,5})', a.get('desc', ''))
        name = m.group(1) if m else ''
    if name:
        tang_bios[name] = a.get('desc', '')
authors = defaultdict(list)
for f in sorted(glob.glob(f'{SRC}/全唐诗/poet.tang.*.json')):
    for e in load(f):
        au = (e.get('author') or '').strip() or '无名氏'
        p = paras(e)
        if not p:
            continue
        w = {'title': e.get('title', ''), 'paragraphs': p,
             'annotations': annotations_from(e)}
        if e.get('strains'):
            w['strains'] = e['strains']
        authors[au].append(w)
for au, works in authors.items():
    write_author('唐', '唐', au, works, tang_bios.get(au, ''))
stats['唐'] = len(authors)
print(f'唐: {len(authors)} authors, {sum(len(v) for v in authors.values())} works')

# ---------- 宋词 -> 宋/作者.json ----------
def song_dynasty(desc):
    for d in ('北宋', '南宋', '辽', '金', '五代'):
        if d in (desc or ''):
            return d
    return '宋'
song_bios = {}
for a in load(f'{SRC}/宋词/author.song.json'):
    desc = a.get('description', '')
    name = ''
    m = re.match(r'^([^：:\s（(]{2,5})', desc)
    if m:
        name = m.group(1)
    if name:
        song_bios[name] = (desc, song_dynasty(desc))
authors = defaultdict(list)
for f in sorted(glob.glob(f'{SRC}/宋词/ci.song.*.json')):
    for e in load(f):
        au = (e.get('author') or '').strip() or '无名氏'
        p = paras(e)
        if not p:
            continue
        w = {'title': e.get('title', ''), 'paragraphs': p,
             'annotations': annotations_from(e)}
        for k in ('rhythmic', 'rhythm'):
            if e.get(k):
                w['rhythmic'] = e[k]
                break
        authors[au].append(w)
for au, works in authors.items():
    desc, dyn = song_bios.get(au, ('', '宋'))
    write_author('宋', dyn, au, works, desc)
stats['宋'] = len(authors)
print(f'宋: {len(authors)} authors, {sum(len(v) for v in authors.values())} works')

# ---------- 诗经 -> 先秦/诗经.json ----------
sj = load(f'{SRC}/诗经/shijing.json')
works = []
for e in sj:
    p = e.get('content') or paras(e)
    works.append({'title': e.get('title', ''), 'chapter': e.get('chapter', ''),
                  'section': e.get('section', ''), 'paragraphs': p,
                  'annotations': []})
write_book('先秦', '先秦', '诗经', '无名氏（周代采诗官采集整理）',
           [{'chapter': f"{w['chapter']}·{w['section']}" if w['section'] else w['chapter'],
             'title': w['title'], 'paragraphs': w['paragraphs'], 'annotations': []}
            for w in works])
stats['诗经'] = len(works)
print(f'诗经: {len(works)}')

# ---------- 楚辞 -> 先秦/作者.json ----------
authors = defaultdict(list)
for e in load(f'{SRC}/楚辞/chuci.json'):
    au = (e.get('author') or '').strip() or '无名氏'
    p = e.get('content') or paras(e)
    if not p:
        continue
    authors[au].append({'title': e.get('title', ''), 'section': e.get('section', ''),
                        'paragraphs': p, 'annotations': annotations_from(e)})
for au, works in authors.items():
    write_author('先秦', '战国', au, works)
stats['楚辞'] = len(authors)
print(f'楚辞: {len(authors)} authors')

# ---------- 论语/大学/中庸/孟子 -> 先秦/*.json ----------
for fname, title, author, dyn in [
    ('论语/lunyu.json', '论语', '孔子弟子及再传弟子', '春秋'),
    ('四书五经/daxue.json', '大学', '曾子（传）', '战国'),
    ('四书五经/zhongyong.json', '中庸', '子思（传）', '战国'),
    ('四书五经/mengzi.json', '孟子', '孟子及弟子', '战国'),
]:
    d = load(f'{SRC}/{fname}')
    items = d if isinstance(d, list) else [d]
    chs = []
    for e in items:
        chs.append({'chapter': e.get('chapter', ''), 'paragraphs': paras(e),
                    'annotations': annotations_from(e)})
    write_book('先秦', dyn, title, author, chs)
    stats[title] = len(chs)
    print(f'{title}: {len(chs)} chapters')

# ---------- 曹操诗集 -> 秦汉/曹操.json ----------
cc = load(f'{SRC}/曹操诗集/caocao.json')
works = [{'title': e.get('title', ''), 'paragraphs': paras(e),
          'annotations': annotations_from(e)} for e in cc if paras(e)]
write_author('秦汉', '东汉', '曹操', works)
stats['曹操'] = len(works)
print(f'曹操: {len(works)}')

# ---------- 元曲 -> 元/作者.json ----------
authors = defaultdict(list)
for e in load(f'{SRC}/元曲/yuanqu.json'):
    au = (e.get('author') or '').strip() or '无名氏'
    p = paras(e)
    if not p:
        continue
    w = {'title': e.get('title', ''), 'paragraphs': p, 'annotations': annotations_from(e)}
    authors[au].append(w)
for au, works in authors.items():
    write_author('元', '元', au, works)
stats['元曲'] = len(authors)
print(f'元曲: {len(authors)} authors, {sum(len(v) for v in authors.values())} works')

# ---------- 五代诗词 -> 五代十国/作者.json ----------
def wudai_works(files, dynasty_label):
    authors = defaultdict(list)
    for f in files:
        for e in load(f):
            au = (e.get('author') or '').strip() or '无名氏'
            p = paras(e)
            if not p:
                continue
            w = {'title': e.get('title') or e.get('rhythmic', ''), 'paragraphs': p,
                 'annotations': annotations_from(e)}
            if e.get('rhythmic'):
                w['rhythmic'] = e['rhythmic']
            authors[(au, dynasty_label)].append(w)
    return authors
authors = wudai_works([f'{SRC}/五代诗词/nantang/poetrys.json'], '南唐')
authors.update(wudai_works(sorted(glob.glob(f'{SRC}/五代诗词/huajianji/huajianji-*-juan.json')), '五代'))
merged = defaultdict(list)
for (au, dyn), works in authors.items():
    merged[au].extend([(dyn, w) for w in works])
for au, lst in merged.items():
    dyn = lst[0][0]
    write_author('五代十国', dyn, au, [w for _, w in lst])
stats['五代十国'] = len(merged)
print(f'五代十国: {len(merged)} authors')

# ---------- 纳兰性德 -> 清/纳兰性德.json ----------
nl = load(f'{SRC}/纳兰性德/纳兰性德诗集.json')
works = [{'title': e.get('title', ''), 'paragraphs': paras(e),
          'annotations': annotations_from(e)} for e in nl if paras(e)]
write_author('清', '清', '纳兰性德', works)
stats['纳兰性德'] = len(works)
print(f'纳兰性德: {len(works)}')

# ---------- 蒙学单行本 ----------
single_books = [
    ('蒙学/sanzijing-new.json', '宋', '宋', '三字经', None),
    ('蒙学/qianziwen.json', '魏晋南北朝', '南北朝', '千字文', None),
    ('蒙学/baijiaxing.json', '宋', '北宋', '百家姓', '无名氏'),
    ('蒙学/dizigui.json', '清', '清', '弟子规', None),
    ('蒙学/shenglvqimeng.json', '清', '清', '声律启蒙', None),
    ('蒙学/youxueqionglin.json', '明', '明', '幼学琼林', None),
    ('蒙学/zengguangxianwen.json', '明', '明', '增广贤文', '无名氏'),
    ('蒙学/zhuzijiaxun.json', '清', '清', '朱子家训', None),
    ('蒙学/wenzimengqiu.json', '唐', '唐', '文字蒙求', None),
]
for fname, ddir, dyn, title, force_author in single_books:
    p = f'{SRC}/{fname}'
    if not os.path.exists(p):
        print(f'skip missing {fname}'); continue
    d = load(p)
    author = force_author or d.get('author') or '无名氏'
    chs = book_chapters_from_dict(d)
    if not chs:
        print(f'empty {fname}'); continue
    write_book(ddir, dyn, title, author, chs)
    stats[title] = len(chs)
    print(f'{title}: {len(chs)} chapters')

# ---------- 古文观止 -> 清/古文观止.json ----------
gw = load(f'{SRC}/蒙学/guwenguanzhi.json')
chs = []
for vol in gw.get('content', []):
    for art in vol.get('content', []):
        chs.append({
            'chapter': f"{vol.get('title','')}·{art.get('chapter','')}",
            'source': art.get('source', ''),
            'author': art.get('author', ''),
            'paragraphs': paras(art),
            'annotations': [],
        })
write_book('清', '清', '古文观止', '吴楚材、吴调侯（选编）', chs)
stats['古文观止'] = len(chs)
print(f'古文观止: {len(chs)} articles')

# ---------- 幽梦影 -> 清/幽梦影.json ----------
ym = load(f'{SRC}/幽梦影/youmengying.json')
items = ym if isinstance(ym, list) else ym.get('content', [])
chs = []
for i, e in enumerate(items):
    text = e.get('content') if isinstance(e.get('content'), str) else ''
    if not text and not paras(e):
        continue
    chs.append({
        'chapter': f'则{i+1}',
        'paragraphs': [text] if text else paras(e),
        'annotations': [{'source': 'chinese-poetry',
                         'notes': e.get('comment', [])}] if e.get('comment') else [],
    })
write_book('清', '清', '幽梦影', '张潮', chs)
stats['幽梦影'] = len(chs)
print(f'幽梦影: {len(chs)}')

# ---------- 名篇索引 ----------
os.makedirs(f'{OUT}/名篇索引', exist_ok=True)
t300 = load(f'{SRC}/蒙学/tangshisanbaishou.json')
c300 = t300.get('content', []) if isinstance(t300, dict) else t300
idx = []
def flatten_t300(items):
    for e in items:
        if isinstance(e, dict) and isinstance(e.get('content'), list) and e.get('content') \
                and isinstance(e['content'][0], dict):
            # type group, e.g. {"type": "五言絕句", "content": [...]}
            flatten_t300(e['content'])
        elif isinstance(e, dict):
            idx.append({'title': e.get('chapter') or e.get('title', ''),
                        'author': re.sub(r'[（）()]', '', e.get('author', '') or '')})
flatten_t300(c300)
save(f'{OUT}/名篇索引/唐诗三百首.json', idx)
print(f'名篇索引/唐诗三百首: {len(idx)}')

print('DONE', dict(stats))
