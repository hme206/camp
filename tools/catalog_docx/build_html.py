#!/usr/bin/env python3
"""Merge the pages listed in sidetoc.html into one structured HTML file for Pandoc."""
import json, os, re, sys
from bs4 import BeautifulSoup, Tag, NavigableString

from config import SRC, BUILD as OUT, SITE, TOC_FILE, find_font

def soup_of(path):
    return BeautifulSoup(open(path, encoding='utf-8', errors='replace').read(), 'html.parser')

def txt(el):
    return re.sub(r'\s+', ' ', el.get_text(' ', strip=True)).strip()

def clean_label(s):
    s = re.sub(r'\s+', ' ', s).strip()
    return re.sub(r'^[a-z]\.\s+', '', s)

# ------------------------------------------------------------------ parse TOC
toc = soup_of(f'{SRC}/{TOC_FILE}')
chapters = []
for li in toc.select('ul.toc-list > li.toc-item'):
    a = li.select_one('.toc-row a.toc-link')
    href = a.get('href', '').strip()
    ch = dict(label=txt(a), file=href, subs=[], tree=None)
    sub_ul = li.select_one('ul.toc-sub')
    if sub_ul:
        for sli in sub_ul.find_all('li', recursive=False):
            tree = sli.select_one('.toc-tree')
            sa = sli.find('a')
            sub = dict(label=txt(sa), file=sa['href'].split('#')[0], pathways=None)
            if tree:
                pathways = []
                cur = None
                for child in tree.find_all(['p', 'ul'], recursive=False):
                    if 'toc-pathway-label' in (child.get('class') or []):
                        cur = dict(label=txt(child), entries=[])
                        pathways.append(cur)
                    elif cur is not None:
                        for pli in child.find_all('li', recursive=False):
                            pa = pli.find('a')
                            st = pa.find('span', class_='toc-status')
                            status = txt(st) if st else ''
                            if st: st.extract()
                            h = pa['href']
                            cur['entries'].append(dict(label=clean_label(txt(pa)),
                                                       file=h.split('#')[0],
                                                       frag=h.split('#')[1] if '#' in h else '',
                                                       status=status))
                sub['pathways'] = pathways
            ch['subs'].append(sub)
    chapters.append(ch)

# Navigation headers that are not catalog chapters (e.g. "Catalog Updates") are left out of the Word document.
# Override with the CATALOG_SKIP_CHAPTERS environment variable (names separated by |).
SKIP = {s.strip().lower() for s in os.environ.get('CATALOG_SKIP_CHAPTERS', 'Catalog Updates').split('|') if s.strip()}
skipped_chapters = [c['label'] for c in chapters if not c['file'] or c['label'].strip().lower() in SKIP]
chapters = [c for c in chapters if c['file'] and c['label'].strip().lower() not in SKIP]

# Every remaining page must exist; otherwise stop with a plain message naming the file(s).
_needed = []
for _c in chapters:
    _needed.append(_c['file'])
    for _s in _c['subs']:
        _needed.append(_s['file'])
        for _pw in (_s['pathways'] or []):
            _needed.extend(e['file'] for e in _pw['entries'])
_missing = sorted({f for f in _needed if f and not os.path.exists(os.path.join(SRC, f))})
if _missing:
    raise SystemExit('The table of contents (' + TOC_FILE + ') links to page(s) that are not in the repository: '
                     + ', '.join(_missing) + '\nUpload the missing page(s), or remove the link from the table of contents.')

# ------------------------------------------------------------------ helpers
def san(s):
    return re.sub(r'[^A-Za-z0-9_]', '_', s)

anchors = {}          # (file, frag) -> bookmark id
toc_entries = []      # in document order: dict(level,text,id)
included = []         # ordered list of included files
empty_pages = []

def stem(f):
    return san(os.path.splitext(f)[0])

out = BeautifulSoup('<html><head><meta charset="utf-8"><title>Catalog</title></head><body></body></html>', 'html.parser')
body = out.body

def new(tag, text=None, **attrs):
    t = out.new_tag(tag)
    for k, v in attrs.items():
        t[k.replace('_', '-') if k == 'custom_style' else k] = v
    if text is not None:
        t.string = text
    return t

