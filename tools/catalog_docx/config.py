"""Shared settings for the catalog Word-document build.

Everything can be overridden with environment variables (see build.sh and the workflow).
"""
import glob, os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.environ.get('CATALOG_SRC', os.path.abspath(os.path.join(HERE, '..', '..')))      # repo root
BUILD = os.environ.get('CATALOG_BUILD', os.path.join(HERE, '_work'))                       # scratch folder
SITE = os.environ.get('CATALOG_SITE', 'https://hme206.github.io/camp/')                    # live site (for links to pages outside the TOC)
YEARS = os.environ.get('CATALOG_YEARS', '2026\u20132027')                                  # shown in header / title / alt text
COLLEGE = os.environ.get('CATALOG_COLLEGE', 'Paul D. Camp Community College')
TOC_FILE = os.environ.get('CATALOG_TOC', 'sidetoc.html')                                   # page that defines the order
COVER = os.environ.get('CATALOG_COVER', os.path.join(SRC, 'images', 'catalogfrontpage.png'))
COVER_ALT = os.environ.get('CATALOG_COVER_ALT', f'Cover of the {COLLEGE} {YEARS} Catalog and Student Handbook. '
    'A large group of graduates in green caps and gowns holds diplomas beneath the Camp Community College logo, '
    'the tagline Grow Your Future, and the slogan Where Small is BIG.')
os.makedirs(BUILD, exist_ok=True)


def find_font(style):
    """Locate Liberation Sans (metric-compatible with Arial) for measuring column widths."""
    for pat in (f'/usr/share/fonts/**/LiberationSans-{style}.ttf',):
        hits = glob.glob(pat, recursive=True)
        if hits:
            return hits[0]
    raise SystemExit('Liberation Sans font not found. Install it (Ubuntu: sudo apt-get install fonts-liberation).')
