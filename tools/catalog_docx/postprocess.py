#!/usr/bin/env python3
"""Post-process body.docx: restyle headings/tables, add cover + pre-filled TOC + section numbering."""
import copy, json, os, re, sys
from xml.sax.saxutils import escape
from docx import Document
from docx.shared import Inches, Pt
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import qn, nsdecls
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import BUILD, SRC, YEARS, COLLEGE, COVER, COVER_ALT
pages = {}
if len(sys.argv) > 2:
    pages = json.load(open(sys.argv[2]))
OUT = sys.argv[1]
_st = json.load(open(f'{BUILD}/structure.json'))
toc = _st['toc']
TABLES = _st['tables']

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
def q(t): return qn(t)

doc = Document(f'{BUILD}/body.docx')
body = doc.element.body

# ------------------------------------------------------------- remove Title paragraph from <title>
for p in list(body.findall(q('w:p'))):
    ps = p.find(q('w:pPr') + '/' + q('w:pStyle'))
    if ps is not None and ps.get(q('w:val')) == 'Title':
        body.remove(p)

# ------------------------------------------------------------- restyle navigation headings via bookmark prefix
RESTYLE = {'pw_': 'PathwayHeading', 'pg_': 'ProgramHeading', 'ct_': 'CertificateHeading'}
n_restyled = 0
for p in body.findall(q('w:p')):
    ps = p.find(q('w:pPr') + '/' + q('w:pStyle'))
    if ps is None or ps.get(q('w:val')) not in ('Heading3', 'Heading4', 'Heading5'):
        continue
    names = []
    sib = p.getprevious()
    while sib is not None and sib.tag == q('w:bookmarkStart'):
        names.append(sib.get(q('w:name'))); sib = sib.getprevious()
    for pref, style in RESTYLE.items():
        if any(n.startswith(pref) for n in names):
            ps.set(q('w:val'), style); n_restyled += 1

# first program under a pathway shares the pathway's page (no extra page break)
def _prev_par(el):
    s = el.getprevious()
    while s is not None and s.tag != q('w:p'):
        s = s.getprevious()
    return s
def _style(par):
    ps = par.find(q('w:pPr') + '/' + q('w:pStyle')) if par is not None else None
    return ps.get(q('w:val')) if ps is not None else None
n_nobreak = 0
for p in body.findall(q('w:p')):
    if _style(p) == 'ProgramHeading' and _style(_prev_par(p)) == 'PathwayHeading':
        ppr = p.find(q('w:pPr'))
        pb = OxmlElement('w:pageBreakBefore'); pb.set(q('w:val'), '0'); ppr.append(pb); n_nobreak += 1
print('programs sharing pathway page:', n_nobreak)

# ------------------------------------------------------------- tables
BORDER, HEAD, ALT = '8FCE8B', '5DC956', 'F2FBF2'
TEXTW = 9360

def set_pstyle(p, style):
    ppr = p.find(q('w:pPr'))
    if ppr is None:
        ppr = OxmlElement('w:pPr'); p.insert(0, ppr)
    ps = ppr.find(q('w:pStyle'))
    if ps is None:
        ps = OxmlElement('w:pStyle'); ppr.insert(0, ps)
    ps.set(q('w:val'), style)

def shade_cell(tc, fill):
    tcpr = tc.find(q('w:tcPr'))
    if tcpr is None:
        tcpr = OxmlElement('w:tcPr'); tc.insert(0, tcpr)
    for s in tcpr.findall(q('w:shd')): tcpr.remove(s)
    sh = OxmlElement('w:shd'); sh.set(q('w:val'), 'clear'); sh.set(q('w:color'), 'auto'); sh.set(q('w:fill'), fill)
    tcpr.append(sh)

def tc_span(tc):
    gs = tc.find(q('w:tcPr') + '/' + q('w:gridSpan'))
    return int(gs.get(q('w:val'))) if gs is not None else 1

