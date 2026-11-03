#!/usr/bin/env python3
"""按体裁拆分：每个朝代目录拆为 <朝代>诗/ <朝代>词/（元另有 元曲/）。
分类规则（按优先级）：
  1. works 有 rhythmic 字段 -> 词（v1 宋词/花间集/南唐词）
  2. 元/ 且标题在 v1 元曲标题集合中 -> 曲（git 52b0ed4 提取，t2s 归一化比对）
  3. 标题命中词牌名（词牌名+分隔符+副题，或标题即词牌名），排除乐府旧题 -> 词
     （仅唐/五代/宋/辽金/元/明/清；词起于唐，先秦至隋不做词牌匹配）
  4. 其余 -> 诗
另：词的空标题用 rhythmic（词牌名）回填；典籍（chapters 结构）归入 X诗/。
用法：python3 scripts/split_shici.py [--dir 唐]  # 不带参数处理除唐之外的全部
"""
import json, os, re, sys, shutil, subprocess

try:
    from opencc import OpenCC
    t2s = OpenCC('t2s').convert
except ImportError:
    t2s = lambda s: s  # noqa

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CIPAI = set(json.load(open(os.path.join(BASE, 'scripts', 'cipai.json'), encoding='utf-8')))

# 乐府旧题：是诗不是词，排除
YUEFU_EXCLUDE = {'关山月','出塞','从军行','江南','敕勒歌','木兰辞','木兰诗','孔雀东南飞',
    '将进酒','行路难','蜀道难','子夜歌','读曲歌','西洲曲','杨柳枝','竹枝词','江南曲',
    '出塞曲','塞上曲','塞下曲','前出塞','后出塞','江南春','长干行','长干曲','襄阳歌',
    '襄阳曲','庐山谣','远别离','公无渡河','战城南','东门行','妇病行','孤儿行','陌上桑',
    '羽林郎','秋胡行','董逃行','塘上行','乌夜啼','白头吟','上邪','江南可采莲','采莲曲',
    '采菱曲','杨叛儿','西乌夜飞','黄鹄曲','雁门太守行','巫山高','芳树','有所思','上留田',
    '白头吟','箜篌引','公无渡河','横吹曲','横吹曲辞','鼓吹曲','鼓吹曲辞'}

# 词牌名只在词体裁存在的朝代做匹配
CI_DYNASTIES = {'唐','五代十国','宋','辽金','元','明','清'}

# 朝代目录 -> 拆分后的目录名前缀
DIRMAP = {
    '宋': '宋', '五代十国': '五代', '元': '元', '明': '明', '清': '清',
    '辽金': '辽金', '隋': '隋', '先秦': '先秦', '秦汉': '秦汉',
    '魏晋南北朝': '魏晋南北朝', '唐': '唐',
}

def norm_title(t):
    return t2s(t or '').strip()

def load_yuanqu_v1():
    """从 git 提取 v1 元曲标题集合：{作者文件名: set(归一化标题)}"""
    import tarfile, io
    out = {}
    tmp = '/tmp/yuanqu_v1/元'
    if not os.path.exists(tmp) or not os.listdir(tmp):
        os.makedirs('/tmp/yuanqu_v1', exist_ok=True)
        p = subprocess.run(['git', 'archive', '52b0ed4', '元/'], cwd=BASE,
                           stdout=subprocess.PIPE, check=True)
        tarfile.open(fileobj=io.BytesIO(p.stdout)).extractall('/tmp/yuanqu_v1')
    for fn in os.listdir(tmp):
        if not fn.endswith('.json'): continue
        try:
            d = json.load(open(os.path.join(tmp, fn), encoding='utf-8'))
        except Exception:
            continue
        out[fn] = {norm_title(w.get('title','')) for w in d.get('works', [])}
    return out

def is_ci_title(title):
    if not title: return False
    head = re.split('[·・/／ 　]', title, maxsplit=1)[0].strip('：:')
    return head in CIPAI and head not in YUEFU_EXCLUDE

def classify(ddir, fn, work, yuanqu_v1):
    """返回 '诗' / '词' / '曲'"""
    if work.get('rhythmic'):
        return '词'
    title = work.get('title','') or ''
    if ddir == '元' and fn in yuanqu_v1 and norm_title(title) in yuanqu_v1[fn]:
        return '曲'
    if ddir in CI_DYNASTIES and is_ci_title(title):
        return '词'
    return '诗'

def split_dynasty(ddir, yuanqu_v1):
    prefix = DIRMAP[ddir]
    buckets = {}  # (genre, fn) -> works/chapters
    stats = {'诗':0,'词':0,'曲':0,'典籍':0}
    for fn in sorted(os.listdir(ddir)):
        if not fn.endswith('.json'): continue
        path = os.path.join(BASE, ddir, fn)
        try:
            d = json.load(open(path, encoding='utf-8'))
        except Exception as e:
            print(f'  跳过 {path}: {e}'); continue
        # 典籍（chapters 结构）-> 诗
        if d.get('chapters') and not d.get('works'):
            key = ('诗', fn)
            buckets.setdefault(key, {'meta': d, 'chapters': []})
            buckets[key]['chapters'].extend(d['chapters'])
            stats['典籍'] += len(d['chapters'])
            continue
        by_genre = {'诗': [], '词': [], '曲': []}
        for w in d.get('works', []):
            g = classify(ddir, fn, w, yuanqu_v1)
            # 词空标题用词牌名回填
            if g == '词' and not (w.get('title') or '').strip() and w.get('rhythmic'):
                w['title'] = w['rhythmic']
            by_genre[g].append(w)
            stats[g] += 1
        for g, works in by_genre.items():
            if works:
                key = (g, fn)
                b = buckets.setdefault(key, {'meta': d, 'works': []})
                b['works'].extend(works)
    # 写出
    for (g, fn), b in buckets.items():
        outdir = os.path.join(BASE, f'{prefix}{g}')
        os.makedirs(outdir, exist_ok=True)
        meta = {k: v for k, v in b['meta'].items() if k not in ('works','chapters')}
        if 'works' in b: meta['works'] = b['works']
        if 'chapters' in b: meta['chapters'] = b['chapters']
        json.dump(meta, open(os.path.join(outdir, fn), 'w', encoding='utf-8'),
                  ensure_ascii=False)
    # 删除原目录
    shutil.rmtree(os.path.join(BASE, ddir))
    return stats

def main():
    only = None
    if '--dir' in sys.argv:
        only = sys.argv[sys.argv.index('--dir')+1]
    yuanqu_v1 = load_yuanqu_v1()
    print(f'v1 元曲标题集合：{len(yuanqu_v1)} 家')
    targets = [only] if only else [d for d in DIRMAP if d != '唐']
    for ddir in targets:
        if not os.path.exists(os.path.join(BASE, ddir)):
            print(f'{ddir}/ 不存在，跳过'); continue
        stats = split_dynasty(ddir, yuanqu_v1)
        print(f'{ddir}: 诗{stats["诗"]} 词{stats["词"]} 曲{stats["曲"]} 典籍章{stats["典籍"]}')

if __name__ == '__main__':
    main()
