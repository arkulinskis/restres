/* For member pages (screenshots, the restaurant flow): sign in on the LOCAL App Server as the admin address, which
   DemoData makes a manager of the demo restaurant, Maison Lumière. First run: creates the account (local database
   only) with the password in tools/live/.test-account-password.txt (git-ignored; drive.mjs fills it in).
   Resolves to window.SEED = {rid, dashboard}. */
(async function () {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  async function until(fn, what, ms) {
    const end = Date.now() + (ms || 30000);
    while (Date.now() < end) { try { const v = fn(); if (v) return v; } catch (e) {} await sleep(150); }
    throw new Error('timed out waiting for: ' + what);
  }
  const $ = (s) => document.querySelector(s), $$ = (s) => Array.from(document.querySelectorAll(s));
  function type(input, value) {
    input.focus(); input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true }));
  }
  const EMAIL = 'arkulinskis@gmail.com', PW = '$TEST_PASSWORD';
  async function form(hash) {
    if (location.hash !== hash) window.UI_READY = false;
    location.hash = hash;
    await until(() => window.UI_READY && $$('.au-card input').length >= 2, hash);
    return $$('.au-card input[type=text], .au-card input[type=email], .au-card input[type=password]').filter((i) => i.offsetParent !== null);
  }
  const press = (label) => $$('.au-card .anvil-role-btn-block button').find((b) => b.textContent.trim() === label).click();
  try {
    if (!$('.pp-member') || $('.pp-member').offsetParent === null) {
      let inputs = await form('#auth');
      type(inputs[0], EMAIL); type(inputs[1], PW);
      press('Sign in');
      await until(() => location.hash === '#dashboard' || ($('.anvil-role-msg-error') && $('.anvil-role-msg-error').offsetParent), 'sign in', 40000);
      if (location.hash !== '#dashboard') {
        inputs = await form('#auth/signup');
        type(inputs[0], 'Vitalijs (admin)'); type(inputs[1], EMAIL); type(inputs[2], PW);
        const tick = $('.au-card input[type=checkbox]'); if (tick && !tick.checked) tick.click();
        press('Create account');
        await until(() => location.hash === '#dashboard', 'sign up', 60000);
      }
    }
    await until(() => window.UI_READY && $('.pp-rc'), 'dashboard cards (the demo restaurant)', 90000);
    const card = $$('.pp-rc').find((c) => /Maison Lumi/.test(c.textContent));
    const href = card && card.querySelector('a.ui-btn.primary').getAttribute('href');
    window.SEED = { rid: href ? decodeURIComponent(href.split('/')[1]) : null, dashboard: '#dashboard' };
    return window.SEED;
  } catch (e) {
    return { error: String(e && e.message || e) };
  }
})();