def order_tcpr(tcpr):
    order = ['cnfStyle', 'tcW', 'gridSpan', 'hMerge', 'vMerge', 'tcBorders', 'shd', 'noWrap', 'tcMar', 'textDirection', 'tcFitText', 'vAlign', 'hideMark']
    kids = list(tcpr)
    kids.sort(key=lambda e: order.index(e.tag.split('}')[1]) if e.tag.split('}')[1] in order else 99)
    for k in kids: tcpr.remove(k)
    for k in kids: tcpr.append(k)

tables = list(body.iter(q('w:tbl')))
if len(tables) != len(TABLES):
    print('WARNING: table count mismatch', len(tables), len(TABLES))
for ti, tbl in enumerate(tables):
    tblpr = tbl.find(q('w:tblPr'))
    grid = tbl.find(q('w:tblGrid'))
    cols = [int(g.get(q('w:w'))) for g in grid.findall(q('w:gridCol'))]
    tot = sum(cols) or 1
    scaled = [max(400, int(round(c * TEXTW / tot))) for c in cols]
    diff = TEXTW - sum(scaled); scaled[-1] += diff
    for g, w in zip(grid.findall(q('w:gridCol')), scaled):
        g.set(q('w:w'), str(w))
    # table properties: fixed width/layout, borders, cell margins
    for tag in ('w:tblW', 'w:tblLayout', 'w:tblBorders', 'w:tblCellMar'):
        for e in tblpr.findall(q(tag)): tblpr.remove(e)
    tblW = OxmlElement('w:tblW'); tblW.set(q('w:w'), str(TEXTW)); tblW.set(q('w:type'), 'dxa')
    borders = parse_xml(f'<w:tblBorders {nsdecls("w")}>' + ''.join(
        f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="{BORDER}"/>' for s in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV')) + '</w:tblBorders>')
    layout = parse_xml(f'<w:tblLayout {nsdecls("w")} w:type="fixed"/>')
    cellmar = parse_xml(f'<w:tblCellMar {nsdecls("w")}><w:top w:w="35" w:type="dxa"/><w:left w:w="80" w:type="dxa"/><w:bottom w:w="35" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar>')
    # schema order: tblStyle, tblW, jc, tblBorders, tblLayout, tblCellMar, tblLook, tblCaption
    style_el = tblpr.find(q('w:tblStyle'))
    look = tblpr.find(q('w:tblLook')); jc = tblpr.find(q('w:jc'))
    meta = TABLES[ti] if ti < len(TABLES) else dict(title='Table', headers=[], rows=0)
    cap = OxmlElement('w:tblCaption'); cap.set(q('w:val'), meta['title'])
    _h = meta['headers']
    desc = OxmlElement('w:tblDescription')
    desc.set(q('w:val'), f"Table with {len(_h)} columns and {max(meta['rows'] - 1, 0)} data rows. Column headings: {', '.join(_h)}.")
    for e in list(tblpr): tblpr.remove(e)
    for e in (style_el, tblW, jc, borders, layout, cellmar, look, cap, desc):
        if e is not None: tblpr.append(e)
    _first = tbl.find(q('w:tr'))
    _fp = _first.find(q('w:trPr'))
    if _fp is None:
        _fp = OxmlElement('w:trPr'); _first.insert(0, _fp)
    if _fp.find(q('w:tblHeader')) is None:
        _fp.append(OxmlElement('w:tblHeader'))
    # rows
    body_i = 0
    for ri, tr in enumerate(tbl.findall(q('w:tr'))):
        trpr = tr.find(q('w:trPr'))
        if trpr is None:
            trpr = OxmlElement('w:trPr'); tr.insert(0, trpr)
        is_head = trpr.find(q('w:tblHeader')) is not None
        if trpr.find(q('w:cantSplit')) is None:
            trpr.insert(0, OxmlElement('w:cantSplit'))
        col = 0
        for tc in tr.findall(q('w:tc')):
            span = tc_span(tc)
            w = sum(scaled[col:col + span]) if col < len(scaled) else scaled[-1]
            col += span
            tcpr = tc.find(q('w:tcPr'))
            if tcpr is None:
                tcpr = OxmlElement('w:tcPr'); tc.insert(0, tcpr)
            for e in tcpr.findall(q('w:tcW')): tcpr.remove(e)
            tcw = OxmlElement('w:tcW'); tcw.set(q('w:w'), str(w)); tcw.set(q('w:type'), 'dxa'); tcpr.insert(0, tcw)
            for p in tc.findall(q('w:p')):
                ps = p.find(q('w:pPr') + '/' + q('w:pStyle'))
                cur = ps.get(q('w:val')) if ps is not None else None
                if cur in (None, 'Compact', 'BodyText', 'FirstParagraph', 'Normal'):
                    set_pstyle(p, 'TableHeader' if is_head else 'TableText')
            if is_head:
                shade_cell(tc, HEAD)
            elif body_i % 2 == 1:
                shade_cell(tc, ALT)
            order_tcpr(tcpr)
        if not is_head:
            body_i += 1
    # drop the empty spacer paragraph pandoc leaves after a table (not needed when a non-table follows)
    _n = tbl.getnext()
    while _n is not None and _n.tag in (q('w:bookmarkStart'), q('w:bookmarkEnd')): _n = _n.getnext()
    if _n is not None and _n.tag == q('w:p') and not ''.join(_n.itertext()).strip() and not _n.xpath('.//w:drawing|.//w:sectPr'):
        _after = _n.getnext()
        while _after is not None and _after.tag in (q('w:bookmarkStart'), q('w:bookmarkEnd')): _after = _after.getnext()
        if _after is not None and _after.tag != q('w:tbl'):
            body.remove(_n)
    # visual gap after each table: spacing on the next paragraph (an empty spacer paragraph can spill to a blank page)
    nxt = tbl.getnext()
    while nxt is not None and nxt.tag in (q('w:bookmarkStart'), q('w:bookmarkEnd')):
        nxt = nxt.getnext()
    if nxt is not None and nxt.tag == q('w:p'):
        if _style(nxt) in (None, 'BodyText', 'FirstParagraph', 'Compact', 'Normal', 'CourseMeta', 'StatusNote', 'TableNote', 'ProgramMeta', 'TableTotal', 'TableCaption', 'TableTitle'):
            ppr = nxt.find(q('w:pPr'))
            if ppr is None:
                ppr = OxmlElement('w:pPr'); nxt.insert(0, ppr)
            sp = ppr.find(q('w:spacing'))
            if sp is None:
                sp = OxmlElement('w:spacing'); ppr.append(sp)
            sp.set(q('w:before'), '140')
    elif nxt is not None and nxt.tag == q('w:tbl'):
        tbl.addnext(parse_xml(f'<w:p {nsdecls("w")}><w:pPr><w:pStyle w:val="Normal"/><w:spacing w:before="0" w:after="0" w:line="20" w:lineRule="exact"/></w:pPr></w:p>'))