def heading(level, text, hid, toc_level=None):
    h = new(f'h{level}', text, id=hid)
    if toc_level:
        toc_entries.append(dict(level=toc_level, text=text, id=hid))
    return h

def status_note(text):
    d = new('div', custom_style='Status Note')
    d.append(new('p', text))
    return d

def placeholder(fname):
    d = new('div', custom_style='Placeholder Note')
    d.append(new('p', f'[Placeholder: {fname} is empty in the source files. Add this section\u2019s content here.]'))
    return d

STRIP_SEL = ['script', 'style', 'svg', 'nav', 'button', 'label', 'input', 'noscript',
             '.print-button-wrapper', '.no-print', '.course-search-wrap',
             '.course-listing-controls', '.course-listing-noresults']

from PIL import ImageFont
_FR = ImageFont.truetype(find_font('Regular'), 90)
_FB = ImageFont.truetype(find_font('Bold'), 90)
def _wpt(word, bold=False, size=9.0):
    """Width of a word in points at the given font size (Liberation Sans = Arial metrics)."""
    return (_FB if bold else _FR).getlength(word) * size / 90.0

def table_colgroup(t):
    """Column widths: proportional to content, but never narrower than the longest word
    (so words are not broken mid-word). Text width of the page = 468 pt."""
    TOTAL, PAD = 468.0, 9.0
    rows = t.find_all('tr')
    pending = {}; ncols = 0; data = []
    for r in rows:
        col = 0; row_cells = []
        for c in r.find_all(['td', 'th'], recursive=False):
            while pending.get(col, 0) > 0:
                pending[col] -= 1; col += 1
            cs = int(c.get('colspan', 1) or 1); rs = int(c.get('rowspan', 1) or 1)
            row_cells.append((col, cs, c))
            if rs > 1:
                for k in range(cs): pending[col + k] = rs - 1
            col += cs
        ncols = max(ncols, col); data.append(row_cells)
    if ncols == 0:
        return None
    lens = [[] for _ in range(ncols)]; floor = [0.0] * ncols
    for row in data:
        for col, cs, c in row:
            if cs == 1 and col < ncols:
                s = txt(c); lens[col].append(min(len(s), 70))
                bold = c.name == 'th'
                words = s.split()
                if words:
                    floor[col] = max(floor[col], max(_wpt(w, bold) for w in words) + PAD)
    raw = []
    for L in lens:
        if L:
            mean = sum(L) / len(L)
            raw.append(max(6.0, min(45.0, 0.6 * mean + 0.4 * max(L))))
        else:
            raw.append(10.0)
    share = [r / sum(raw) * TOTAL for r in raw]
    w = [max(s, f) for s, f in zip(share, floor)]
    # take any excess back from columns that are above their floor
    for _ in range(50):
        excess = sum(w) - TOTAL
        if excess <= 0.01: break
        room = [max(0.0, wi - fi) for wi, fi in zip(w, floor)]
        if sum(room) <= 0.01:
            w = [wi * TOTAL / sum(w) for wi in w]; break
        take = min(excess, sum(room))
        w = [wi - take * ri / sum(room) for wi, ri in zip(w, room)]
    tot = sum(w)
    cg = out.new_tag('colgroup')
    for wi in w:
        c = out.new_tag('col'); c['style'] = f'width: {100 * wi / tot:.2f}%'
        cg.append(c)
    return cg

import copy

def _cells(r): return r.find_all(['td', 'th'], recursive=False)
def _int(v):
    try: return max(1, int(v))
    except Exception: return 1

def _note_paragraph(r):
    cells = _cells(r)
    p = out.new_tag('p')
    def fill(c):
        frag = BeautifulSoup(c.decode_contents(), 'html.parser')
        for node in list(frag.contents): p.append(node.extract())
    if len(cells) == 1:
        fill(cells[0])
    else:
        st = out.new_tag('strong'); st.string = txt(cells[0]).rstrip(':') + ':'
        p.append(st); p.append(' ')
        for i, c in enumerate(cells[1:]):
            if i: p.append(' / ')
            fill(c)
    d = out.new_tag('div'); d['custom-style'] = 'Table Total'; d.append(p)
    return d

