/* Optional enhancement: shows when the Word document was last rebuilt, its size and page count.
   The button works without this script; if the info file can't be read, the static text stays. */
(function () {
  var meta = document.getElementById('catalog-download-meta');
  if (!meta || !window.fetch) { return; }
  fetch('downloads/catalog-info.json', { cache: 'no-store' })
    .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
    .then(function (info) {
      var d = new Date(info.built + 'T12:00:00');
      var when = isNaN(d.getTime()) ? info.built
        : d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
      meta.textContent = 'Word document (.docx), ' + info.size_mb + ' MB, ' + info.pages +
        ' pages. Updated ' + when + '.';
    })
    .catch(function () { /* keep the default text */ });
})();
