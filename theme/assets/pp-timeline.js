/* pp-timeline.js: the Reservations day timeline (one row per table, bookings as blocks, the occupancy curve, closed
   hours shaded, a "now" line). Drawing engine only: Components/Timeline wraps it and turns clicks into Python events.
   PP.timeline(el, day, handler)  day = Portal.get_day(); handler(kind, payload): kind "edit" {id} | "slot" {time, table} */
(function () {
  'use strict';
  var PP = window.PP;
  var HOUR = 96;  // px per hour, before the timeline stretches to the width it has

  function range(D) {
    var lo = null, hi = null;
    D.hours.forEach(function (p) { var a = PP.toMin(p[0]), b = PP.toMin(p[1]); lo = lo == null ? a : Math.min(lo, a); hi = hi == null ? b : Math.max(hi, b); });
    D.reservations.forEach(function (r) {
      if (r.status === 'cancelled' || r.status === 'declined' || r.status === 'no_show') return;
      lo = lo == null ? r.start_min : Math.min(lo, r.start_min); hi = hi == null ? r.start_min + r.duration : Math.max(hi, r.start_min + r.duration);
    });
    if (lo == null) { lo = 12 * 60; hi = 23 * 60; }
    return [Math.floor(lo / 60) * 60, Math.min(1440, Math.ceil(hi / 60) * 60)];
  }

  function html(D) {
    var esc = PP.esc;
    var rg = range(D), lo = rg[0], hi = rg[1], span = hi - lo, hours = span / 60;
    var pos = function (m) { return ((m - lo) / span * 100) + '%'; };
    var w = function (m) { return (m / span * 100) + '%'; };
    var LIVE = { pending: 1, confirmed: 1, seated: 1, done: 1 };
    var live = D.reservations.filter(function (r) { return LIVE[r.status]; });
    var ticks = '';
    for (var h = lo; h < hi; h += 60) ticks += '<span class="tick" style="left:' + pos(h) + '">' + PP.hm(h) + '</span>';
    var shade = '', cur = lo;
    D.hours.map(function (p) { return [PP.toMin(p[0]), PP.toMin(p[1])]; }).forEach(function (p) {
      if (p[0] > cur) shade += '<span class="closed" style="left:' + pos(cur) + ';width:' + w(p[0] - cur) + '"></span>';
      cur = Math.max(cur, p[1]);
    });
    if (cur < hi) shade += '<span class="closed" style="left:' + pos(cur) + ';width:' + w(hi - cur) + '"></span>';
    var thr = D.settings.auto_threshold;
    var occ = (D.curve || []).map(function (c) {
      var m = PP.toMin(c.time);
      return '<span class="col' + (c.pct >= thr ? ' hot' : '') + '" title="' + esc(c.time + ' · ' + c.pct + '% booked · ' + c.guests + ' guests') + '" style="left:' + pos(m) +
        ';width:calc(' + w(D.settings.slot_min) + ' - 2px);height:' + Math.max(2, c.pct * .32) + 'px"></span>';
    }).join('');
    var rows = D.tables.map(function (t) { return { id: t.id, name: t.name, seats: t.seats }; });
    if (live.some(function (r) { return !r.tables.length; })) rows.push({ id: '', name: 'No table', seats: '' });
    var nowLine = D.now_min != null && D.now_min >= lo && D.now_min <= hi
      ? '<span class="now" style="left:calc(var(--lab) + (100% - var(--lab)) * ' + ((D.now_min - lo) / span) + ')"></span>' : '';
    return '<div class="tl" style="--hours:' + hours + '"><div class="tl-in" style="min-width:calc(var(--lab) + ' + hours * HOUR + 'px)">' + nowLine +
      '<div class="tl-row head"><div class="lab">Table</div><div class="lane">' + ticks + '</div></div>' +
      '<div class="tl-row occ"><div class="lab">Booked</div><div class="lane">' + occ + '</div></div>' +
      rows.map(function (row) {
        var blocks = live.filter(function (r) { return row.id ? r.tables.indexOf(row.id) >= 0 : !r.tables.length; }).map(function (r) {
          var joined = r.tables.length > 1 ? ' · ' + r.table_names.join('+') : '';
          var vip = r.guest && r.guest.visits > 2 ? ' ★' : '';
          return '<button type="button" class="blk ' + r.status + '" data-id="' + esc(r.id) + '" style="left:' + pos(r.start_min) + ';width:' + w(r.duration) + '" title="' +
            esc(r.time + '–' + r.end + ' · ' + r.name + ' · ' + r.party + ' guests' + (r.status === 'pending' ? ' · awaiting approval' : r.status === 'seated' ? ' · seated' : '')) +
            '"><b>' + esc(r.name) + vip + '</b> · ' + r.party + esc(joined) + '</button>';
        }).join('');
        return '<div class="tl-row"><div class="lab">' + esc(row.name) + (row.seats ? ' <span>' + row.seats + '</span>' : '') + '</div>' +
          '<div class="lane" data-lane="' + esc(row.id) + '" data-lo="' + lo + '" data-span="' + span + '">' + shade + blocks + '</div></div>';
      }).join('') + '</div></div>';
  }

  PP.timeline = function (el, day, handler) {
    el.innerHTML = day.tables.length ? html(day) : '<div class="ui-empty">Add tables first, under Tables &amp; layout.</div>';
    if (el.__ppTl) el.removeEventListener('click', el.__ppTl);
    el.__ppTl = function (e) {
      var b = e.target.closest('.blk');
      if (b) { handler('edit', { id: b.dataset.id }); return; }
      var lane = e.target.closest('[data-lane]');
      if (!lane) return;
      var rect = lane.getBoundingClientRect();
      var m = +lane.dataset.lo + (e.clientX - rect.left) / rect.width * +lane.dataset.span;
      var step = day.settings.slot_min;
      m = Math.max(0, Math.floor(m / step) * step);
      handler('slot', { time: PP.hm(m), table: lane.dataset.lane || '' });
    };
    el.addEventListener('click', el.__ppTl);
  };
})();