restructure_log = dict(split_tables=0, subtables=0, notes=0, rowspans_expanded=0, no_thead=[], leftover_unmerged=0)

def restructure_table(t, fname):
    cap = t.find('caption'); orig = txt(cap) if cap else ''
    rows = t.find_all('tr')
    if not rows: return
    thead = t.find('thead')
    head_ids = {id(r) for r in (thead.find_all('tr') if thead else [])}
    # --- expand rowspans: repeat the value in each row it covered
    carry = {}
    for r in rows:
        queue = _cells(r); newcells = []; col = 0
        while True:
            if col in carry and carry[col][1] > 0:
                c = copy.copy(carry[col][0]); c.attrs.pop('rowspan', None)
                carry[col][1] -= 1; newcells.append(c); col += _int(c.get('colspan'))
                restructure_log['rowspans_expanded'] += 1
            elif queue:
                c = queue.pop(0); rs = _int(c.get('rowspan'))
                if rs > 1:
                    carry[col] = [copy.copy(c), rs - 1]
                c.attrs.pop('rowspan', None)
                newcells.append(c); col += _int(c.get('colspan'))
            elif any(k >= col and v[1] > 0 for k, v in carry.items()):
                col += 1
            else:
                break
        r.clear()
        for c in newcells: r.append(c)
    # --- header rows
    if not head_ids:
        first = rows[0]
        if all(c.name == 'th' for c in _cells(first)):
            head_ids = {id(first)}
        else:
            for c in _cells(first): c.name = 'th'          # promote first row to header cells
            head_ids = {id(first)}
            restructure_log['no_thead'].append(fname)
    head_rows = [r for r in rows if id(r) in head_ids]
    body_rows = [r for r in rows if id(r) not in head_ids]
    ncols = max(sum(_int(c.get('colspan')) for c in _cells(r)) for r in rows)
    span_row = lambda r: any(_int(c.get('colspan')) > 1 for c in _cells(r))
    divider = lambda r: len(_cells(r)) == 1 and _int(_cells(r)[0].get('colspan')) >= ncols and ncols > 1
    # --- segment at section rows / total rows
    segs = []; cur = dict(label=None, rows=[])
    for i, r in enumerate(body_rows):
        if divider(r):
            j = i + 1; has = False
            while j < len(body_rows) and not divider(body_rows[j]):
                if not span_row(body_rows[j]): has = True; break
                j += 1
            if cur['rows']: segs.append(('t', cur)); cur = dict(label=None, rows=[])
            if has: cur = dict(label=txt(r), rows=[])
            else: segs.append(('n', r))
        elif span_row(r):
            if cur['rows']: segs.append(('t', cur)); cur = dict(label=cur['label'] if False else None, rows=[])
            segs.append(('n', r))
        else:
            cur['rows'].append(r)
    if cur['rows']: segs.append(('t', cur))
    tabs = [s for k, s in segs if k == 't']
    needs_split = any(k == 'n' for k, _ in segs) or any(s['label'] for s in tabs)
    if not needs_split:
        t['data-title'] = orig
        return
    restructure_log['split_tables'] += 1
    # shared column widths computed over all ordinary rows so every sub-table lines up
    tmp = out.new_tag('table')
    for r in head_rows: tmp.append(copy.copy(r))
    for s in tabs:
        for r in s['rows']: tmp.append(copy.copy(r))
    cg = table_colgroup(tmp)
    multi = len(tabs) > 1
    nodes = []
    if multi and orig:
        d = new('div', custom_style='Table Title'); d.append(new('p', orig)); nodes.append(d)
    for kind, s in segs:
        if kind == 't':
            nt = out.new_tag('table')
            capt = s['label'] if multi else (' \u2013 '.join(x for x in (orig, s['label']) if x))
            if capt:
                c = out.new_tag('caption'); c.string = capt; nt.append(c)
            if cg is not None: nt.append(copy.copy(cg))
            th = out.new_tag('thead')
            for hr in head_rows: th.append(copy.copy(hr))
            nt.append(th)
            tb = out.new_tag('tbody')
            for r in s['rows']: tb.append(r.extract())
            nt.append(tb)
            nt['data-title'] = ' \u2013 '.join(x for x in (orig, s['label']) if x)
            nodes.append(nt); restructure_log['subtables'] += 1
        else:
            nodes.append(_note_paragraph(s)); restructure_log['notes'] += 1
    for n in nodes: t.insert_before(n)
    t.decompose()

