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

  // Wires up each chapter's dropdown button: toggles aria-expanded
  // and the `hidden` attribute on its subsection list. Using `hidden`
  // (rather than height/animation tricks) means collapsed subsections
  // are fully removed from the accessibility tree and tab order.
  function initToggles(container) {
    container.querySelectorAll(".toc-toggle").forEach(button => {
      button.addEventListener("click", () => {
        const submenu = document.getElementById(button.getAttribute("aria-controls"));
        const expanded = button.getAttribute("aria-expanded") === "true";
        button.setAttribute("aria-expanded", String(!expanded));
        if (submenu) submenu.hidden = expanded;
      });
    });
  }

  // Filter-style search: matches typed text against each chapter's
  // title and its subsection titles. Chapters with no match are
  // hidden; chapters whose only match is a subsection get their
  // dropdown auto-expanded so the match is visible.
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
            // Search cleared — collapse back to the default state
            submenu.hidden = true;
            toggle.setAttribute("aria-expanded", "false");
          }
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
