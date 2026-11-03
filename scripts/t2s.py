#!/usr/bin/env python3
"""Convert traditional Chinese to simplified in all JSON data files.

Usage: python3 t2s.py [--dir 唐]  (default: all dirs except 唐)
Idempotent: only rewrites files that actually change.
"""
import json, os, sys
from opencc import OpenCC

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cc = OpenCC('t2s')

SKIP_DIRS = {'.git', '名篇索引', 'scripts'}
only_dir = sys.argv[sys.argv.index('--dir') + 1] if '--dir' in sys.argv else None

def conv(obj):
    """Recursively t2s all string values. Returns (new_obj, changed)."""
    if isinstance(obj, str):
        n = cc.convert(obj)
        return n, n != obj
    if isinstance(obj, list):
        changed = False
        out = []
        for x in obj:
            nx, c = conv(x)
            out.append(nx)
            changed = changed or c
        return out, changed
    if isinstance(obj, dict):
        changed = False
        out = {}
        for k, v in obj.items():
            nv, c = conv(v)
            out[k] = nv
            changed = changed or c
        return out, changed
    return obj, False

n_files = n_changed = 0
for root, dirs, files in os.walk(OUT):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    rel = os.path.relpath(root, OUT)
    top = rel.split(os.sep)[0]
    if only_dir and top != only_dir:
        continue
    if not only_dir and top == '唐':
        continue
    for fn in files:
        if not fn.endswith('.json'):
            continue
        p = os.path.join(root, fn)
        try:
            d = json.load(open(p, encoding='utf-8'))
        except Exception as e:
            print(f'skip {p}: {e}')
            continue
        n_files += 1
        nd, changed = conv(d)
        if changed:
            json.dump(nd, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
            n_changed += 1

print(f'DONE: {n_files} files scanned, {n_changed} converted')