def unmerge_leftovers(t):
    for c in list(t.find_all(['td', 'th'])):
        cs = _int(c.get('colspan'))
        if cs > 1:
            for _ in range(cs - 1):
                e = out.new_tag(c.name); c.insert_after(e)
            restructure_log['leftover_unmerged'] += 1
        c.attrs.pop('colspan', None); c.attrs.pop('rowspan', None)

def prepare_page(fname):
    """Return the cleaned <main> of a page (a detached Tag), or None when the page is empty."""
    s = soup_of(f'{SRC}/{fname}')
    m = s.find('main')
    if m is None:
        return None
    # subject headings: keep only the subject name
    for h in m.select('h2.subject-heading'):
        n = h.select_one('.subject-name')
        name = txt(n) if n else txt(h)
        h.clear(); h.string = name
    for sel in STRIP_SEL:
        for el in m.select(sel):
            el.decompose()
    # course entries: move id onto the title heading, drop empty outline links
    for ce in m.select('div.course-entry'):
        t = ce.find('h3')
        if t is not None and ce.get('id'):
            t['id'] = ce['id']
    for o in m.select('p.course-outline'):
        a = o.find('a')
        in_course = o.find_parent('div', class_='course-entry') is not None
        if in_course:
            # course-listing "Detailed Outline" links that point nowhere are dropped
            if a is None or not a.get('href', '').strip():
                o.decompose()
        else:
            # program-page footnotes / table notes are real content: keep them as a small note style
            w = out.new_tag('div'); w['custom-style'] = 'Table Note'
            o.wrap(w)
    # meta paragraphs get their own Word styles
    for p in list(m.select('p.course-meta')):
        in_course = p.find_parent('div', class_='course-entry') is not None
        w = out.new_tag('div'); w['custom-style'] = 'Course Meta' if in_course else 'Program Meta'
        p.wrap(w)
    # remove empty paragraphs
    for p in m.find_all('p'):
        if not p.get_text(strip=True).replace('\xa0', '') and not p.find(['img', 'br']):
            p.decompose()
    for sec in m.find_all('section'):
        if 'program-section' in (sec.get('class') or []):
            sec['data-ps'] = '1'
    for a in m.find_all('a'):
        a['data-src'] = fname
    # accreditation seal size
    for im in m.find_all('img'):
        im['width'] = '1.3in'
        if 'height' in im.attrs: del im['height']
    # unwrap helper wrappers and drop presentational attributes
    for el in m.find_all(['div', 'span', 'section', 'center', 'font']):
        if el.name == 'div' and el.get('custom-style'):
            continue
        if el.name == 'section' and el.get('data-ps'):
            continue
        if el.name == 'div' and el.get('id') and 'course-entry' not in (el.get('class') or []):
            continue
        el.unwrap()
    for el in m.find_all(True):
        if el.name == 'col':
            continue
        for attr in ('class', 'style', 'aria-label', 'aria-labelledby', 'aria-live', 'role', 'hidden',
                     'data-prefix', 'tabindex', 'align', 'width' if el.name not in ('img', 'col') else '_', 'valign'):
            if attr in el.attrs: del el.attrs[attr]
    # accessibility: remove merged cells (split tables at section rows, unmerge the rest)
    for t in list(m.find_all('table')):
        restructure_table(t, fname)
    for t in m.find_all('table'):
        unmerge_leftovers(t)
        if t.find('colgroup') is None:
            cg = table_colgroup(t)
            if cg is not None:
                cap = t.find('caption')
                (cap.insert_after(cg) if cap else t.insert(0, cg))
    return m

def retag(h, newlevel):
    h.name = f'h{newlevel}'

