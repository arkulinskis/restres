/* Helpers for the how-to guide's screenshot steps (tools/howto/howto.py). Loaded once per Chrome run; a shot's "do"
   in docs/howto/guide.json is the body of an async function that can use H. Keep it small and generic: page-specific
   clicks belong in guide.json, next to the shot they set up. */
(function () {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const $ = (s, root) => (root || document).querySelector(s);
  const $$ = (s, root) => Array.from((root || document).querySelectorAll(s));
  const vis = (e) => !!e && e.getBoundingClientRect().width > 0;
  const text = (e) => (e.textContent || '').trim().replace(/\s+/g, ' ');
  async function until(fn, what, ms) {
    const end = Date.now() + (ms || 30000);
    while (Date.now() < end) { try { const v = fn(); if (v) return v; } catch (e) {} await sleep(150); }
    throw new Error('timed out waiting for: ' + what);
  }
  const dialog = () => $$('.anvil-modal-content').filter(vis).pop() || null;
  /* the visible button (or link) whose text is `label` (a string, or a RegExp), inside `scope` (CSS) or the open dialog */
  function button(label, scope) {
    const root = scope === 'dialog' ? dialog() : scope ? $(scope) : document;
    if (!root) return null;
    const ok = (b) => vis(b) && (label instanceof RegExp ? label.test(text(b)) : text(b) === label);
    return $$('button, a.ui-btn, [role=button]', root).find(ok) || null;
  }
  async function click(label, scope, ms) {
    const b = await until(() => button(label, scope), 'button "' + label + '"', ms || 20000);
    b.click();
    await sleep(500);
    return b;
  }
  function type(input, value) {
    input.focus(); input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true }));
    input.dispatchEvent(new Event('blur', { bubbles: true }));
  }
  async function go(hash, ready) {
    if (location.hash !== hash) window.UI_READY = false;
    location.hash = hash;
    await until(() => window.UI_READY === true && location.hash === hash && (!ready || ready()), hash, 60000);
    await sleep(600);
  }
  async function opened(re) { return until(() => dialog() && (!re || re.test(dialog().textContent)) && dialog(), 'dialog ' + (re || ''), 30000); }
  /* close whatever dialog is open: its Cancel / Close button, else Escape (all PlanPlate dialogs are dismissible) */
  async function closeDialogs() {
    for (let i = 0; i < 4 && dialog(); i++) {
      const b = button(/^(Cancel|Close|Done|Not now)$/, 'dialog');
      if (b) b.click();
      else { const m = dialog().closest('.modal'); (m || document).dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', keyCode: 27, which: 27, bubbles: true })); }
      await sleep(700);
    }
  }
  async function view(label) {  // the segmented switches (Timeline / List / Upcoming ...)
    const b = await until(() => $$('.ui-seg button').find((x) => vis(x) && text(x) === label), 'view ' + label);
    b.click();
    await sleep(900);
  }
  async function scrollTo(sel) { const e = await until(() => $$(sel).find(vis), sel); e.scrollIntoView({ block: 'start' }); window.scrollBy(0, -80); await sleep(500); }
  const demoId = () => { const c = $$('.pp-rc').find((x) => /Maison Lumi/.test(x.textContent));
                         return c && decodeURIComponent(c.querySelector('a.ui-btn.primary').getAttribute('href').split('/')[1]); };

  /* Admin -> Demo data -> Reload: fresh bookings for today and the next days, two requests to approve. Sets SEED.rid. */
  async function reloadDemo() {
    const old = demoId() || (window.SEED && window.SEED.rid);
    await go('#admin/demo', () => $('.ad-demo') && button('Reload demo data', '.ad-demo'));
    await click('Reload demo data', '.ad-demo');
    await click('Load', 'dialog');
    await until(() => !dialog(), 'reload confirm closed', 30000);
    for (let i = 0; i < 14; i++) {
      await sleep(4000);
      await go(i % 2 ? '#dashboard' : '#profile');
      if (location.hash === '#dashboard') {
        await until(() => $('.pp-rc'), 'dashboard cards', 30000);
        const id = demoId();
        if (id && id !== old) { window.SEED = Object.assign(window.SEED || {}, { rid: id }); return id; }
      }
    }
    throw new Error('the demo restaurant did not reload');
  }

  /* sign in (or create the account, on the local test database only) with this email and the test password */
  async function signIn(email, name) {
    const form = async (hash) => {
      await go(hash, () => $$('.au-card input').length >= 2);
      return $$('.au-card input[type=text], .au-card input[type=email], .au-card input[type=password]').filter(vis);
    };
    const press = (label) => $$('.au-card .anvil-role-btn-block button').find((b) => text(b) === label).click();
    let inputs = await form('#auth');
    type(inputs[0], email); type(inputs[1], '$TEST_PASSWORD');
    press('Sign in');
    await until(() => location.hash === '#dashboard' || vis($('.anvil-role-msg-error')), 'sign in', 40000);
    if (location.hash !== '#dashboard') {
      inputs = await form('#auth/signup');
      type(inputs[0], name); type(inputs[1], email); type(inputs[2], '$TEST_PASSWORD');
      const tick = $('.au-card input[type=checkbox]'); if (tick && !tick.checked) tick.click();
      press('Create account');
      await until(() => location.hash === '#dashboard', 'sign up', 60000);
    }
    await until(() => window.UI_READY && location.hash === '#dashboard', 'the dashboard', 90000);
    await sleep(2500);  // the restaurant cards (or the empty state)
  }
  async function signOut() {
    const b = $$('button').find((x) => text(x) === 'Sign out');
    if (b) b.click();
    await until(() => !$('.pp-member') || !vis($('.pp-member')) || /landing|auth/.test(location.hash), 'signed out', 30000);
    await sleep(1000);
  }

  try { if (window.UI && UI.setTheme) UI.setTheme('light'); } catch (e) {}  // the guide is printed: light theme

  /* show the live address instead of the local test server's (text, links shown as text, input prefixes, input values) */
  function live(origin) {
    if (!origin) return;
    const host = origin.replace(/^https?:\/\//, ''), re = /https?:\/\/localhost:\d+|localhost:\d+/g;
    const fix = (t) => t.replace(re, (m) => (m.startsWith('http') ? origin : host));
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = walk.nextNode(); n; n = walk.nextNode()) if (/localhost:\d+/.test(n.nodeValue)) n.nodeValue = fix(n.nodeValue);
    $$('input, textarea').forEach((i) => { if (/localhost:\d+/.test(i.value)) i.value = fix(i.value); });
  }

  window.H = { sleep, $, $$, vis, text, until, dialog, button, click, type, go, opened, closeDialogs, view, scrollTo, demoId,
               reloadDemo, signIn, signOut, live };
  return 'helpers ready';
})();
