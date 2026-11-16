(function () {
  var panels = Array.prototype.slice.call(document.querySelectorAll('[role="tabpanel"]'));
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.tab[data-tab]'));
  var first = panels.length ? panels[0].id.replace(/^p-/, '') : '';

  function show(name, scroll) {
    var panel = document.getElementById('p-' + name);
    if (!panel) { name = first; panel = document.getElementById('p-' + name); }
    if (!panel) return;
    panels.forEach(function (p) { p.hidden = p !== panel; });
    tabs.forEach(function (t) {
      var on = t.getAttribute('data-tab') === name;
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      if (on) {
        var row = t.parentElement;
        var l = t.offsetLeft - row.offsetLeft;
        if (l < row.scrollLeft || l + t.offsetWidth > row.scrollLeft + row.clientWidth) row.scrollLeft = Math.max(0, l - 16);
      }
    });
    if (scroll) {
      var bar = document.querySelector('.tabbar');
      var top = panel.getBoundingClientRect().top + window.scrollY - (bar ? bar.offsetHeight : 0);
      if (window.scrollY > top) window.scrollTo(0, top);
    }
  }
  window.addEventListener('hashchange', function () { show(location.hash.slice(1), true); });
  show(location.hash.slice(1), false);

  /* Download PDF: branded or unbranded, via the browser's Save as PDF */
  var btn = document.querySelector('.pdf-btn');
  var menu = document.querySelector('.pdf-menu');
  var baseTitle = document.title;
  function closeMenu() { if (btn) { btn.setAttribute('aria-expanded', 'false'); menu.hidden = true; } }
  if (btn) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var open = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', open ? 'false' : 'true');
      menu.hidden = open;
      if (!open) menu.querySelector('.pdf-opt').focus();
    });
    document.addEventListener('click', function (e) { if (!e.target.closest('.pdf')) closeMenu(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeMenu(); });
    Array.prototype.forEach.call(menu.querySelectorAll('.pdf-opt'), function (o) {
      o.addEventListener('click', function () {
        var unbranded = o.getAttribute('data-brand') === 'unbranded';
        closeMenu();
        document.body.classList.toggle('unbranded', unbranded);
        // The browser suggests the page title as the PDF file name
        document.title = document.body.getAttribute('data-file-title') || baseTitle;
        setTimeout(function () { window.print(); }, 30);
      });
    });
    window.addEventListener('afterprint', function () {
      document.body.classList.toggle('unbranded', document.body.getAttribute('data-default-brand') === 'none');
      document.title = baseTitle;
    });
  }
})();
