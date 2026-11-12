import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import BUILD
txt = open(os.path.join(BUILD, 'pass1.txt'), encoding='utf-8').read().split('\f')
toc = json.load(open(os.path.join(BUILD, 'structure.json')))['toc']
norm = lambda s: re.sub(r'\s+', ' ', s).strip()
lead = [i for i, p in enumerate(txt) if '.....' in p]
body_start = max(lead) + 1                       # 0-based index of first body page
page_lines = [[norm(l) for l in p.split('\n') if l.strip()] for p in txt]
res, miss = {}, []
pg, ln = body_start, 0
for e in toc:
    target = norm(e['text']); found = False
    for p in range(pg, len(page_lines)):
        lines = page_lines[p]
        for i in range(ln if p == pg else 0, len(lines)):
            for w in (1, 2, 3):
                if norm(' '.join(lines[i:i + w])) == target:
                    res[e['id']] = p - body_start + 1
                    pg, ln, found = p, i + 1, True; break
            if found: break
        if found: break
    if not found: miss.append(e['text'])
json.dump(res, open(os.path.join(BUILD, 'pages.json'), 'w'))
print('body starts at pdf page', body_start + 1, '| matched', len(res), 'of', len(toc), '| missing', miss[:10])
