(function () {
  /* Tabs switch in place. They never follow a link: inside app previews
     (sandboxed frames) a '#section' link replaces the whole page with a blank one. */
  var panels = Array.prototype.slice.call(document.querySelectorAll('[role="tabpanel"]'));
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.tab[data-tab]'));
  var first = panels.length ? panels[0].id.replace(/^p-/, '') : '';

  function readHash() {
    try { return (window.location.hash || '').slice(1); } catch (e) { return ''; }
  }
  function writeHash(name) {
    // Lets a link open a given tab. Some previews forbid it; the tabs work regardless.
    try { if (window.history && history.replaceState) history.replaceState(null, '', '#' + name); } catch (e) {}
  }

  function show(name, opts) {
    opts = opts || {};
    var panel = document.getElementById('p-' + name);
    if (!panel) { name = first; panel = document.getElementById('p-' + name); }
    if (!panel) return;
    panels.forEach(function (p) { p.classList.toggle('active', p === panel); });
    tabs.forEach(function (t) {
      var on = t.getAttribute('data-tab') === name;
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      t.tabIndex = on ? 0 : -1;
      if (on) {
        var row = t.parentElement;
        var l = t.offsetLeft - row.offsetLeft;
        if (l < row.scrollLeft || l + t.offsetWidth > row.scrollLeft + row.clientWidth) row.scrollLeft = Math.max(0, l - 16);
      }
    });
    if (opts.scroll) {
      var bar = document.querySelector('.tabbar');
      var top = panel.getBoundingClientRect().top + window.pageYOffset - (bar ? bar.offsetHeight : 0);
      if (window.pageYOffset > top) window.scrollTo(0, top);
    }
    if (opts.record) writeHash(name);
  }

  document.addEventListener('click', function (e) {
    var el = e.target.closest ? e.target.closest('[data-tab], [data-go]') : null;
    if (!el) return;
    e.preventDefault();
    show(el.getAttribute('data-tab') || el.getAttribute('data-go'), { scroll: true, record: true });
  });
  document.addEventListener('keydown', function (e) {
    var el = e.target;
    if (el && el.getAttribute && el.getAttribute('data-go') && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      show(el.getAttribute('data-go'), { scroll: true, record: true });
    }
    if (el && el.getAttribute && el.getAttribute('role') === 'tab' && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) {
      var i = tabs.indexOf(el) + (e.key === 'ArrowRight' ? 1 : -1);
      var next = tabs[(i + tabs.length) % tabs.length];
      next.focus();
      show(next.getAttribute('data-tab'), { record: true });
    }
  });
  window.addEventListener('hashchange', function () { show(readHash(), { scroll: true }); });
  show(readHash(), {});

  /* Download PDF: branded or unbranded, via the browser's print window. */
  var btn = document.querySelector('.pdf-btn');
  var menu = document.querySelector('.pdf-menu');
  var baseTitle = document.title;
  var printed = false;
  window.addEventListener('beforeprint', function () { printed = true; });
  window.addEventListener('afterprint', function () {
    document.body.classList.toggle('unbranded', document.body.getAttribute('data-default-brand') === 'none');
    document.title = baseTitle;
  });

  function notice() {
    if (document.querySelector('.notice-backdrop')) return;
    var wrap = document.createElement('div');
    wrap.className = 'notice-backdrop';
    wrap.innerHTML = '<div class="notice" role="dialog" aria-modal="true" aria-labelledby="notice-t">' +
      '<h2 id="notice-t">This viewer can’t print</h2>' +
      '<p>The report is open inside a preview that blocks the print window, so the PDF can’t be saved from here.</p>' +
      '<p>Open the report file in Chrome, Edge, Safari or Firefox and use <b>Download PDF</b> there, or ask Claude: ' +
      '<code>save this report as a PDF</code> (add “unbranded” if you want).</p>' +
      '<button type="button">Got it</button></div>';
    document.body.appendChild(wrap);
    var ok = wrap.querySelector('button');
    var close = function () { wrap.parentNode && wrap.parentNode.removeChild(wrap); if (btn) btn.focus(); };
    ok.addEventListener('click', close);
    wrap.addEventListener('click', function (e) { if (e.target === wrap) close(); });
    document.addEventListener('keydown', function esc(e) { if (e.key === 'Escape') { close(); document.removeEventListener('keydown', esc); } });
    ok.focus();
  }

  function closeMenu() { if (btn) { btn.setAttribute('aria-expanded', 'false'); menu.hidden = true; } }
  if (btn && menu) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var open = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', open ? 'false' : 'true');
      menu.hidden = open;
      if (!open) menu.querySelector('.pdf-opt').focus();
    });
    document.addEventListener('click', function (e) { if (!e.target.closest || !e.target.closest('.pdf')) closeMenu(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeMenu(); });
    Array.prototype.forEach.call(menu.querySelectorAll('.pdf-opt'), function (o) {
      o.addEventListener('click', function (e) {
        e.stopPropagation();
        var unbranded = o.getAttribute('data-brand') === 'unbranded';
        closeMenu();
        document.body.classList.toggle('unbranded', unbranded);
        document.title = document.body.getAttribute('data-file-title') || baseTitle;
        printed = false;
        setTimeout(function () {
          try { window.print(); } catch (err) { printed = false; }
          // A real print window fires 'beforeprint' (and blocks until closed).
          // If nothing happened, the viewer blocked it: explain instead of failing silently.
          setTimeout(function () { if (!printed) { document.title = baseTitle; notice(); } }, 400);
        }, 30);
      });
    });
  }
})();
