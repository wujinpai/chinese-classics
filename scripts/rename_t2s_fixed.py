#!/usr/bin/env python3
"""FIXED filename t2s rename: merges trad/simp duplicate author files.
Key fix: when deduping, PRESERVES annotations (keeps work with annotations,
or merges annotation lists). Verifies work counts.
Usage: python3 scripts/rename_t2s_fixed.py --dir 唐
"""
import json, os, re, sys
from collections import defaultdict
from opencc import OpenCC
cc = OpenCC('t2s')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def dedup_key(w):
    t = (w.get('title') or '')
    paras = w.get('paragraphs', [])
    body = re.sub(r'[，。！？；：、\s「」『』（）()　・…—]', '', ''.join(paras))[:15]
    return (t, body)

def merge_annotations(w1, w2):
    """合并两条重复作品的 annotations，去重"""
    a1 = w1.get('annotations', []) or []
    a2 = w2.get('annotations', []) or []
    # 简单去重：按 notes+translation 拼接去重
    seen = set()
    out = []
    for a in a1 + a2:
        k = (tuple(a.get('notes', []) or []), a.get('translation',''), a.get('appreciation',''))
        if k not in seen:
            seen.add(k)
            out.append(a)
    return out

def main():
    ddir = sys.argv[sys.argv.index('--dir') + 1]
    groups = defaultdict(list)
    for fn in os.listdir(os.path.join(BASE, ddir)):
        if not fn.endswith('.json'): continue
        groups[cc.convert(fn)].append(fn)

    n_rename = n_merge = 0
    works_before = works_after = 0
    ann_before = ann_after = 0

    for new_fn, olds in sorted(groups.items()):
        # 统计 before
        for fn in olds:
            d = json.load(open(os.path.join(BASE, ddir, fn), encoding='utf-8'))
            works_before += len(d.get('works', []))
            ann_before += sum(1 for w in d.get('works', []) if w.get('annotations'))

        if len(olds) == 1 and olds[0] == new_fn:
            # 无需改动
            d = json.load(open(os.path.join(BASE, ddir, olds[0]), encoding='utf-8'))
            works_after += len(d.get('works', []))
            ann_after += sum(1 for w in d.get('works', []) if w.get('annotations'))
            continue
        if len(olds) == 1:
            os.rename(os.path.join(BASE, ddir, olds[0]),
                      os.path.join(BASE, ddir, new_fn))
            n_rename += 1
            d = json.load(open(os.path.join(BASE, ddir, new_fn), encoding='utf-8'))
            works_after += len(d.get('works', []))
            ann_after += sum(1 for w in d.get('works', []) if w.get('annotations'))
        else:
            # 合并：保留 annotations
            merged = None
            seen = {}  # key -> work (保留 annotations 最多的版本)
            for fn in sorted(olds):
                d = json.load(open(os.path.join(BASE, ddir, fn), encoding='utf-8'))
                if merged is None:
                    merged = {k: v for k, v in d.items() if k != 'works'}
                    merged['works'] = []
                    merged['author'] = cc.convert(d.get('author', ''))
                for w in d.get('works', []):
                    k = dedup_key(w)
                    if k not in seen:
                        seen[k] = w
                    else:
                        # 重复：合并 annotations，保留有释义的版本
                        old = seen[k]
                        merged_ann = merge_annotations(old, w)
                        # 选择 annotations 更多的版本为基础
                        base = old if len(old.get('annotations', []) or []) >= len(w.get('annotations', []) or []) else w
                        base['annotations'] = merged_ann
                        seen[k] = base
            merged['works'] = list(seen.values())
            # author_desc 取最长的
            best_desc = merged.get('author_desc', '')
            for fn in olds:
                d = json.load(open(os.path.join(BASE, ddir, fn), encoding='utf-8'))
                if len(d.get('author_desc', '') or '') > len(best_desc or ''):
                    best_desc = d['author_desc']
            merged['author_desc'] = best_desc
            json.dump(merged, open(os.path.join(BASE, ddir, new_fn), 'w', encoding='utf-8'),
                      ensure_ascii=False)
            for fn in olds:
                if fn != new_fn:
                    os.remove(os.path.join(BASE, ddir, fn))
            n_merge += 1
            works_after += len(merged['works'])
            ann_after += sum(1 for w in merged['works'] if w.get('annotations'))

    print(f'改名: {n_rename} | 合并: {n_merge}')
    print(f'作品: {works_before} -> {works_after} (差值应为去重数)')
    print(f'释义: {ann_before} -> {ann_after} (不应减少)')

if __name__ == '__main__':
    main()