n_empty = 0
for _p in body.findall(q('w:p')):
    _ps = _p.find(q('w:pPr') + '/' + q('w:pStyle'))
    _s = _ps.get(q('w:val')) if _ps is not None else None
    if _s in ('Compact', 'BodyText', 'FirstParagraph') and not ''.join(_p.itertext()).strip() \
            and not _p.xpath('.//w:drawing|.//w:sectPr|.//w:br'):
        body.remove(_p); n_empty += 1
print('removed empty text paragraphs:', n_empty)

# ------------------------------------------------------------- TOC (pre-filled field)
def toc_entry_par(level, text, bm, page, first=False, last=False):
    runs = ''
    if first:
        runs += ('<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                 '<w:r><w:instrText xml:space="preserve"> TOC \\o "1-2" \\h \\z \\t "Pathway Heading,3,Program Heading,4,Certificate Heading,5" </w:instrText></w:r>'
                 '<w:r><w:fldChar w:fldCharType="separate"/></w:r>')
    pg = str(pages.get(bm, 0))
    runs += (f'<w:hyperlink w:anchor="{bm}" w:history="1">'
             f'<w:r><w:rPr><w:noProof/></w:rPr><w:t xml:space="preserve">{escape(text)}</w:t></w:r>'
             f'<w:r><w:rPr><w:noProof/><w:webHidden/></w:rPr><w:tab/></w:r>'
             f'<w:r><w:rPr><w:noProof/><w:webHidden/></w:rPr><w:fldChar w:fldCharType="begin"/></w:r>'
             f'<w:r><w:rPr><w:noProof/><w:webHidden/></w:rPr><w:instrText xml:space="preserve"> PAGEREF {bm} \\h </w:instrText></w:r>'
             f'<w:r><w:rPr><w:noProof/><w:webHidden/></w:rPr><w:fldChar w:fldCharType="separate"/></w:r>'
             f'<w:r><w:rPr><w:noProof/><w:webHidden/></w:rPr><w:t>{pg}</w:t></w:r>'
             f'<w:r><w:rPr><w:noProof/><w:webHidden/></w:rPr><w:fldChar w:fldCharType="end"/></w:r>'
             f'</w:hyperlink>')
    if last:
        runs += '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
    return parse_xml(f'<w:p {nsdecls("w")}><w:pPr><w:pStyle w:val="TOC{level}"/></w:pPr>{runs}</w:p>')

