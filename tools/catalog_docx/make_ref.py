#!/usr/bin/env python3
"""Create reference.docx (Word template) styled from the Camp catalog CSS."""
import copy
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import BUILD, YEARS, COLLEGE
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.shared import Pt, RGBColor, Inches
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

GREEN_D, GOLD, LIGHT, MID, BORDER, MUTED = '1A5C14', 'B8922A', 'EAF7EA', '5DC956', '8FCE8B', '555555'
FONT = 'Arial'

d = Document(os.path.join(BUILD, 'ref0.docx'))
st = d.styles
S = {x.name: x for x in st}

# ---------- fonts: drop theme fonts everywhere, force Arial
def force_arial(rpr):
    rf = rpr.find(qn('w:rFonts'))
    if rf is None:
        rf = OxmlElement('w:rFonts'); rpr.insert(0, rf)
    for a in list(rf.attrib):
        del rf.attrib[a]
    for a in ('ascii', 'hAnsi', 'cs', 'eastAsia'):
        rf.set(qn(f'w:{a}'), FONT)

root = st.element
dd = root.find(qn('w:docDefaults'))
if dd is not None:
    rpr = dd.find(qn('w:rPrDefault')).find(qn('w:rPr'))
    force_arial(rpr)
    for tag in ('w:sz', 'w:szCs'):
        e = rpr.find(qn(tag))
        if e is None:
            e = OxmlElement(tag); rpr.append(e)
        e.set(qn('w:val'), '21')           # 10.5 pt
for s in st:
    el = s.element
    rpr = el.find(qn('w:rPr'))
    if rpr is not None and rpr.find(qn('w:rFonts')) is not None:
        force_arial(rpr)

def rgb(h): return RGBColor.from_string(h)

def pbdr(style, side='bottom', sz=8, color=GOLD, space=3):
    ppr = style.element.get_or_add_pPr()
    b = ppr.find(qn('w:pBdr'))
    if b is None:
        b = OxmlElement('w:pBdr'); ppr.append(b)
    e = OxmlElement(f'w:{side}')
    e.set(qn('w:val'), 'single'); e.set(qn('w:sz'), str(sz)); e.set(qn('w:space'), str(space)); e.set(qn('w:color'), color)
    b.append(e)

def shade(style, fill):
    ppr = style.element.get_or_add_pPr()
    sh = OxmlElement('w:shd'); sh.set(qn('w:val'), 'clear'); sh.set(qn('w:color'), 'auto'); sh.set(qn('w:fill'), fill)
    ppr.append(sh)

def fmt(style, size=None, bold=None, italic=None, color=None, before=None, after=None,
        keep_next=None, keep_lines=None, line=None, left=None, page_break=None):
    f = style.font; pf = style.paragraph_format
    f.name = FONT
    force_arial(style.element.get_or_add_rPr())
    if size is not None: f.size = Pt(size)
    if bold is not None: f.bold = bold
    if italic is not None: f.italic = italic
    if color: f.color.rgb = rgb(color)
    if before is not None: pf.space_before = Pt(before)
    if after is not None: pf.space_after = Pt(after)
    if keep_next is not None: pf.keep_with_next = keep_next
    if keep_lines is not None: pf.keep_together = keep_lines
    if line is not None: pf.line_spacing = line
    if left is not None: pf.left_indent = Inches(left)
    if page_break is not None: pf.page_break_before = page_break

# ---------- body styles
fmt(S['Normal'], size=10.5, line=1.15, before=0, after=0)
for n in ('Body Text', 'First Paragraph'):
    fmt(st[n], size=10.5, line=1.15, before=0, after=6)
fmt(S['Compact'], size=10.5, line=1.1, before=0, after=2)
fmt(S['Block Text'], size=10.5, italic=True, color=MUTED, before=4, after=6)
fmt(S['Table Caption'], size=10.5, bold=True, italic=False, color=GREEN_D, before=8, after=4, keep_next=True)
fmt(S['Footnote Text'], size=9)

