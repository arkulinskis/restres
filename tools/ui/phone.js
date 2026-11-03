/* Phone-width check (run at 390 px wide by tools/ui_test.py): every page loads without errors and without sideways
   scrolling, signed out (landing, sign-in, the guest pages) and signed in (every restaurant page of the demo).
   Resolves to {ok, log}. */
(async function () {
  const log = [], bad = [];
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  async function until(fn, what, ms) {
    const end = Date.now() + (ms || 30000);
    while (Date.now() < end) { try { const v = fn(); if (v) return v; } catch (e) {} await sleep(150); }
    throw new Error('timed out waiting for: ' + what);
  }
  const $$ = (s) => Array.from(document.querySelectorAll(s));
  async function check(hash, ready) {
    if (location.hash !== hash) window.UI_READY = false;
    location.hash = hash;
    await until(() => window.UI_READY && location.hash === hash && (!ready || ready()), hash, 60000);
    await sleep(700);
    const w = document.documentElement.scrollWidth, vw = screen.width || window.innerWidth;
    const wide = $$('body *').filter((e) => { const r = e.getBoundingClientRect(); return r.width && r.right > vw + 1 && !e.closest('.pp-tl-host, .anvil-role-pp-hours, .pp-tabs'); })
      .slice(0, 3).map((e) => e.tagName.toLowerCase() + '.' + String(e.className).split(' ').slice(0, 2).join('.'));
    if (w > vw + 1) bad.push(hash + ' scrolls sideways (' + w + ' > ' + vw + ') ' + wide.join(' '));
    log.push((w > vw + 1 ? 'WIDE ' : 'ok   ') + hash + ' (' + w + ')');
  }
  try {
    for (const h of ['#landing', '#auth', '#auth/signup', '#book/maison-lumiere', '#menu/maison-lumiere']) await check(h);
    const seed = await (async () => { /*SEED*/ })();
    if (!seed || !seed.rid) throw new Error('could not sign in: ' + JSON.stringify(seed));
    const rid = encodeURIComponent(seed.rid);
    await check('#dashboard');
    for (const p of ['today', 'reservations', 'guests', 'hours', 'tables', 'events', 'dishes', 'gallery', 'website', 'share', 'settings']) await check('#' + p + '/' + rid);
    await check('#profile');
    log.push(bad.length ? 'PROBLEMS: ' + bad.join(' | ') : 'PASSED');
    return { ok: !bad.length, log: log };
  } catch (e) {
    log.push(String(e && e.message || e));
    return { ok: false, log: log };
  }
})();