# section properties
final_sect = body.find(q('w:sectPr'))
hdr_ftr = [copy.deepcopy(e) for e in final_sect if e.tag in (q('w:headerReference'), q('w:footerReference'))]

def make_sect(kind):
    s = OxmlElement('w:sectPr')
    if kind == 'cover':
        s.append(parse_xml(f'<w:pgSz {nsdecls("w")} w:w="12240" w:h="15840"/>'))
        s.append(parse_xml(f'<w:pgMar {nsdecls("w")} w:top="360" w:right="360" w:bottom="360" w:left="360" w:header="0" w:footer="0" w:gutter="0"/>'))
    else:
        for e in hdr_ftr: s.append(copy.deepcopy(e))
        s.append(parse_xml(f'<w:pgSz {nsdecls("w")} w:w="12240" w:h="15840"/>'))
        s.append(parse_xml(f'<w:pgMar {nsdecls("w")} w:top="1440" w:right="1440" w:bottom="1296" w:left="1440" w:header="648" w:footer="648" w:gutter="0"/>'))
        s.append(parse_xml(f'<w:pgNumType {nsdecls("w")} w:fmt="lowerRoman" w:start="1"/>'))
    return s

# final (body) section: decimal numbering restarting at 1
pn = parse_xml(f'<w:pgNumType {nsdecls("w")} w:fmt="decimal" w:start="1"/>')
mar = final_sect.find(q('w:pgMar')); mar.addnext(pn)

front = []

# cover page (full-page image)
img_path = COVER
iw, ih = Image.open(img_path).size
width_in = 8.0
cover_p = doc.add_paragraph()
cover_p.alignment = 1
cover_p.paragraph_format.space_before = Pt(0); cover_p.paragraph_format.space_after = Pt(0)
cover_p.paragraph_format.line_spacing = 1.0
run = cover_p.add_run()
pic = run.add_picture(img_path, width=Inches(width_in))
pic._inline.docPr.set('descr', COVER_ALT)
pic._inline.docPr.set('title', 'Catalog cover')
# keep it on one page: cap height at 10.4in
if pic.height > Inches(10.4):
    ratio = Inches(10.4) / pic.height
    pic.height = int(pic.height * ratio); pic.width = int(pic.width * ratio)
cp = cover_p._p
body.remove(cp)
ppr = cp.get_or_add_pPr()
ppr.append(make_sect('cover'))
front.append(cp)