def emit_children(m, fname, levelmap, drop_first_h1=True, ids_stem=None, base=1):
    """Return list of nodes from m with headings remapped."""
    s = ids_stem or stem(fname)
    hs = m.find_all(re.compile(r'^h[1-6]$'))
    if drop_first_h1:
        for h in hs:
            if h.name == 'h1':
                h.decompose(); break
    for h in m.find_all(re.compile(r'^h[1-6]$')):
        lv = int(h.name[1])
        retag(h, levelmap.get(lv, min(6, lv + 2)))
    prev_lv = base
    for h in m.find_all(re.compile(r'^h[1-6]$')):
        lv = int(h.name[1])
        if lv > prev_lv + 1:
            lv = prev_lv + 1; retag(h, lv)
        prev_lv = lv
    # prefix ids of remaining elements and register anchors
    for el in m.find_all(True):
        if el.get('id') and not re.match(r'^(ct|pg|sub|ch|pw)_', el['id']):
            raw = el['id']
            newid = f'x_{s}_{san(raw)}'
            if (fname, raw) not in anchors:
                anchors[(fname, raw)] = newid
            el['id'] = anchors[(fname, raw)]
    return list(m.children)

def add_nodes(nodes):
    for n in nodes:
        if isinstance(n, NavigableString) and not str(n).strip():
            continue
        body.append(n.extract() if isinstance(n, Tag) else n)

def add_page(fname, levelmap, drop_first_h1=True, base=1):
    included.append(fname)
    m = prepare_page(fname)
    if m is None:
        empty_pages.append(fname)
        return False
    multi_h1 = len(m.find_all('h1')) > 1
    if multi_h1:
        levelmap = {1: levelmap.get('multi1', 3), 2: levelmap.get('multi2', 4), 3: levelmap.get('multi3', 5)}
        drop_first_h1 = False
    add_nodes(emit_children(m, fname, levelmap, drop_first_h1, base=base))
    return True

# ------------------------------------------------------------------ assemble
SINGLE = {2: 2, 3: 3, 4: 4}
SUB = {2: 3, 3: 4, 4: 5, 'multi1': 3, 'multi2': 4, 'multi3': 5}
SINGLE_M = {2: 2, 3: 3, 4: 4, 'multi1': 2, 'multi2': 3, 'multi3': 4}
PROG = {2: 5, 3: 6, 4: 6}

# labels for cert-page sections gathered from the program tree
cert_labels = {}
for ch in chapters:
    for sub in ch['subs']:
        for pw in (sub['pathways'] or []):
            for e in pw['entries']:
                if e['frag']:
                    cert_labels[(e['file'], e['frag'])] = (e['label'], e['status'])

for ci, ch in enumerate(chapters, 1):
    files = []
    for f in [ch['file']] + [s['file'] for s in ch['subs']]:
        if f not in files: files.append(f)
    ch_id = f'ch_{ci:02d}'
    body.append(heading(1, ch['label'], ch_id, 1))
    if len(files) == 1:
        f = files[0]
        anchors[(f, '')] = ch_id
        ok = add_page(f, SINGLE_M)
        if not ok:
            body.append(placeholder(f))
        continue
    if ch['file'] not in [x['file'] for x in ch['subs']]:
        # landing page with its own intro text: placed directly under the chapter heading
        anchors[(ch['file'], '')] = ch_id
        if not add_page(ch['file'], SINGLE_M):
            body.append(placeholder(ch['file']))
    for si, sub in enumerate(ch['subs']):
        f = sub['file']
        if f in included and not sub['pathways']:
            continue
        sid = f'sub_{stem(f)}'
        anchors[(f, '')] = sid
        if f == ch['file']:
            anchors[(ch['file'], '')] = sid
        body.append(heading(2, sub['label'], sid, 2))
        ok = add_page(f, SUB, base=2)
        if not ok:
            body.append(placeholder(f))
        if sub['pathways']:
            for pi, pw in enumerate(sub['pathways'], 1):
                pid = f'pw_{pi:02d}'
                body.append(heading(3, pw['label'], pid, 3))
                for e in pw['entries']:
                    f2 = e['file']
                    if f2 in included:
                        continue
                    if not e['frag']:
                        gid = f'pg_{stem(f2)}'
                        anchors[(f2, '')] = gid
                        body.append(heading(4, e['label'], gid, 4))
                        if e['status']:
                            body.append(status_note('Status: ' + e['status']))
                        ok = add_page(f2, PROG, base=4)
                        if not ok:
                            body.append(placeholder(f2))
                    else:
                        # certificate group page: included once, sections become Certificate headings
                        included.append(f2)
                        m = prepare_page(f2)
                        if m is None:
                            empty_pages.append(f2); continue
                        h1 = m.find('h1')
                        gid = f'pg_{stem(f2)}'
                        anchors[(f2, '')] = gid
                        gtext = txt(h1) if h1 else e['label']
                        body.append(heading(4, gtext, gid, 4))
                        if h1: h1.decompose()
                        # section ids
                        for sec in m.find_all('section', attrs={'data-ps': '1'}):
                            secid = sec.get('id')
                            h2 = sec.find('h2')
                            label, status = cert_labels.get((f2, secid), (txt(h2) if h2 else secid, ''))
                            cid = f'ct_{stem(f2)}_{san(secid)}'
                            anchors[(f2, secid)] = cid
                            toc_entries.append(dict(level=5, text=label, id=cid))
                            if h2 is not None:
                                h2.string = label
                                h2['id'] = cid
                            if secid: del sec['id']
                            del sec.attrs['data-ps']
                            if status and h2 is not None:
                                h2.insert_after(status_note('Status: ' + status))
                            sec.unwrap()
                        add_nodes(emit_children(m, f2, {2: 5, 3: 6, 4: 6}, drop_first_h1=False, base=4))

