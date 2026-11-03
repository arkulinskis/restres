/* PlanPlate's main journeys, run inside the real app (Anvil App Server) by tools/ui_test.py through tools/live/drive.mjs.
   Resolves to {ok, log}. Keep log lines ASCII (the Windows console).
   1. a visitor: the landing page fills the screen, the guest booking form books a table, the guest page shows it,
      the menu (what the QR code opens) lists dishes;
   2. the admin (a manager of the demo restaurant Maison Lumiere): dashboard, Today, Reservations (approve a request,
      add a booking in the editor), Guests, Opening hours, Tables, Events, Menu, Gallery, Website, Share & QR, Settings. */
(async function () {
  const log = [], t0 = Date.now();
  const say = (m) => log.push(((Date.now() - t0) / 1000).toFixed(1) + 's ' + m);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  async function until(fn, what, ms) {
    const end = Date.now() + (ms || 30000);
    while (Date.now() < end) { try { const v = fn(); if (v) return v; } catch (e) {} await sleep(150); }
    throw new Error('timed out waiting for: ' + what);
  }
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));
  const vis = (e) => e && e.getBoundingClientRect().width > 0;
  const btn = (scope, text) => $$(scope + ' button').find((b) => vis(b) && b.textContent.trim().replace(/\s+/g, ' ') === text);
  function type(input, value) {
    input.focus(); input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true }));
    input.dispatchEvent(new Event('blur', { bubbles: true }));
  }
  async function page(hash, ready, what) {
    if (location.hash !== hash) window.UI_READY = false;
    location.hash = hash;
    await until(() => window.UI_READY && location.hash === hash && ready(), what || hash, 60000);
    await sleep(400);
  }
  const ok = (cond, msg) => { if (!cond) throw new Error('FAILED: ' + msg); say('ok   ' + msg); };
  const dialog = () => $$('.anvil-modal-content').filter(vis).pop();

  try {
    // ---------------------------------------------------------------- visitors
    await page('#landing', () => $('.lp-hero'), 'landing');
    const hero = $('.lp-hero').getBoundingClientRect();
    ok(hero.top < 2 && hero.height >= Math.min(window.innerHeight, 640) - 2, 'landing: the hero fills the screen (no band above or below)');
    ok($('.lp-hero .pp-authbox') && $$('.lp-hero input').length >= 2, 'landing: the sign-in box sits in the hero');

    await page('#book/maison-lumiere', () => $$('.anvil-role-pp-times .anvil-role-chip button').length || $('.anvil-role-pp-times') , 'booking form');
    ok(/Maison Lumi/.test($('.anvil-role-pp-mast-name').textContent), 'booking form: the demo restaurant');
    const day = await until(() => $$('.pp-pd').find((d) => !d.disabled && !d.classList.contains('wd') && !d.classList.contains('out')), 'an open day');
    const firstTime = await until(() => $$('.anvil-role-pp-times .anvil-role-chip button').find((b) => !b.disabled), 'a free time', 40000);
    firstTime.click();
    await until(() => !$('.pp-panel .anvil-role-btn-lg button').disabled, 'Continue enabled');
    $('.pp-panel .anvil-role-btn-lg button').click();
    await until(() => vis($('.pp-summary')), 'details step');
    const f = $$('.pp-panel input').filter(vis);
    type(f[0], 'Flow Tester'); type(f[1], 'flow.tester@example.com'); type(f[2], '+1 514 555 0199');
    const tick = $$('.pp-consent input[type=checkbox]').find(vis); if (!tick.checked) tick.click();
    btn('.pp-panel', 'Book table') ? btn('.pp-panel', 'Book table').click() : btn('.pp-panel', 'Send request').click();
    await until(() => vis($('.pp-done')), 'booked', 40000);
    ok(/booked|received/i.test($('.pp-done').textContent), 'booking form: a guest books a table');
    const manage = $('.pp-done a.ui-btn.primary').getAttribute('href');
    ok(/#r\/[0-9a-f]{32}/.test(manage), 'booking form: the guest gets their private link');
    await page('#r/' + manage.split('#r/')[1], () => $('.pp-status'), 'guest page');
    ok(/Flow Tester/.test($('.pp-status').textContent), 'guest page: shows the booking');
    await page('#menu/maison-lumiere', () => $$('.pp-dish').length > 3, 'menu');
    ok(/Confit de canard/.test(document.body.textContent), 'menu: the dishes (what the QR code opens)');

    // ---------------------------------------------------------------- the manager
    const seed = await (async () => { /*SEED*/ })();
    ok(seed && seed.rid, 'signed in; the demo restaurant is on the dashboard');
    const rid = encodeURIComponent(seed.rid);
    await page('#today/' + rid, () => $('.pp-status-card'));
    ok(/Open now|Closed/.test($('.anvil-role-pp-big-t').textContent), 'today: open or closed right now');
    ok($$('.pp-stat').length === 4, 'today: the four numbers');

    await page('#reservations/' + rid, () => $('.pp-daybar'));
    ok($$('.pp-ap').length >= 1, 'reservations: requests waiting for approval');
    const before = $$('.pp-ap').length;
    btn('.pp-ap', 'Approve').click();
    await until(() => $$('.pp-ap').length === before - 1 || !vis($('.pp-approvals')), 'approved', 40000);
    ok(true, 'reservations: approve a request');
    ok($('.pp-tl-host .tl') || $('.pp-tl-host .ui-empty'), 'reservations: the timeline draws');
    btn('.pp-res-tools', 'New booking').click();
    await until(() => dialog() && /Add a booking/.test(dialog().textContent), 'booking editor');
    const d = dialog();
    const inputs = Array.from(d.querySelectorAll('input')).filter(vis);
    const nameBox = inputs.find((i) => i.closest('label') && /Guest name/.test(i.closest('label').textContent));
    type(nameBox, 'Phone Booking Test');
    const timeBox = inputs.find((i) => i.type === 'time');
    type(timeBox, '19:00');
    Array.from(d.querySelectorAll('button')).find((b) => b.textContent.trim() === 'Add booking').click();
    await until(() => !dialog() || /could not|anyway/i.test(dialog().textContent), 'saved', 40000);
    if (dialog()) { const force = Array.from(dialog().querySelectorAll('button')).find((b) => /Save anyway/.test(b.textContent)); if (force) force.click(); }
    await until(() => !dialog(), 'editor closed', 40000);
    ok(true, 'reservations: a staff booking is added in the editor');
    $$('.ui-seg button').find((b) => b.textContent.trim() === 'List').click();
    await until(() => vis($('.pp-res-list')) || vis($$('.ui-empty').find(vis)), 'list view');
    ok(true, 'reservations: list view');

    await page('#guests/' + rid, () => $$('.pp-grow-row').length > 1);
    ok(/lise Martin/.test($('.pp-glist').textContent), 'guests: the guest book lists regulars');
    $$('button.pp-grow-row').find((r) => /lise Martin/.test(r.textContent)).click();
    await until(() => dialog() && /Visits and bookings/.test(dialog().textContent), 'guest card');
    ok(/VIP|Regular/.test(dialog().textContent), 'guests: a guest card with tags and visits');
    Array.from(dialog().querySelectorAll('button')).find((b) => b.textContent.trim() === 'Close').click();
    await until(() => !dialog(), 'closed');

    await page('#hours/' + rid, () => $$('.pp-day').length > 20);
    ok($$('.pp-pc').length >= 2, 'hours: periods and the month calendar');
    await page('#tables/' + rid, () => $$('.pp-floor .tb').length >= 9);
    ok(true, 'tables: the floor plan draws every table');
    $$('.pp-floor .tb')[0].dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, clientX: 10, clientY: 10, pointerId: 1 }));
    $$('.pp-floor .tb')[0].dispatchEvent(new PointerEvent('pointerup', { bubbles: true, clientX: 10, clientY: 10, pointerId: 1 }));
    await until(() => vis($$('.pp-side input').find(vis)), 'table form');
    ok(/T\d/.test($$('.pp-side input').find(vis).value), 'tables: tap a table to edit it');
    await page('#events/' + rid, () => $$('.pp-ec').length >= 1);
    btn('.pp-ec', 'Set up the room') ? btn('.pp-ec', 'Set up the room').click() : btn('.pp-ec', 'Room').click();
    await until(() => $$('.pp-setup .pp-floor .tb').length >= 9, 'room set-up');
    ok(true, 'events: an event room set-up opens on the floor plan');
    await page('#dishes/' + rid, () => $$('.pp-eddish').length > 5);
    ok(true, 'menu editor: sections and dishes');
    await page('#gallery/' + rid, () => $('.pp-gallery'));
    ok(/Stored/.test(document.body.textContent), 'gallery: the photo storage is shown');
    await page('#website/' + rid, () => $('.pp-sbar'));
    ok(vis($('.pp-site-layout')) || vis($('.pp-welcome')), 'website: the builder');
    await page('#share/' + rid, () => $$('.pp-qr svg').length >= 2);
    ok(/embed\.js/.test(document.body.textContent), 'share: QR codes and the Reserve button code');
    await page('#settings/' + rid, () => $('.pp-set'));
    ok($$('.pp-rule').length >= 6, 'settings: the booking rules');
    say('PASSED');
    return { ok: true, log: log };
  } catch (e) {
    say(String(e && e.message || e));
    return { ok: false, log: log };
  }
})();
