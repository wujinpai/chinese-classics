#!/usr/bin/env python3
"""
抓取古诗文网(www.gushiwen.cn)注释/译文/赏析,写入 <朝代>/<作者>.json 的 annotations.

用法:
  python3 fetch_annotations.py --limit 10      # 只跑前10首(样本)
  python3 fetch_annotations.py                 # 全量320首
  python3 fetch_annotations.py --resume        # 从checkpoint继续

要点:
  - 桌面 Chrome UA;每次请求间隔>=2秒;失败重试2次
  - checkpoint: scripts/.fetch_ckpt.json 记录已完成(index序号)
  - 只改 annotations 字段,不碰正文
  - 标题匹配:精确 -> 后缀归一(其一->一) -> 正文首句校验
"""
import json, os, re, sys, time, urllib.request, urllib.parse, socket
from opencc import OpenCC
socket.setdefaulttimeout(25)  # 硬超时:DNS/连接/读取任一环节卡住都不超过25秒

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX_PATH = os.path.join(BASE, '名篇索引', '唐诗三百首.json')
CKPT_PATH = os.path.join(BASE, 'scripts', '.fetch_ckpt.json')
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
      'Connection': 'close', 'Accept-Encoding': 'identity'}
SITE = 'https://www.gushiwen.cn'
cc = OpenCC('t2s')
CN_NUM = {'一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
          '六': '6', '七': '7', '八': '8', '九': '9', '十': '10'}
# 常见异体字归一
VARIANT = str.maketrans({'脁': '朓', '濬': '浚', '谿': '溪', '遊': '游',
                         '汎': '泛', '劒': '剑', '嶽': '岳', '彙': '汇',
                         '裏': '里', '牀': '床', '筝': '箏'})
# 特殊:索引标题 -> 本地目标篇目(抓组诗页,写到指定单篇)
# 王維《雜詩》(君自故乡来) = 本地 雜詩三首 二,古诗文网只有组诗《杂诗三首》页
OVERRIDES = {('王維', '雜詩'): ('雜詩三首', '雜詩三首 二')}


def t2s(s):
    return cc.convert(s)


def norm_text(s):
    """正文归一:去标点空白,用于比对"""
    s = t2s(s)
    s = re.sub(r'[，。？！；：「」『』（）()、—…·\s]', '', s)
    return s


def fetch(url, retries=2):
    """用curl抓取(urllib在此网络下频繁IncompleteRead,curl稳定)"""
    import subprocess
    last = None
    for i in range(retries + 1):
        try:
            p = subprocess.run(
                ['curl', '-s', '--max-time', '40', '-A', UA['User-Agent'],
                 '--compressed', url],
                capture_output=True, timeout=50)
            html = p.stdout.decode('utf-8', errors='replace')
            if len(html) < 5000:  # 被拦空回
                raise ValueError(f'empty/blocked response({len(html)}b)')
            time.sleep(2.2)
            return html
        except Exception as e:
            last = e
            time.sleep(3 * (i + 1))
    raise last


def norm_title(t):
    """标题归一:简体;其一->1;去数字量词"""
    t = t2s(t).translate(VARIANT)
    t = re.sub(r'·其([一二三四五六七八九十]+)$',
               lambda m: '·' + ''.join(CN_NUM.get(c, c) for c in m.group(1)), t)
    return t


def title_key(t):
    """去后缀的标题主干,用于模糊匹配"""
    t = norm_title(t)
    t = re.sub(r'[二三四五六七八九]首', '', t)   # 月下独酌四首 -> 月下独酌
    t = re.sub(r'·\d+$', '', t)                  # 清平调·1 -> 清平调
    t = re.sub(r'\s+\d+$', '', t)                # 贈別二首 1 -> 贈別二首
    t = re.sub(r'[一二三四五六七八九十]+$', '', t).strip()
    t = re.sub(r'·[^·]+$', '', t)                # 清平调·云想衣裳花想容 -> 清平调(首句后缀)
    return t


LIST_CACHE = os.path.join(BASE, 'scripts', '.list_cache.json')


