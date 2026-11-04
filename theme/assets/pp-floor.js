/* pp-floor.js: the floor plan (Tables & layout, and each event's room set-up). Drawing + dragging only; the
   Components/FloorPlan Python component wraps it.
   PP.floor(el, plan, handler)
     plan = { tables: [{id, name, seats, shape, x, y, active}], groups: [{tables: [ids], tag}],   (joined / pushed together)
              selected: [ids], out: [ids] (taken out: dashed), draggable: bool, empty: "text when there are no tables" }
     handler(kind, payload): "pick" {id} (a tap or Enter) | "move" {id, x, y} (a drag ended; x/y in % of the floor) */
(function () {
  'use strict';
  var PP = window.PP;

  function size(t) {
    if (t.shape === 'round') { var d = 44 + t.seats * 5; return [d, d]; }
    if (t.shape === 'long') return [60 + t.seats * 11, 48];
    var s = 44 + t.seats * 4; return [s, s];
  }
  function chairs(t, w, h) {
    var out = '', n = Math.min(t.seats, 24), i;
    if (t.shape === 'round') {
      for (i = 0; i < n; i++) {
        var a = (i / n) * Math.PI * 2 - Math.PI / 2, r = w / 2 + 9;
        out += '<span class="chair" style="left:' + (w / 2 + 9 + Math.cos(a) * r) + 'px;top:' + (h / 2 + 9 + Math.sin(a) * r) + 'px"></span>';
      }
      return out;
    }
    var top = Math.ceil(n / 2), bot = n - top;
    if (t.shape === 'square' && n <= 2) { top = 1; bot = n - 1; }
    for (i = 0; i < top; i++) out += '<span class="chair" style="left:' + (9 + w * (i + 1) / (top + 1)) + 'px;top:2px"></span>';
    for (i = 0; i < bot; i++) out += '<span class="chair" style="left:' + (9 + w * (i + 1) / (bot + 1)) + 'px;top:' + (h + 16) + 'px"></span>';
    return out;
  }

  function html(P) {
    var esc = PP.esc, by = {}, inGroup = {}, tagged = {};
    P.tables.forEach(function (t) { by[t.id] = t; });
    var lines = (P.groups || []).map(function (g) {
      var ts = g.tables.map(function (id) { return by[id]; }).filter(Boolean), seg = '';
      ts.forEach(function (t) { inGroup[t.id] = g; });
      for (var i = 1; i < ts.length; i++) seg += '<line x1="' + ts[i - 1].x + '%" y1="' + ts[i - 1].y + '%" x2="' + ts[i].x + '%" y2="' + ts[i].y + '%"/>';
      return seg;
    }).join('');
    var sel = P.selected || [], out = P.out || [];
    return '<div class="pp-floor' + (P.draggable ? ' can-drag' : '') + '"><svg class="links">' + lines + '</svg>' +
      (P.tables.length ? '' : '<div class="hint-empty">' + esc(P.empty || 'Add your first table to start the floor plan.') + '</div>') +
      P.tables.map(function (t) {
        var sz = size(t), g = inGroup[t.id];
        var cls = 'tb ' + t.shape + (g ? ' joined' : '') + (t.active === false || out.indexOf(t.id) >= 0 ? ' off' : '') + (sel.indexOf(t.id) >= 0 ? ' sel' : '');
        var tag = '', gk = g ? g.tables.join() : '';
        if (g && g.tag && !tagged[gk]) { tagged[gk] = 1; tag = '<span class="jtag">' + esc(g.tag) + '</span>'; }
        return '<div class="' + cls + '" data-t="' + esc(t.id) + '" tabindex="0" role="button" aria-label="' + esc(t.name + ', ' + t.seats + ' seats' + (g ? ', joined' : '')) +
          '" style="left:' + t.x + '%;top:' + t.y + '%;width:' + (sz[0] + 18) + 'px;height:' + (sz[1] + 18) + 'px">' + chairs(t, sz[0], sz[1]) + tag +
          '<div class="top" style="width:' + sz[0] + 'px;height:' + sz[1] + 'px"><div><b>' + esc(t.name) + '</b><span>' + t.seats + '</span></div></div></div>';
      }).join('') + '</div>';
  }

  // Table sizes are in pixels at a 760px-wide floor; smaller floors (phones) shrink them to match.
  function scale(el) {
    var fl = el.querySelector('.pp-floor');
    if (fl) fl.style.setProperty('--s', Math.max(0.6, Math.min(1, fl.clientWidth / 760)).toFixed(3));
  }

  PP.floor = function (el, plan, handler) {
    el.innerHTML = html(plan);
    scale(el);
    setTimeout(function () { scale(el); }, 0);
    el.__ppFloor = { plan: plan, handler: handler };
    if (el.__ppWired) return;
    el.__ppWired = true;
    var drag = null;
    window.addEventListener('resize', function () { scale(el); });
    el.addEventListener('pointerdown', function (e) {
      var tb = e.target.closest('.tb');
      if (!tb || e.button > 0) return;
      drag = { el: tb, id: tb.dataset.t, x0: e.clientX, y0: e.clientY, fl: el.querySelector('.pp-floor').getBoundingClientRect(), moved: false };
      try { tb.setPointerCapture(e.pointerId); } catch (x) {}
    });
    el.addEventListener('pointermove', function (e) {
      if (!drag || !el.__ppFloor.plan.draggable) return;
      if (!drag.moved && Math.abs(e.clientX - drag.x0) + Math.abs(e.clientY - drag.y0) < 4) return;
      drag.moved = true;
      drag.el.classList.add('dragging');
      var x = Math.max(3, Math.min(97, (e.clientX - drag.fl.left) / drag.fl.width * 100));
      var y = Math.max(5, Math.min(95, (e.clientY - drag.fl.top) / drag.fl.height * 100));
      drag.x = Math.round(x * 2) / 2; drag.y = Math.round(y * 2) / 2;
      drag.el.style.left = drag.x + '%'; drag.el.style.top = drag.y + '%';
    });
    el.addEventListener('pointerup', function () {
      if (!drag) return;
      var d = drag; drag = null;
      d.el.classList.remove('dragging');
      var h = el.__ppFloor.handler;
      if (!d.moved) h('pick', { id: d.id });
      else h('move', { id: d.id, x: d.x, y: d.y });
    });
    el.addEventListener('pointercancel', function () { if (drag) { drag.el.classList.remove('dragging'); drag = null; } });
    el.addEventListener('keydown', function (e) {
      var tb = e.target.closest && e.target.closest('.tb');
      if (tb && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); el.__ppFloor.handler('pick', { id: tb.dataset.t }); }
    });
  };
})();
