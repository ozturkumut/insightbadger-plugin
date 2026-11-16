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
})();