# ---------- headings (mirrors .catalog-content h1/h2/h3: dark green, gold rule)
H = {
    'Heading 1': dict(italic=False, size=22, bold=True, color=GREEN_D, before=0, after=14, keep_next=True, keep_lines=True, page_break=True),
    'Heading 2': dict(italic=False, size=16, bold=True, color=GREEN_D, before=22, after=8, keep_next=True, keep_lines=True),
    'Heading 3': dict(italic=False, size=13, bold=True, color=GREEN_D, before=14, after=5, keep_next=True, keep_lines=True),
    'Heading 4': dict(italic=False, size=11.5, bold=True, color=GREEN_D, before=11, after=4, keep_next=True, keep_lines=True),
    'Heading 5': dict(size=10.5, bold=True, italic=True, color=GREEN_D, before=10, after=3, keep_next=True, keep_lines=True),
    'Heading 6': dict(italic=False, size=10.5, bold=True, color=MUTED, before=8, after=3, keep_next=True, keep_lines=True),
}
for name, kw in H.items():
    fmt(S[name], **kw)
pbdr(S['Heading 1'], sz=18, space=4)
pbdr(S['Heading 2'], sz=8, space=3)

# ---------- custom paragraph styles
def custom(name, base, **kw):
    s = st.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    S[name] = s
    s.base_style = S[base]
    s.quick_style = True
    fmt(s, **kw)
    return s

# program navigation levels: appear in the TOC (via \t switch) and in Word's Navigation pane
pw = custom('Pathway Heading', 'Heading 3', italic=False, size=14, bold=True, color=GREEN_D, before=0, after=10, keep_next=True, keep_lines=True, page_break=True)
shade(pw, LIGHT); pbdr(pw, 'left', sz=36, color=GOLD, space=6)
pbdr(pw, 'bottom', sz=4, color=BORDER, space=2)
pg = custom('Program Heading', 'Heading 4', italic=False, size=13.5, bold=True, color=GREEN_D, before=0, after=6, keep_next=True, keep_lines=True, page_break=True)
pbdr(pg, 'bottom', sz=8, color=GOLD, space=3)
ct = custom('Certificate Heading', 'Heading 5', size=12, bold=True, italic=False, color=GREEN_D, before=18, after=5, keep_next=True, keep_lines=True)
pbdr(ct, 'bottom', sz=4, color=BORDER, space=2)

pm = custom('Program Meta', 'Body Text', size=10, line=1.2, before=2, after=8)
shade(pm, LIGHT); pbdr(pm, 'left', sz=24, color=GOLD, space=6)
cm = custom('Course Meta', 'Body Text', size=9, color=MUTED, line=1.15, before=0, after=8)
tt2 = custom('Table Title', 'Body Text', size=11, bold=True, color=GREEN_D, before=10, after=2, keep_next=True)
tot = custom('Table Total', 'Body Text', size=10, bold=True, before=3, after=8)
shade(tot, LIGHT)
tn = custom('Table Note', 'Body Text', size=9, line=1.15, before=4, after=8)
sn = custom('Status Note', 'Body Text', size=9.5, italic=True, color=MUTED, before=0, after=6)
ph = custom('Placeholder Note', 'Body Text', size=10, italic=True, before=4, after=6)
# yellow highlight so the placeholder is noticed
ph.element.get_or_add_rPr().append(parse_xml(f'<w:highlight {nsdecls("w")} w:val="yellow"/>'))

# table text styles (mirrors .catalog-content table: .88rem)
tx = custom('Table Text', 'Compact', size=9, line=1.05, before=1, after=1)
th = custom('Table Header', 'Table Text', bold=True, color='000000')

# TOC title (not an outline level, so it is not listed in itself)
tt = S['TOC Heading']
fmt(tt, size=22, bold=True, color=GREEN_D, before=0, after=10)
pbdr(tt, sz=18, space=4)
ppr = tt.element.get_or_add_pPr()
for ol in ppr.findall(qn('w:outlineLvl')): ppr.remove(ol)

