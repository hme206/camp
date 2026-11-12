#!/usr/bin/env bash
# Builds downloads/Camp_College_Catalog.docx from the pages listed in sidetoc.html.
# Needs: python3 (+ requirements.txt), pandoc 3.1.x, LibreOffice (soffice), poppler-utils (pdftotext), fonts-liberation.
set -euo pipefail
cd "$(dirname "$0")"
export CATALOG_SRC="${CATALOG_SRC:-$(cd ../.. && pwd)}"
export CATALOG_BUILD="${CATALOG_BUILD:-$PWD/_work}"
SOFFICE="${SOFFICE:-soffice}"
OUTFILE="${OUTFILE:-$CATALOG_SRC/downloads/Camp_College_Catalog.docx}"
mkdir -p "$CATALOG_BUILD" "$(dirname "$OUTFILE")"
cd "$CATALOG_BUILD" && rm -f *.docx *.pdf *.txt pages*.json structure.json combined.html && cd - >/dev/null

echo "== 1/6 merge pages from the TOC"
python3 build_html.py
echo "== 2/6 Word template"
pandoc -o "$CATALOG_BUILD/ref0.docx" --print-default-data-file reference.docx
python3 make_ref.py
echo "== 3/6 convert"
pandoc -f html -t docx --reference-doc="$CATALOG_BUILD/reference.docx" --resource-path="$CATALOG_SRC" \
       "$CATALOG_BUILD/combined.html" -o "$CATALOG_BUILD/body.docx"
echo "== 4/6 first pass (cover, TOC, tables) + layout render to find page numbers"
python3 postprocess.py "$CATALOG_BUILD/pass1.docx"
$SOFFICE --headless --convert-to pdf --outdir "$CATALOG_BUILD" "$CATALOG_BUILD/pass1.docx" >/dev/null 2>&1
pdftotext "$CATALOG_BUILD/pass1.pdf" "$CATALOG_BUILD/pass1.txt"
python3 pages.py
echo "== 5/6 final pass with page numbers filled in"
python3 postprocess.py "$CATALOG_BUILD/pass2.docx" "$CATALOG_BUILD/pages.json"
$SOFFICE --headless --convert-to pdf --outdir "$CATALOG_BUILD" "$CATALOG_BUILD/pass2.docx" >/dev/null 2>&1
echo "== 6/6 publish file + info"
cp "$CATALOG_BUILD/pass2.docx" "$OUTFILE"
PAGES=$(pdfinfo "$CATALOG_BUILD/pass2.pdf" | awk '/^Pages:/{print $2}')
python3 - "$OUTFILE" "$PAGES" <<'PY'
import json, os, sys, datetime
f, pages = sys.argv[1], int(sys.argv[2])
info = dict(built=datetime.date.today().isoformat(), pages=pages, size_mb=round(os.path.getsize(f) / 1e6, 1))
json.dump(info, open(os.path.join(os.path.dirname(f), 'catalog-info.json'), 'w'))
print('built', f, info)
PY
