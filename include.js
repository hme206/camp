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

  // Filter-style search: matches typed text against each chapter's
  // title and its subsection titles (this naturally includes program
  // names nested inside the Program Requirements pathway tree too,
  // since querySelectorAll("a") reaches every link at any depth under
  // .toc-sub). Chapters with no match are hidden; chapters whose only
  // match is a subsection get their dropdown auto-expanded so the
  // match is visible — and if that match is itself nested inside the
  // collapsed pathway tree, that inner toggle gets auto-expanded too.
  //
  // NOTE for later: this searches only the TOC's own text (chapter
  // and subsection titles), not full page content. To upgrade to
  // full-text search across all catalog pages, replace the data
  // this function reads (currently pulled live from the DOM) with
  // a generated content index, and keep the same filtering/display
  // logic below.
  function initSearch(container) {
    const input = container.querySelector("#toc-search-input");
    const status = container.querySelector("#toc-search-status");
    const noResults = container.querySelector("#toc-no-results");
    const items = container.querySelectorAll(".toc-item");
    if (!input) return;

    input.addEventListener("input", () => {
      const query = input.value.trim().toLowerCase();
      let visibleCount = 0;

      items.forEach(item => {
        const chapterLink = item.querySelector(".toc-link");
        const chapterText = chapterLink.textContent.toLowerCase();
        const submenu = item.querySelector(".toc-sub");
        const toggle = item.querySelector(".toc-toggle");
        const subLinks = submenu ? Array.from(submenu.querySelectorAll("a")) : [];

        const chapterMatches = query === "" || chapterText.includes(query);
        const matchingSubLinks = query === ""
          ? []
          : subLinks.filter(a => a.textContent.toLowerCase().includes(query));

        const itemMatches = chapterMatches || matchingSubLinks.length > 0;
        item.hidden = !itemMatches;

        if (itemMatches) visibleCount++;

        if (submenu && toggle) {
          if (query !== "" && matchingSubLinks.length > 0 && !chapterMatches) {
            // Only subsections matched — expand so the match is visible
            submenu.hidden = false;
            toggle.setAttribute("aria-expanded", "true");
          } else if (query === "") {
            // Search cleared — restore whatever the user had open before
            // searching, rather than force-collapsing everything
            const expandedIds = getExpandedIds();
            const wasExpanded = expandedIds.has(toggle.getAttribute("aria-controls"));
            submenu.hidden = !wasExpanded;
            toggle.setAttribute("aria-expanded", String(wasExpanded));
          }
        }

        // Nested pathway tree (Program Requirements): if any matching
        // link lives inside a .toc-subtoggle's target, expand that
        // inner toggle too so the match is actually visible, not just
        // present-but-hidden inside a collapsed .toc-tree.
        if (submenu) {
          submenu.querySelectorAll(".toc-subtoggle").forEach(subToggle => {
            const subTargetId = subToggle.getAttribute("aria-controls");
            const subTarget = document.getElementById(subTargetId);
            if (!subTarget) return;

            if (query === "") {
              const expandedIds = getExpandedIds();
              const wasExpanded = expandedIds.has(subTargetId);
              subTarget.hidden = !wasExpanded;
              subToggle.setAttribute("aria-expanded", String(wasExpanded));
              return;
            }

            const nestedMatch = Array.from(subTarget.querySelectorAll("a"))
              .some(a => a.textContent.toLowerCase().includes(query));

            if (nestedMatch) {
              subTarget.hidden = false;
              subToggle.setAttribute("aria-expanded", "true");
            }
          });
        }
      });

      if (noResults) noResults.hidden = visibleCount !== 0;

      if (status) {
        status.textContent = query === ""
          ? ""
          : `${visibleCount} chapter${visibleCount === 1 ? "" : "s"} found`;
      }
    });
  }

});
