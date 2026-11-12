# Catalog download button: setup (about 10 minutes)

**What you get:** a "Download the Catalog" button on `catalog.html`. Anyone who clicks it downloads the
current, accessible Word version of the whole catalog. GitHub rebuilds the Word file automatically every
time you change the catalog pages, so the button is never out of date.

## Install

1. **Copy the files into your repo.** Unzip this package into the repo's top folder (the one that holds
   `catalog.html` and `sidetoc.html`). It adds:
   - `.github/workflows/build-catalog-docx.yml`  (the automatic build)
   - `tools/catalog_docx/`  (the conversion scripts)
   - `downloads/`  (the built Word file; included so the button works right away)
   - `catalog-download.css` and `catalog-download.js`  (button style and optional "last updated" text)
   - `catalog.html`  (replaces yours; the only changes are the download panel and a text description for the cover image, which had an empty description)

   If you have edited `catalog.html` since I copied it, don't overwrite it. Copy the
   `<section class="catalog-download">...</section>` block, the extra `<link>` line in `<head>`
   and the extra `<script>` line at the bottom into your version.
2. **Commit and push** to your main branch.
3. **Allow the build to save its file.** On GitHub: *Settings > Actions > General > Workflow permissions >*
   **Read and write permissions > Save**.
4. **Run the first build.** *Actions* tab > **Build catalog Word document** > **Run workflow**.
   It takes about 5 to 10 minutes. When it shows a green check, a new commit appears with the updated file.
5. **Test it.** Open `https://hme206.github.io/camp/catalog.html` and click the button.
   Direct link to the file: `https://hme206.github.io/camp/downloads/Camp_College_Catalog.docx`

## Day to day

Edit pages as usual and push. The build runs by itself, and the file and the "Updated ..." date on the
button refresh a few minutes later. The page order comes from `sidetoc.html`, so a page you add there is
included automatically.

The build also checks accessibility (no merged cells, header rows on every table, heading order, image
descriptions, contrast). If a change would break one of those, the build fails and the previous file stays
online. You will see a red X in the Actions tab with the reason.

## Each new year

- In `.github/workflows/build-catalog-docx.yml`, change `CATALOG_YEARS`.
- Replace `images/catalogfrontpage.png`. Optionally add `CATALOG_COVER_ALT` under `env:` to describe the
  new cover photo for screen readers.
- Update the years in the panel text on `catalog.html`.

## Troubleshooting

- **Build fails on "push" with a permission error:** repeat step 3.
- **Button gives "404 Not Found":** the first build has not finished, or `downloads/` was not committed.
- **File does not change after edits:** edits must be pushed to the main branch; check the Actions tab for a run.
- **Page numbers in the Word table of contents look off in Word:** right-click the table of contents and
  choose *Update Field*.

## Good to know

- Each rebuild adds about 2 MB to the repo's history. That is fine for years of updates.
- The site-wide focus colour in `styles.css` (`--focus: #ff6b00`) is 2.9:1 against white, just under the
  3:1 that WCAG 2.1 expects for focus indicators. The new button uses its own stronger focus ring. If you
  want the whole site to pass, a darker orange such as `#d45500` does.
- To build on your own computer instead, install Python 3.12, pandoc 3.1.x, LibreOffice, poppler-utils and
  fonts-liberation, run `pip install -r tools/catalog_docx/requirements.txt`, then
  `bash tools/catalog_docx/build.sh`.