# ------------------------------------------------------------------ fix links
inc = set(included)
unresolved = []
stats = dict(internal=0, site=0, external=0, dropped=0)
for a in list(body.find_all('a')):
    href = (a.get('href') or '').strip()
    cur = a.get('data-src', '')
    if 'data-src' in a.attrs: del a.attrs['data-src']
    if not href or href.lower().startswith('javascript:'):
        a.unwrap(); stats['dropped'] += 1; continue
    if re.match(r'^(https?:|mailto:|tel:)', href, re.I):
        stats['external'] += 1; continue
    if href.startswith('#'):
        tgt = anchors.get((cur, href[1:]))
        if tgt: a['href'] = '#' + tgt; stats['internal'] += 1
        else: unresolved.append((cur, href)); a.unwrap(); stats['dropped'] += 1
        continue
    base, _, frag = href.partition('#')
    if base in inc:
        tgt = anchors.get((base, frag)) or anchors.get((base, ''))
        if tgt: a['href'] = '#' + tgt; stats['internal'] += 1
        else: unresolved.append((cur, href)); a.unwrap(); stats['dropped'] += 1
    elif re.match(r'^(www\.|[\w-]+(\.[\w-]+)+/)', base) and not base.endswith('.html'):
        a['href'] = 'https://' + href; stats['external'] += 1
    elif base.endswith('.html'):
        a['href'] = SITE + base + ('#' + frag if frag else ''); stats['site'] += 1
    else:
        unresolved.append((cur, href)); a.unwrap(); stats['dropped'] += 1

for a in body.find_all('a'):
    if 'data-src' in a.attrs: del a.attrs['data-src']

tables_meta = []
for t in body.find_all('table'):
    cap = t.find('caption')
    title = t.get('data-title') or (txt(cap) if cap else '')
    if not title:
        h = t.find_previous(re.compile(r'^h[1-6]$')); title = txt(h) if h else 'Table'
    heads = [txt(c) for c in (t.find('thead').find_all('th') if t.find('thead') else [])]
    if cap is None:
        c = out.new_tag('caption'); c.string = title; t.insert(0, c)
    tables_meta.append(dict(title=title, headers=heads, rows=len(t.find_all('tr'))))
    t.attrs.pop('data-title', None)
open(f'{OUT}/combined.html', 'w', encoding='utf-8').write(str(out))
json.dump(dict(toc=toc_entries, included=included, empty=empty_pages,
               skipped=skipped_chapters, unresolved=unresolved, stats=stats, tables=tables_meta, restructure=restructure_log),
          open(f'{OUT}/structure.json', 'w'), indent=1)
print('pages included:', len(included), '| empty:', empty_pages, '| skipped chapters:', skipped_chapters)
print('toc entries:', len(toc_entries), '| levels:', {l: sum(1 for e in toc_entries if e["level"]==l) for l in range(1,6)})
print('table restructure:', restructure_log)
print('links:', stats, '| unresolved:', unresolved[:15])