# TOC heading + entries
front.append(parse_xml(f'<w:p {nsdecls("w")}><w:pPr><w:pStyle w:val="TOCHeading"/></w:pPr><w:r><w:t>Table of Contents</w:t></w:r></w:p>'))
for i, e in enumerate(toc):
    front.append(toc_entry_par(e['level'], e['text'], e['id'], None, first=(i == 0), last=(i == len(toc) - 1)))
# the front-matter section ends with the last TOC entry paragraph (no empty paragraph needed)
front[-1].find(q('w:pPr')).append(make_sect('toc'))

first_el = body[0]
for el in front:
    first_el.addprevious(el)


# ------------------------------------------------------------- schema-order fix-up (Word is strict about child order)
PPR = ['pStyle','keepNext','keepLines','pageBreakBefore','framePr','widowControl','numPr','suppressLineNumbers','pBdr','shd','tabs',
       'suppressAutoHyphens','kinsoku','wordWrap','overflowPunct','topLinePunct','autoSpaceDE','autoSpaceDN','bidi','adjustRightInd',
       'snapToGrid','spacing','ind','contextualSpacing','mirrorIndents','suppressOverlap','jc','textDirection','textAlignment',
       'textboxTightWrap','outlineLvl','divId','cnfStyle','rPr','sectPr','pPrChange']
RPR = ['rStyle','rFonts','b','bCs','i','iCs','caps','smallCaps','strike','dstrike','outline','shadow','emboss','imprint','noProof',
       'snapToGrid','vanish','webHidden','color','spacing','w','kern','position','sz','szCs','highlight','u','effect','bdr','shd',
       'fitText','vertAlign','rtl','cs','em','lang','eastAsianLayout','specVanish','oMath']
TCPR = ['cnfStyle','tcW','gridSpan','hMerge','vMerge','tcBorders','shd','noWrap','tcMar','textDirection','tcFitText','vAlign','hideMark']
STYLE = ['name','aliases','basedOn','next','link','autoRedefine','hidden','uiPriority','semiHidden','unhideWhenUsed','qFormat',
         'locked','personal','personalCompose','personalReply','rsid','pPr','rPr','tblPr','trPr','tcPr','tblStylePr']
SETTINGS = ['writeProtection','view','zoom','removePersonalInformation','removeDateAndTime','doNotDisplayPageBoundaries','displayBackgroundShape',
            'printPostScriptOverText','printFractionalCharacterWidth','printFormsData','embedTrueTypeFonts','embedSystemFonts','saveSubsetFonts',
            'saveFormsData','mirrorMargins','alignBordersAndEdges','bordersDoNotSurroundHeader','bordersDoNotSurroundFooter','gutterAtTop',
            'hideSpellingErrors','hideGrammaticalErrors','activeWritingStyle','proofState','formsDesign','attachedTemplate','linkStyles',
            'stylePaneFormatFilter','stylePaneSortMethod','documentType','mailMerge','revisionView','trackRevisions','doNotTrackMoves',
            'doNotTrackFormatting','documentProtection','autoFormatOverride','styleLockTheme','styleLockQFSet','defaultTabStop',
            'autoHyphenation','consecutiveHyphenLimit','hyphenationZone','doNotHyphenateCaps','showEnvelope','summaryLength','clickAndTypeStyle',
            'defaultTableStyle','evenAndOddHeaders','bookFoldRevPrinting','bookFoldPrinting','bookFoldPrintingSheets','drawingGridHorizontalSpacing',
            'drawingGridVerticalSpacing','displayHorizontalDrawingGridEvery','displayVerticalDrawingGridEvery','doNotUseMarginsForDrawingGridOrigin',
            'drawingGridHorizontalOrigin','drawingGridVerticalOrigin','doNotShadeFormData','noPunctuationKerning','characterSpacingControl',
            'printTwoOnOne','strictFirstAndLastChars','noLineBreaksAfter','noLineBreaksBefore','savePreviewPicture','doNotValidateAgainstSchema',
            'saveInvalidXml','ignoreMixedContent','alwaysShowPlaceholderText','doNotDemarcateInvalidXml','saveXmlDataOnly','useXSLTWhenSaving',
            'saveThroughXslt','showXMLTags','alwaysMergeEmptyNamespace','updateFields','hdrShapeDefaults','footnotePr','endnotePr','compat',
            'docVars','rsids','mathPr','attachedSchema','themeFontLang','clrSchemeMapping','doNotIncludeSubdocsInStats','doNotAutoCompressPictures',
            'forceUpgrade','captions','readModeInkLockDown','smartTagType','schemaLibrary','shapeDefaults','doNotEmbedSmartTags','decimalSymbol','listSeparator']
