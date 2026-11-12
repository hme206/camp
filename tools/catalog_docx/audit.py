import re, sys, zipfile, json
from lxml import etree
path = sys.argv[1]
STRICT = '--strict' in sys.argv
FAILS = []
z = zipfile.ZipFile(path)
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
ns = {'w': W, 'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'}
doc = etree.fromstring(z.read('word/document.xml'))
q = lambda t: '{%s}%s' % (W, t)

# 1 merged cells
merged = len(doc.xpath('//w:tcPr/w:gridSpan | //w:tcPr/w:vMerge | //w:tcPr/w:hMerge', namespaces=ns))
print('1. merged/split cells (gridSpan/vMerge/hMerge):', merged)
if merged: FAILS.append(f'{merged} merged/split table cells')

# 2 header rows + 3 empty cells
tbls = doc.xpath('//w:tbl', namespaces=ns)
nohdr = [i for i, t in enumerate(tbls) if t.find(q('tr')).find(q('trPr') + '/' + q('tblHeader')) is None]
nocap = [i for i, t in enumerate(tbls) if t.find(q('tblPr') + '/' + q('tblCaption')) is None]
empty_hdr = empty_body = 0
for t in tbls:
    for ri, tr in enumerate(t.findall(q('tr'))):
        for tc in tr.findall(q('tc')):
            has = ''.join(tc.itertext()).strip() != ''
            if not has:
                if ri == 0: empty_hdr += 1
                else: empty_body += 1
print(f'2. tables: {len(tbls)} | without repeating header row: {len(nohdr)} | without title: {len(nocap)} | description present on all:', all(t.find(q('tblPr') + '/' + q('tblDescription')) is not None for t in tbls))
if nohdr: FAILS.append(f'{len(nohdr)} tables without a header row')
if nocap: FAILS.append(f'{len(nocap)} tables without a title')
if empty_hdr: FAILS.append(f'{empty_hdr} empty header cells')
print(f'3. empty header cells: {empty_hdr} | empty body cells: {empty_body}')

# 4 heading order
LV = {'Heading1': 1, 'Heading2': 2, 'Heading3': 3, 'Heading4': 4, 'Heading5': 5, 'Heading6': 6, 'PathwayHeading': 3, 'ProgramHeading': 4, 'CertificateHeading': 5}
prev = 0; skips = []; n = 0
for p in doc.iter(q('p')):
    ps = p.find(q('pPr') + '/' + q('pStyle'))
    s = ps.get(q('val')) if ps is not None else None
    if s in LV:
        n += 1; lv = LV[s]; txt = ''.join(p.itertext())[:50]
        if lv > prev + 1: skips.append((prev, lv, txt))
        if not txt.strip(): skips.append(('EMPTY HEADING', lv, ''))
        prev = lv
if skips: FAILS.append(f'{len(skips)} heading-order problems: {skips[:3]}')
print(f'4. headings: {n} | skipped levels: {len(skips)}', skips[:12])

# 5 images
dps = doc.xpath('//wp:docPr', namespaces=ns)
if any(not (d.get('descr') or '').strip() for d in dps): FAILS.append('image without alt text')
print('5. images:', len(dps), '| without alt text:', sum(1 for d in dps if not (d.get('descr') or '').strip()))

# 6 empty paragraphs (outside tables) that carry nothing
empties = 0
for p in doc.xpath('/w:document/w:body/w:p', namespaces=ns):
    if ''.join(p.itertext()).strip() == '' and not p.xpath('.//w:drawing|.//w:sectPr|.//w:br', namespaces=ns):
        empties += 1
print('6. empty body paragraphs:', empties)
if empties: FAILS.append(f'{empties} empty paragraphs')

# 7 language, title
styles = z.read('word/styles.xml').decode()
core = z.read('docProps/core.xml').decode()
if 'en-US' not in styles: FAILS.append('document language not set')
if not re.search(r'<dc:title>.+</dc:title>', core): FAILS.append('document title not set')
print('7. language en-US in defaults:', 'w:lang w:val="en-US"' in styles or "w:val=\"en-US\"" in styles, '| title property:', bool(re.search(r'<dc:title>.+</dc:title>', core)))

# 8 links
rels = z.read('word/_rels/document.xml.rels').decode()
GENERIC = re.compile(r'^(here|click here|link|this link|read more|more|this page|this)$', re.I)
texts = [''.join(h.itertext()).strip() for h in doc.iter(q('hyperlink'))]
bad = [t for t in texts if GENERIC.match(t)]
raw = [t for t in texts if re.match(r'^(https?://|www\.)', t)]
print(f'8. hyperlinks: {len(texts)} | generic text: {len(bad)} {bad[:5]} | raw-URL text: {len(raw)}')

# 9 sizes
szs = [int(e.get(q('val'))) for e in etree.fromstring(z.read('word/styles.xml')).iter(q('sz'))]
print('9. smallest style font size (pt):', min(szs) / 2)

# 10 contrast
def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
def cr(a, b):
    la, lb = lum(a), lum(b)
    if la < lb: la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)
pairs = [('Body text on white', '000000', 'FFFFFF'), ('Headings (dark green) on white', '1A5C14', 'FFFFFF'),
         ('Pathway heading on light-green band', '1A5C14', 'EAF7EA'), ('Muted text (meta/notes/header) on white', '555555', 'FFFFFF'),
         ('Course meta on white', '555555', 'FFFFFF'), ('Table header: black on green', '000000', '5DC956'),
         ('Table text on banded row', '000000', 'F2FBF2'), ('Hyperlink on white', '0B5394', 'FFFFFF'),
         ('Hyperlink on light-green box', '0B5394', 'EAF7EA'), ('Hyperlink on banded row', '0B5394', 'F2FBF2'),
         ('Page numbers/header (muted) on white', '555555', 'FFFFFF')]
print('10. contrast (AA needs 4.5:1 for text):')
for n, f, b in pairs:
    r = cr(f, b)
    if r < 4.5: FAILS.append(f'low contrast: {n} ({r:.1f}:1)')
    print(f'     {r:5.1f}:1  {"PASS" if r >= 4.5 else "FAIL"}  {n}')

if FAILS:
    print('\nACCESSIBILITY AUDIT FAILED:'); [print('  -', f) for f in FAILS]
    if STRICT: sys.exit(1)
else:
    print('\nACCESSIBILITY AUDIT PASSED')