def discover_author(author_trad, max_pages=8):
    """作者诗文列表 {归一标题: (原标题, url)},按热度排序页(站内用简体作者名检索)"""
    cache = {}
    if os.path.exists(LIST_CACHE):
        try:
            cache = json.load(open(LIST_CACHE, encoding='utf-8'))
        except Exception:
            cache = {}
    if author_trad in cache:
        print(f'  列表缓存命中 {len(cache[author_trad])} 篇')
        return {k: tuple(v) for k, v in cache[author_trad].items()}
    out = {}
    author_simp = t2s(author_trad)
    for pg in range(1, max_pages + 1):
        url = (f'{SITE}/shiwens/default.aspx?page={pg}&tstr=&astr='
               f'{urllib.parse.quote(author_simp)}&cstr=&xstr=')
        try:
            html = fetch(url)
        except Exception as e:
            print(f'  [warn] 作者列表页失败 {author_trad} p{pg}: {e}')
            break
        for m in re.finditer(r'<a[^>]*href="(/shiwenv_[a-z0-9]+\.aspx)"[^>]*>(.*?)</a>', html, re.S):
            u, t = m.groups()
            t = re.sub(r'<[^>]+>', '', t).strip()
            if t and len(t) < 40 and norm_title(t) not in out:
                out[norm_title(t)] = (t, SITE + u)
        if '下一页' not in html:
            break
    cache[author_trad] = {k: list(v) for k, v in out.items()}
    json.dump(cache, open(LIST_CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
    return out


def find_urls(index_title_trad, listing):
    """在作者列表中找候选URL列表(按优先级排序,调用方逐个试内容匹配).

    精确 -> 编号一致 -> 编号页(按编号排序,内容校验区分) -> 组诗页
    """
    nt = norm_title(index_title_trad)
    if nt in listing:
        return [(listing[nt][1], 'exact')]
    key = title_key(index_title_trad)
    if not key:
        return []
    m = re.search(r'·(\d+)$', nt)
    num = m.group(1) if m else None
    numbered, groups = [], []
    for lt, (raw, url) in listing.items():
        if title_key(lt) != key:
            continue
        lm = re.search(r'·(\d+)$', lt)
        lnum = lm.group(1) if lm else None
        if num is not None and num == lnum:
            return [(url, 'fuzzy-num')]
        (numbered if lnum else groups).append((lnum or '9', url))
    numbered.sort()
    out = [(u, 'fuzzy-cand') for _, u in numbered]
    out += [(u, 'fuzzy-base') for _, u in groups]
    return out


def find_url(index_title_trad, listing):
    """兼容老调用:取第一个候选"""
    cands = find_urls(index_title_trad, listing)
    return cands[0] if cands else (None, None)


def parse_page(html, url):
    """解析诗文页:正文/注释/译文/赏析(兼容A/B两种布局)"""
    res = {'url': url, 'poem': [], 'notes': [], 'translation': '', 'appreciation': ''}
    # 正文: <div class="contson" [id=...]>...</div>
    m = re.search(r'<div class="contson"[^>]*>(.*?)</div>', html, re.S)
    if m:
        txt = re.sub(r'<[^>]+>', '\n', m.group(1))
        res['poem'] = [l.strip() for l in txt.split('\n') if l.strip()]
    # 注释/译文/赏析: 全页找 <p><strong>X</strong><br/>... 或 <p><strong>X<br/></strong>...
    for pm in re.finditer(
            r'<p[^>]*>\s*<strong>(注释|译文|赏析|译文及注释)(?:<br\s*/?>)?\s*</strong>\s*(?:<br\s*/?>\s*)?(.*?)</p>',
            html, re.S):
        head, rest = pm.group(1), pm.group(2)
        lines = [re.sub(r'<[^>]+>', '', x).strip()
                 for x in re.split(r'<br\s*/?>', rest)]
        lines = [l for l in lines if l]
        if not lines:
            continue
        if head.startswith('注释') or head == '译文及注释':
            # "译文及注释"通常只有译文,按行数>3且无冒号判为译文
            if head == '译文及注释' and not any('：' in l or ':' in l for l in lines[:3]):
                if not res['translation']:
                    res['translation'] = '\n'.join(lines)
            else:
                res['notes'] = lines
        elif head.startswith('译文'):
            if not res['translation']:
                res['translation'] = '\n'.join(lines)
        elif head.startswith('赏析'):
            if not res['appreciation']:
                res['appreciation'] = '\n'.join(lines)
    return res if (res['poem'] or res['notes'] or res['translation']) else None


def match_local(data, index_title, poem_lines, force_title=None):
    """本地作品匹配(内容强制校验:data为已加载的作者文件dict)

    返回 ([命中的作品], 方式). 规则:古诗文页正文是基准,本地作品首句
    必须出现在页正文内才算命中. 同诗异名variant(内容相同)全部返回,
    都会写注释;命中不了返回空列表,绝不写错篇.
    force_title: 指定本地目标篇目(组诗页->单篇的特殊情况).
    """
    works = data['works']
    page_text = norm_text(''.join(poem_lines)) if poem_lines else ''

    def content_ok(w):
        """同篇判定:本地首句与页正文有>=5字公共子串(兼容版本异文,拦截错篇)"""
        if not page_text or not w.get('paragraphs'):
            return False
        first = norm_text(w['paragraphs'][0])
        if not first or len(first) < 5:
            return False
        for i in range(len(first) - 4):
            if first[i:i + 5] in page_text:
                return True
        return False

    def cand_keys(t):
        t1 = t.replace('·其一', ' 一').replace('·其二', ' 二').replace('·其三', ' 三') \
              .replace('·其四', ' 四').replace('·其五', ' 五')
        t2 = re.sub(r'·其([一二三四五六七八九十])$',
                    lambda m: ' ' + m.group(1), t)
        return {t, t1, t2}

    # 0. 强制指定篇目(组诗页特殊情况)
    if force_title:
        cands = [w for w in works if w['title'] == force_title]
        if len(cands) == 1 and content_ok(cands[0]):
            return cands, 'override+content'
        return [], 'override-miss'
    # 1. 精确标题
    exacts = [w for w in works if w['title'] == index_title]
    if exacts:
        hit = [w for w in exacts if content_ok(w)]
        if hit:
            return hit, 'exact+content'
        return [], 'exact-content-mismatch'
    # 2. 后缀归一
    keys = cand_keys(index_title)
    hit = [w for w in works if w['title'] in keys and content_ok(w)]
    if hit:
        return hit, 'suffix+content'
    # 3. 标题主干+内容(主干含輞川集/乐府前缀等时用包含匹配)
    key = title_key(index_title)
    hit = [w for w in works
           if (key and (key in title_key(w['title']) or title_key(w['title']) in key))
           and content_ok(w)]
    if hit:
        return hit, 'content+title'
    return [], 'miss'


def main():
    limit = None
    resume = '--resume' in sys.argv
    if '--limit' in sys.argv:
        i = sys.argv.index('--limit')
        limit = int(sys.argv[i + 1])

    idx = json.load(open(IDX_PATH, encoding='utf-8'))
    ckpt = set()
    if resume and os.path.exists(CKPT_PATH):
        ckpt = set(json.load(open(CKPT_PATH, encoding='utf-8')))
    print(f'index {len(idx)} 首, checkpoint 已有 {len(ckpt)} 首, limit={limit}')

    # 按作者分组,复用discover
    from collections import defaultdict
    by_author = defaultdict(list)
    for i, e in enumerate(idx):
        by_author[e['author']].append((i, e))

    done = 0
    stats = {'ok': 0, 'miss_url': 0, 'miss_local': 0, 'skip': 0}
    for author, items in by_author.items():
        if limit and done >= limit:
            break
        targets = [(i, e) for i, e in items if i not in ckpt]
        if not targets:
            continue
        print(f'== {author} ({len(targets)}首待抓) ==')
        listing = discover_author(author)
        print(f'  列表得 {len(listing)} 篇')
        afile = os.path.join(BASE, '唐', author + '.json')
        if not os.path.exists(afile):
            print(f'  [warn] 无作者文件 {afile}')
            stats['skip'] += len(targets)
            continue
        data = json.load(open(afile, encoding='utf-8'))
        dirty = False
        for i, e in targets:
            if limit and done >= limit:
                break
            title = e['title']
            ov = OVERRIDES.get((author, title))
            search_title = ov[0] if ov else title
            cands = find_urls(search_title, listing)
            if not cands:
                print(f'  [miss-url] {title}')
                stats['miss_url'] += 1
                continue
            ws, mhow, url, how, parsed = [], None, None, None, None
            for curl, chow in cands:
                try:
                    html = fetch(curl)
                except Exception as ex:
                    print(f'  [fetch-fail] {title}: {ex}')
                    continue
                parsed = parse_page(html, curl)
                if not parsed or (not parsed['notes'] and not parsed['translation']):
                    print(f'  [parse-empty] {title} {curl}')
                    continue
                ws, mhow = match_local(data, title, parsed['poem'],
                                       force_title=ov[1] if ov else None)
                if ws:
                    url, how = curl, chow
                    break
                print(f'  [miss-local:{mhow}] {title} {curl}')
            if not ws:
                stats['miss_local'] += 1
                continue
            # 只写annotations(干净内容字段,无source/url),释义文本繁转简(不碰正文与标题)
            wrote = 0
            for w in ws:
                if w.get('annotations'):
                    print(f'  [exists] {title} -> {w["title"]}')
                    continue
                ann = {}
                if parsed['notes']:
                    ann['notes'] = [t2s(l) for l in parsed['notes']]
                if parsed['translation']:
                    ann['translation'] = t2s(parsed['translation'])
                if parsed['appreciation']:
                    ann['appreciation'] = t2s(parsed['appreciation'])
                w.setdefault('annotations', []).append(ann)
                dirty = True
                wrote += 1
            if wrote:
                print(f'  [ok:{how}/{mhow}] {title} -> {wrote}篇 '
                      f'(注{len(parsed["notes"])}条/译{"有" if parsed["translation"] else "无"}/赏{"有" if parsed["appreciation"] else "无"})')
                stats['ok'] += 1
            ckpt.add(i)
            done += 1
            json.dump(sorted(ckpt), open(CKPT_PATH, 'w'))
        if dirty:
            json.dump(data, open(afile, 'w', encoding='utf-8'), ensure_ascii=False)
            print(f'  已写回 {afile}')
    print('stats:', stats)


if __name__ == '__main__':
    main()