ORDERS = {'pPr': PPR, 'rPr': RPR, 'tcPr': TCPR, 'style': STYLE}

def reorder(root):
    n = 0
    for tag, order in ORDERS.items():
        for el in root.iter(q('w:' + tag)):
            kids = list(el)
            key = lambda e: order.index(e.tag.split('}')[1]) if e.tag.split('}')[1] in order else len(order)
            srt = sorted(kids, key=key)          # stable
            if srt != kids:
                for k in kids: el.remove(k)
                for k in srt: el.append(k)
                n += 1
    return n

fixed = reorder(doc.element) + reorder(doc.styles.element)
# stray text inside property blocks (stock pandoc template quirk)
for r in doc.styles.element.iter(q('w:rPr')):
    r.text = None
    for c in r: c.tail = None
# settings child order
_se = doc.settings.element
_kids = list(_se)
_srt = sorted(_kids, key=lambda e: SETTINGS.index(e.tag.split('}')[1]) if e.tag.split('}')[1] in SETTINGS else len(SETTINGS))
if _srt != _kids:
    for k in _kids: _se.remove(k)
    for k in _srt: _se.append(k)
seen = set()
for sct in doc.sections:
    for part in (sct.header, sct.footer):
        el = part._element
        if id(el) not in seen:
            seen.add(id(el)); fixed += reorder(el)
for pm in doc.element.iter(q('w:pgMar')):
    if pm.get(q('w:gutter')) is None: pm.set(q('w:gutter'), '0')
try:
    numel = doc.part.numbering_part.element
    for tag in ('w:nsid', 'w:tmpl'):
        for e in numel.iter(q(tag)):
            v = e.get(q('w:val'))
            if v and len(v) != 8: e.set(q('w:val'), v.upper().rjust(8, '0')[-8:])
except Exception as ex:
    print('numbering fix skipped:', ex)
st_el = doc.settings.element
z = st_el.find(q('w:zoom'))
if z is not None:
    st_el.remove(z)
    pos = 0
    for i, ch in enumerate(st_el):
        if ch.tag in (q('w:writeProtection'), q('w:view')): pos = i + 1
    st_el.insert(pos, z)
# document language (WCAG 3.1.1)
_dd = doc.styles.element.find(q('w:docDefaults'))
if _dd is not None:
    _rp = _dd.find(q('w:rPrDefault') + '/' + q('w:rPr'))
    for e in _rp.findall(q('w:lang')): _rp.remove(e)
    _lang = OxmlElement('w:lang'); _lang.set(q('w:val'), 'en-US'); _lang.set(q('w:eastAsia'), 'en-US'); _lang.set(q('w:bidi'), 'ar-SA')
    _rp.append(_lang); reorder(doc.styles.element)
for dp in doc.element.iter('{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr'):
    if not (dp.get('descr') or '').strip():
        dp.set('descr', dp.get('title') or 'Image')
print('reordered property blocks:', fixed)

# ------------------------------------------------------------- metadata
doc.core_properties.title = COLLEGE + ' \u2013 ' + YEARS + ' Catalog & Student Handbook'
doc.core_properties.author = COLLEGE
doc.core_properties.subject = 'College Catalog'
doc.save(OUT)
print('saved', OUT, '| restyled headings:', n_restyled, '| tables:', len(tables), '| toc entries:', len(toc))
