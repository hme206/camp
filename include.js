/* ══════════════════════════════════════════════════════════
   include.js — Paul D. Camp Community College
   Fetches shared HTML snippets (toptoc.html, sidetoc.html, etc.)
   and injects them into their placeholder <div id="..."> elements.
   Also wires up the catalog sidebar's dropdown toggles and
   filter-style search once sidetoc.html has loaded.

   Usage: on any page, add empty placeholder divs, e.g.:
     <div id="toptoc"></div>
     <div id="sidetoc"></div>
   then include this script before </body>:
     <script src="include.js"></script>
   ══════════════════════════════════════════════════════════ */

document.addEventListener("DOMContentLoaded", () => {

  // Map of placeholder div IDs -> the HTML file to load into them.
  // Add more entries here as you create more shared snippets.
  const includes = {
    "toptoc":  "toptoc.html",
    "sidetoc": "sidetoc.html"
  };

  Object.entries(includes).forEach(([elementId, file]) => {
    const target = document.getElementById(elementId);
    if (!target) return; // page doesn't use this snippet, skip it

    fetch(file)
      .then(response => {
        if (!response.ok) {
          throw new Error(`Failed to load ${file}: ${response.status}`);
        }
        return response.text();
      })
      .then(html => {
        target.innerHTML = html;

        if (elementId === "toptoc") {
          highlightCurrentPage(target, "a");
        }

        if (elementId === "sidetoc") {
          highlightCurrentPage(target, ".toc-link, .toc-sub a");
          initToggles(target);
          initSearch(target);
        }
      })
      .catch(err => {
        console.error(err);
        target.innerHTML = `<p style="color:red;">Could not load ${file}</p>`;
      });
  });

  // Marks the link matching the current page with aria-current="page",
  // the accessible (and CSS-hookable) way to indicate "you are here" —
  // screen readers announce it, and cstyles.css styles it visually.
  function highlightCurrentPage(container, selector) {
    const currentPage = window.location.pathname.split("/").pop();
    container.querySelectorAll(selector).forEach(link => {
      const linkPage = link.getAttribute("href").split("#")[0];
      if (linkPage === currentPage) {
        link.setAttribute("aria-current", "page");
      }
    });
  }

  // ──────────────────────────────────────────────────────────
  // Expanded-section persistence
  //
  // sidetoc.html is fetched fresh on every page load, so without
  // this, expanding a chapter (or the Program Requirements pathway
  // tree), clicking a link inside it, and landing on a new page
  // would always show every toggle back in its collapsed default
  // state. This remembers which toggles the user has opened, keyed
  // by each toggle's aria-controls id, and restores that state the
  // next time sidetoc.html loads — on any page.
  //
  // Toggles remain fully collapsible by clicking them again; this
  // only affects what state they start in on a fresh page load.
  // ──────────────────────────────────────────────────────────
  const TOC_STORAGE_KEY = "campTocExpandedIds";

  function getExpandedIds() {
    try {
      const raw = localStorage.getItem(TOC_STORAGE_KEY);
      return raw ? new Set(JSON.parse(raw)) : new Set();
    } catch (e) {
      return new Set();
    }
  }

  function saveExpandedIds(idSet) {
    try {
      localStorage.setItem(TOC_STORAGE_KEY, JSON.stringify(Array.from(idSet)));
    } catch (e) {
      // localStorage unavailable (private browsing, storage full, etc.) —
      // toggles still work for the current page, they just won't persist
    }
  }

  function rememberExpanded(id, expanded) {
    const ids = getExpandedIds();
    if (expanded) {
      ids.add(id);
    } else {
      ids.delete(id);
    }
    saveExpandedIds(ids);
  }

  // Wires up both toggle levels: .toc-toggle (chapter dropdowns) and
  // .toc-subtoggle (the Program Requirements pathway tree). Both share
  // the same aria-expanded / aria-controls / hidden contract, so one
  // function handles both. Restores each toggle's remembered state on
  // load, then keeps it in sync with localStorage on every click.
  function initToggles(container) {
    const expandedIds = getExpandedIds();

    container.querySelectorAll(".toc-toggle, .toc-subtoggle").forEach(button => {
      const targetId = button.getAttribute("aria-controls");
      const submenu = document.getElementById(targetId);
      if (!submenu) return;

      // Restore remembered state from a previous page
      if (expandedIds.has(targetId)) {
        button.setAttribute("aria-expanded", "true");
        submenu.hidden = false;
      }

      button.addEventListener("click", () => {
        const expanded = button.getAttribute("aria-expanded") === "true";
        const nowExpanded = !expanded;
        button.setAttribute("aria-expanded", String(nowExpanded));
        submenu.hidden = expanded; // expanded was true -> now hide; was false -> now show
        rememberExpanded(targetId, nowExpanded);
      });
    });
  }

  // ──────────────────────────────────────────────────────────
  // Full-site search
  //
  // Every page on the site shares the same template, and every
  // page's URL already appears somewhere in sidetoc.html's own
  // links. So instead of only matching against chapter/subsection
  // link text, this collects every unique URL out of the sidebar,
  // fetches each page in the background, extracts the visible text
  // from its .catalog-content region, and searches THAT — real
  // page content, not just menu labels.
  //
  // The index is built once per browser tab (cached in
  // sessionStorage) so navigating between pages doesn't re-fetch
  // everything each time; it only rebuilds if the cached version
  // looks stale (see INDEX_MAX_AGE_MS) or is missing.
  //
  // While a search is active, results replace the normal chapter
  // tree with a flat list of matching pages + a text snippet.
  // Clearing the search restores the normal collapsed/expanded
  // chapter view exactly as it was.
  // ──────────────────────────────────────────────────────────
  const SEARCH_INDEX_KEY = "campSiteSearchIndex";
  const INDEX_MAX_AGE_MS = 1000 * 60 * 30; // rebuild if older than 30 minutes

  function collectSiteUrls(container) {
    const urls = new Set();
    container.querySelectorAll("a[href]").forEach(a => {
      const href = a.getAttribute("href");
      if (!href || href.startsWith("http") || href.startsWith("mailto:")) return;
      urls.add(href.split("#")[0]);
    });
    return Array.from(urls);
  }

  function loadCachedIndex() {
    try {
      const raw = sessionStorage.getItem(SEARCH_INDEX_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (Date.now() - parsed.builtAt > INDEX_MAX_AGE_MS) return null;
      return parsed.pages;
    } catch (e) {
      return null;
    }
  }

  function saveCachedIndex(pages) {
    try {
      sessionStorage.setItem(SEARCH_INDEX_KEY, JSON.stringify({
        builtAt: Date.now(),
        pages: pages
      }));
    } catch (e) {
      // sessionStorage unavailable — index just won't persist across
      // page loads in this tab; search still works for the current page
    }
  }

  function extractPageText(html) {
    const doc = new DOMParser().parseFromString(html, "text/html");
    const titleEl = doc.querySelector(".catalog-content h1") || doc.querySelector("title");
    const title = titleEl ? titleEl.textContent.trim() : "Untitled page";
    const contentEl = doc.querySelector(".catalog-content");
    const text = contentEl ? contentEl.textContent.replace(/\s+/g, " ").trim() : "";
    return { title, text };
  }

  // Builds the full-site index once, fetching every page in
  // parallel. Returns a Promise resolving to the page array.
  function buildSiteIndex(urls) {
    const fetches = urls.map(url =>
      fetch(url)
        .then(res => (res.ok ? res.text() : null))
        .then(html => {
          if (!html) return null;
          const { title, text } = extractPageText(html);
          return { url, title, text };
        })
        .catch(() => null)
    );

    return Promise.all(fetches).then(results => {
      const pages = results.filter(Boolean);
      saveCachedIndex(pages);
      return pages;
    });
  }

  // Returns a short snippet of `text` centered on the first
  // occurrence of `query`, with the match itself wrapped in <mark>.
  function buildSnippet(text, query) {
    const lower = text.toLowerCase();
    const idx = lower.indexOf(query);
    if (idx === -1) return text.slice(0, 140) + (text.length > 140 ? "…" : "");

    const start = Math.max(0, idx - 60);
    const end = Math.min(text.length, idx + query.length + 60);
    const prefix = start > 0 ? "…" : "";
    const suffix = end < text.length ? "…" : "";
    const before = escapeHtml(text.slice(start, idx));
    const match = escapeHtml(text.slice(idx, idx + query.length));
    const after = escapeHtml(text.slice(idx + query.length, end));

    return `${prefix}${before}<mark>${match}</mark>${after}${suffix}`;
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function initSearch(container) {
    const input = container.querySelector("#toc-search-input");
    const status = container.querySelector("#toc-search-status");
    const noResults = container.querySelector("#toc-no-results");
    const tocList = container.querySelector(".toc-list");
    if (!input) return;

    // Results list, inserted right after the search box's parent
    // banner, hidden until a search is active
    const resultsList = document.createElement("ul");
    resultsList.className = "toc-search-results";
    resultsList.hidden = true;
    tocList.parentNode.insertBefore(resultsList, tocList);

    let siteIndex = loadCachedIndex();
    let indexBuilding = null;

    function ensureIndex() {
      if (siteIndex) return Promise.resolve(siteIndex);
      if (indexBuilding) return indexBuilding;

      const urls = collectSiteUrls(container);
      if (status) status.textContent = "Searching all pages…";

      indexBuilding = buildSiteIndex(urls).then(pages => {
        siteIndex = pages;
        indexBuilding = null;
        return pages;
      });
      return indexBuilding;
    }

    function renderResults(query, pages) {
      const matches = pages.filter(page =>
        page.title.toLowerCase().includes(query) || page.text.toLowerCase().includes(query)
      );

      resultsList.innerHTML = "";
      matches.forEach(page => {
        const li = document.createElement("li");
        li.className = "toc-search-result";
        const snippet = page.text.toLowerCase().includes(query)
          ? buildSnippet(page.text, query)
          : "";
        li.innerHTML = `
          <a href="${page.url}">${escapeHtml(page.title)}</a>
          ${snippet ? `<span class="toc-search-snippet">${snippet}</span>` : ""}
        `;
        resultsList.appendChild(li);
      });

      resultsList.hidden = matches.length === 0;
      tocList.hidden = true;
      if (noResults) noResults.hidden = matches.length !== 0;

      if (status) {
        status.textContent = `${matches.length} page${matches.length === 1 ? "" : "s"} found`;
      }
    }

    function clearSearch() {
      resultsList.hidden = true;
      resultsList.innerHTML = "";
      tocList.hidden = false;
      if (noResults) noResults.hidden = true;
      if (status) status.textContent = "";
    }

    let debounceTimer = null;
    input.addEventListener("input", () => {
      const query = input.value.trim().toLowerCase();

      clearTimeout(debounceTimer);

      if (query === "") {
        clearSearch();
        return;
      }

      debounceTimer = setTimeout(() => {
        ensureIndex().then(pages => renderResults(query, pages));
      }, 200);
    });
  }

});
