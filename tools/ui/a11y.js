/* Accessibility check (WCAG 2.2 A + AA), run inside the real app by tools/ui_test.py through tools/live/drive.mjs.
   1. axe-core (APP_MAKER/vendor/axe-core, injected by ui_test.py) on every page, signed out and signed in, light and dark:
      a "serious" or "critical" WCAG problem fails the run; smaller ones and best-practice hints are listed as notes.
   2. Keyboard checks on the guest booking form: after picking guests, a day or a time, the focus stays on that
      choice (no jump to the top of the page), chosen buttons say so (aria-pressed), the hidden anti-spam box is out of
      the Tab order, tick boxes show a focus ring, fields have autocomplete, and the Privacy page keeps Tab inside.
   Resolves to {ok, log}. Keep log lines ASCII (the Windows console). */
(async function () {
  /*AXE*/
  const log = [], bad = [];
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  async function until(fn, what, ms) {
    const end = Date.now() + (ms || 30000);
    while (Date.now() < end) { try { const v = fn(); if (v) return v; } catch (e) {} await sleep(150); }
    throw new Error('timed out waiting for: ' + what);
  }
  const $ = (s) => document.querySelector(s), $$ = (s) => Array.from(document.querySelectorAll(s));
  const ascii = (s) => String(s).normalize('NFD').replace(/[^\x20-\x7e]/g, '');
  const ok = (cond, msg) => { if (cond) log.push('ok   ' + msg); else { bad.push(msg); log.push('FAIL ' + msg); } };
  async function page(hash, ready) {
    if (location.hash !== hash) window.UI_READY = false;
    location.hash = hash;
    await until(() => window.UI_READY && location.hash === hash && (!ready || ready()), hash, 60000);
    await sleep(900);
  }
  if (!window.axe) { const s = document.createElement('script'); s.textContent = window.__AXE_SRC; document.head.appendChild(s); }

  async function scan(hash, ready) {
    await page(hash, ready);
    for (const theme of ['light', 'dark']) { window.UI.setTheme(theme); await sleep(900); /* let colour transitions and toasts settle */ await axeRun(hash + ' ' + theme); }
    window.UI.setTheme('auto');
  }
  async function axeRun(hash) {
    const res = await window.axe.run(document, {
      runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] },
    });
    let serious = 0;
    for (const v of res.violations) {
      const wcag = v.tags.some((t) => /^wcag2/.test(t));
      const fail = wcag && (v.impact === 'serious' || v.impact === 'critical');
      const where = v.nodes.slice(0, 2).map((n) => ascii(n.target.join(' ')).slice(0, 70)).join(' | ');
      log.push((fail ? 'FAIL ' : 'note ') + hash + ' ' + v.id + ' (' + v.impact + ', ' + v.nodes.length + 'x): ' + where);
      if (fail) {
        serious++; bad.push(hash + ' ' + v.id);
        for (const n of v.nodes.slice(0, 3)) log.push('       ' + ascii(n.html).replace(/\s+/g, ' ').slice(0, 150) + ' :: ' + ascii((n.failureSummary || '').split(/\n/).slice(1).join(' ')).slice(0, 150));
      }
    }
    if (!serious) log.push('ok   ' + hash + ': no serious WCAG problems (' + res.passes.length + ' rules pass)');
  }

  try {
    // ---------------------------------------------------------------- the guest booking form by keyboard
    await page('#book/maison-lumiere', () => $$('.anvil-role-pp-times .anvil-role-chip button').length);
    ok(!!$('[role=heading][aria-level="1"]'), 'booking: the restaurant name is the main heading');
    const two = $$('.pp-party .anvil-role-chip button').find((b) => b.textContent.trim() === '3');
    two.focus(); two.click();
    await until(() => document.activeElement && document.activeElement.getAttribute('data-key') === '|3', 'focus back on "3"', 30000).catch(() => 0);
    ok(document.activeElement && document.activeElement.getAttribute('data-key') === '|3', 'booking: focus stays on the chosen party size');
    ok(document.activeElement.getAttribute('aria-pressed') === 'true', 'booking: the chosen party size says aria-pressed=true');
    const day = $$('.pp-pd').filter((d) => !d.disabled && d.getAttribute('aria-pressed') === 'false')[1];
    const dkey = day.getAttribute('data-key');
    day.focus(); day.click();
    await until(() => document.activeElement && document.activeElement.getAttribute('data-key') === dkey, 'focus back on the day', 30000).catch(() => 0);
    ok(document.activeElement && document.activeElement.getAttribute('data-key') === dkey && document.activeElement.getAttribute('aria-pressed') === 'true',
      'booking: focus stays on the chosen day, which says it is chosen');
    await until(() => /free times|horaires|brivi|No tables|Closed/i.test(ascii(($('.anvil-role-sr') || {}).textContent || '')), 'the spoken status', 30000).catch(() => 0);
    ok($('.anvil-role-sr') && $('.anvil-role-sr').getAttribute('role') === 'status' && ascii($('.anvil-role-sr').textContent).length > 5,
      'booking: a screen-reader status says how many times are free (' + ascii(($('.anvil-role-sr') || {}).textContent || '') + ')');
    const time = await until(() => $$('.anvil-role-pp-times .anvil-role-chip button').find((b) => !b.disabled), 'a free time', 30000);
    const tkey = time.getAttribute('data-key');
    time.focus(); time.click();
    await sleep(500);
    ok(document.activeElement && document.activeElement.getAttribute('data-key') === tkey && document.activeElement.getAttribute('aria-pressed') === 'true',
      'booking: focus stays on the chosen time');
    const next = $('.pp-panel .anvil-role-btn-lg button');
    await until(() => !next.disabled, 'Your details enabled');
    next.click();
    await until(() => $('.pp-summary') && $('.pp-summary').getBoundingClientRect().width > 0, 'details step');
    ok(document.activeElement && document.activeElement.tagName === 'INPUT', 'booking: the details step starts in the name field');
    const fields = $$('.pp-book input, .pp-book textarea').filter((e) => e.getBoundingClientRect().width > 2);
    ok(['name', 'email', 'tel'].every((k) => fields.some((f) => f.autocomplete === k)), 'booking: name, email and phone have autocomplete');
    const hp = $('.pp-hp input');
    ok(hp && hp.tabIndex === -1, 'booking: the hidden anti-spam box is out of the Tab order');
    const tick = $$('.pp-consent input[type=checkbox]')[0];
    tick.focus();
    // a script's focus() doesn't always count as keyboard focus (:focus-visible), so check the app's CSS instead:
    // no app.css rule may drop the outline of a focused tick box, and a :focus-visible rule must draw one
    const appRules = [];
    for (const sh of document.styleSheets) { if (!/app\.css/.test(sh.href || '')) continue; for (const r of sh.cssRules) if (r.selectorText) appRules.push(r); }
    const kills = appRules.filter((r) => /:focus/.test(r.selectorText) && /outline:\s*(none|0)/.test(r.cssText) && (() => { try { return tick.matches(r.selectorText); } catch (e) { return false; } })());
    const rings = appRules.filter((r) => /input:focus-visible|\s:focus-visible/.test(r.selectorText) && /outline:\s*\d/.test(r.cssText));
    ok(!kills.length && rings.length, 'booking: tick boxes keep a focus ring (' + (kills.map((r) => r.selectorText).join(', ') || rings.length + ' ring rules') + ')');
    ok($$('.pp-consent input[type=checkbox]').filter((c) => c.getAttribute('aria-required') === 'true').length === 2, 'booking: the two required ticks say so');
    $$('.pp-book .anvil-role-btn-primary button').filter((b) => b.getBoundingClientRect().width > 0).pop().click();  // empty form
    await until(() => $$('.pp-book .anvil-role-msg-error').some((e) => e.getBoundingClientRect().width > 0), 'the error');
    const err = $$('.pp-book .anvil-role-msg-error').find((e) => e.getBoundingClientRect().width > 0);
    ok(err.getAttribute('role') === 'alert', 'booking: the error is announced (role=alert): ' + ascii(err.textContent).slice(0, 60));
    ok(document.activeElement && document.activeElement.getAttribute('aria-invalid') === 'true', 'booking: focus moves to the first empty field');

    // ---------------------------------------------------------------- the Privacy & Terms page keeps Tab inside
    $$('[data-lk-open]').filter((e) => e.getBoundingClientRect().width > 0)[0].click();
    await until(() => window.LegalKit && window.LegalKit.isOpen(), 'the Privacy page');
    const behind = Array.from(document.body.children).filter((e) => e.id !== 'lk-root' && e.tagName !== 'SCRIPT');
    ok(behind.length && behind.every((e) => e.inert), 'privacy page: the app behind it is inert (Tab stays inside)');
    window.LegalKit.close();
    ok(Array.from(document.body.children).every((e) => !e.inert), 'privacy page: closing it gives the app back');

    // ---------------------------------------------------------------- axe on every page
    for (const h of ['#landing', '#auth', '#auth/signup', '#book/maison-lumiere', '#menu/maison-lumiere']) await scan(h);
    const seed = await (async () => { /*SEED*/ })();
    if (!seed || !seed.rid) throw new Error('could not sign in: ' + JSON.stringify(seed));
    const rid = encodeURIComponent(seed.rid);
    await scan('#dashboard');
    for (const p of ['today', 'reservations', 'guests', 'hours', 'tables', 'events', 'dishes', 'gallery', 'website', 'share', 'settings']) await scan('#' + p + '/' + rid);
    await scan('#profile');
    log.push(bad.length ? 'PROBLEMS: ' + bad.join(' | ') : 'PASSED');
    return { ok: !bad.length, log: log };
  } catch (e) {
    log.push(String(e && e.message || e));
    return { ok: false, log: log };
  }
})();