# ---------- TOC 1..5 styles (names must be 'toc N' for Word to regenerate them)
TOC = {1: dict(ind=0, sz=20, b=True, before=90, after=10),
       2: dict(ind=220, sz=19, b=False, before=0, after=0),
       3: dict(ind=440, sz=18, b=True, before=40, after=0),
       4: dict(ind=660, sz=18, b=False, before=0, after=0),
       5: dict(ind=880, sz=18, b=False, before=0, after=0)}
for n, o in TOC.items():
    xml = f'''<w:style {nsdecls("w")} w:type="paragraph" w:styleId="TOC{n}">
  <w:name w:val="toc {n}"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:uiPriority w:val="39"/><w:unhideWhenUsed/>
  <w:pPr><w:tabs><w:tab w:val="right" w:leader="dot" w:pos="9350"/></w:tabs>
    <w:spacing w:before="{o['before']}" w:after="{o['after']}" w:line="240" w:lineRule="auto"/><w:ind w:left="{o['ind']}"/></w:pPr>
  <w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:cs="{FONT}"/>{'<w:b/>' if o['b'] else ''}<w:sz w:val="{o['sz']}"/><w:szCs w:val="{o['sz']}"/></w:rPr>
</w:style>'''
    root.append(parse_xml(xml))

# ---------- hyperlink character style
hl = None
for s in st:
    if s.name == 'Hyperlink': hl = s
if hl is None:
    hl = st.add_style('Hyperlink', WD_STYLE_TYPE.CHARACTER)
hl.font.color.rgb = rgb('0B5394'); hl.font.underline = True

# ---------- page setup, header, footer
sec = d.sections[0]
sec.page_width, sec.page_height = Inches(8.5), Inches(11)
sec.left_margin = sec.right_margin = Inches(1.0)
sec.top_margin, sec.bottom_margin = Inches(1.0), Inches(0.9)
sec.header_distance = sec.footer_distance = Inches(0.45)

hp = sec.header.paragraphs[0]
hp.text = ''
r = hp.add_run(COLLEGE); r.font.size = Pt(9); r.font.color.rgb = rgb(GREEN_D); r.bold = True
r = hp.add_run('\t' + YEARS + ' Catalog & Student Handbook'); r.font.size = Pt(9); r.font.color.rgb = rgb(MUTED)
ppr = hp._p.get_or_add_pPr()
ppr.append(parse_xml(f'<w:tabs {nsdecls("w")}><w:tab w:val="clear" w:pos="4680"/><w:tab w:val="clear" w:pos="9360"/><w:tab w:val="right" w:pos="9360"/></w:tabs>'))
ppr.append(parse_xml(f'<w:pBdr {nsdecls("w")}><w:bottom w:val="single" w:sz="6" w:space="4" w:color="{GOLD}"/></w:pBdr>'))

fp = sec.footer.paragraphs[0]
fp.text = ''
fp.alignment = 1
def fld(par, instr):
    for t, extra in (('begin', None), ('instr', instr), ('separate', None), ('text', '1'), ('end', None)):
        r = par.add_run(); r.font.size = Pt(9); r.font.color.rgb = rgb(MUTED)
        if t == 'instr':
            e = OxmlElement('w:instrText'); e.set(qn('xml:space'), 'preserve'); e.text = f' {extra} '; r._r.append(e)
        elif t == 'text':
            r.text = extra
        else:
            e = OxmlElement('w:fldChar'); e.set(qn('w:fldCharType'), t); r._r.append(e)
fld(fp, 'PAGE')

# body-level default language
d.core_properties.title = COLLEGE + ' \u2013 ' + YEARS + ' Catalog & Student Handbook'
d.core_properties.author = COLLEGE
d.save(os.path.join(BUILD, 'reference.docx'))
print('reference.docx written')
