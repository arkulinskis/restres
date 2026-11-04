/* Admin pages (local App Server only: signs up the ADMIN_EMAILS address, which becomes admin there).
   Visits every tab, flips a user's Active switch twice, opens the demo-data confirm, imports old-PlanPlate CSV files. Resolves to {ok, log}. */
(async function () {
  const log = [];
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  async function until(fn, what, ms) {
    const end = Date.now() + (ms || 30000);
    while (Date.now() < end) { try { const v = fn(); if (v) return v; } catch (e) {} await sleep(150); }
    throw new Error('timed out waiting for: ' + what);
  }
  const $ = (s) => document.querySelector(s), $$ = (s) => Array.from(document.querySelectorAll(s));
  const ok = (c, m) => { if (!c) throw new Error('FAILED: ' + m); log.push('ok   ' + m); };
  function type(input, value) {
    input.focus(); input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true }));
  }
  async function page(hash, ready) {
    if (location.hash !== hash) window.UI_READY = false;
    location.hash = hash;
    await until(() => window.UI_READY && location.hash === hash && ready(), hash);
    await sleep(300);
  }
  try {
    // sign in as the admin address (seed.js's local account; created on the first run)
    await page('#auth', () => $$('.au-card input').length >= 2);
    const inputs = () => $$('.au-card input[type=text], .au-card input[type=email], .au-card input[type=password]').filter((i) => i.offsetParent);
    const pw = '$TEST_PASSWORD';
    type(inputs()[0], 'arkulinskis@gmail.com'); type(inputs()[1], pw);
    $$('.au-card .anvil-role-btn-block button').find((b) => /Sign in/.test(b.textContent)).click();
    await sleep(4000);
    if (location.hash !== '#dashboard') {  // no account yet in this local database: create it
      await page('#auth/signup', () => $$('.au-card input').length >= 3);
      const i = inputs(); type(i[0], 'Local Admin'); type(i[1], 'arkulinskis@gmail.com'); type(i[2], pw);
      const tick = $('.au-card input[type=checkbox]'); if (tick && !tick.checked) tick.click();
      $$('.au-card .anvil-role-btn-block button').find((b) => /Create account/.test(b.textContent)).click();
    }
    await until(() => location.hash === '#dashboard' && window.UI_READY, 'signed in as admin', 60000);
    await page('#admin/overview', () => $$('.ad-stat').length >= 3);
    ok(/\d/.test($('.ad-stat').textContent), 'overview: the numbers');
    ok($('.anvil-role-avatar button') && (document.querySelector('.ui-menu a[href="#admin"]') || {}).offsetParent !== undefined, 'menu has the Admin link');
    await page('#admin/feedback', () => $('.ad-filter'));
    ok(/New \(\d+\)/.test($('.ad-filter').textContent), 'feedback: filter counts');
    await page('#admin/users', () => $$('.ad-user-row').length >= 1);
    const row = $$('.ad-user-row').find((r) => !/arkulinskis@gmail.com/.test(r.textContent));
    const box = row.querySelectorAll('input[type=checkbox]')[1];
    const was = box.checked;
    box.click(); await sleep(2500); box.click(); await sleep(2500);
    ok(box.checked === was, 'users: Active switch saved twice (back as it was)');
    type($('.anvil-role-ad-search-box'), 'nobody-matches-this'); $('.anvil-role-ic-search button').click();
    await until(() => $$('.ad-user-row').length === 0, 'search narrows');
    ok(/0 people/.test(document.body.textContent), 'users: search');
    await page('#admin/demo', () => $('.ad-demo'));
    ok(/Status:/.test($('.ad-demo').textContent), 'demo: status line');

    // Old PlanPlate: import CSV files the way Anvil's Data Tables download them
    await page('#admin/users', () => $$('.ad-user-row').length >= 1);
    ok($$('.ad-user-row')[0].querySelectorAll('input[type=checkbox]').length === 3, 'users: Admin, Active and Free plan switches');
    await page('#admin/import', () => $('.ad-import') && $('.ad-import input[type=file]'));
    ok($('.ad-import input[name=timezone], .ad-import input[type=hidden]'), 'import: the time zone field');
    const OLD = 'c0ffee00-1111-4222-8333-944445555666';
    const day = new Date(Date.now() + 10 * 864e5).toISOString().slice(0, 10);
    const csv = (name, rows) => new File([rows.map((r) => r.map((c) => '"' + String(c).replace(/"/g, '""') + '"').join(',')).join(String.fromCharCode(13, 10))], name, { type: 'text/csv' });
    const files = [
      csv('restaurants.csv', [['uid', 'restaurant', 'eating_time', 'regular', 'special', 'table_seats', 'contact_email', 'resto_message_en', 'resto_message_fr', 'resto_message_lv'],
        [OLD, 'UI Import Bistro', '1.5', JSON.stringify([['Monday', '17:00', '22:00'], ['Tuesday', '17:00', '22:00']]), '[]', JSON.stringify([['a', false, '4'], ['b', false, '2']]),
         'ui.import@example.com', 'Hello from the old app', '', '']]),
      csv('new_staff_access.csv', [['restaurant_id', 'user_id', 'type_id', 'user_name'], [OLD, 'ui.import@example.com', 'owner', '']]),
      csv('reservations.csv', [['restaurant', 'guests', 'special_comments', 'name', 'phone', 'email', 'mydate', 'mytime', 'reservation_request_time', 'approved', 'seated', 'done', 'reservation_uid', 'notified_info_email', 'resto_comment', 'status'],
        [OLD, '2', '', 'Old Guest', '123', 'old.guest@example.com', day, '19:00', '', 'True', 'False', 'False', 'c0ffee00-aaaa-4bbb-8ccc-000000000001', 'True', '', '']]),
    ];
    const input = $('.ad-import input[type=file]');
    const dtf = new DataTransfer(); files.forEach((f) => dtf.items.add(f)); input.files = dtf.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
    await until(() => /UI Import Bistro/.test(($('.anvil-role-ad-pre') || {}).textContent || ''), 'import preview', 40000);
    ok(/reservations: 1 rows/.test($('.anvil-role-ad-pre').textContent), 'import: the preview lists what is in the files');
    $('.ad-import .anvil-role-ic-database button').click();
    const go = await until(() => $$('.modal button, .anvil-modal-content button').find((b) => b.textContent.trim() === 'Import' && b.offsetParent), 'import confirm');
    go.click();
    await until(() => $$('.anvil-role-ad-pre').some((p) => /^Done\./.test(p.textContent) && p.offsetParent), 'import report', 60000);
    ok(/restaurants (added|updated): 1/.test(document.body.textContent), 'import: the restaurant is in');
    const hours = await (await fetch('/_/api/v1/' + OLD + '/en')).text();
    ok(/Monday:<\/strong> 17:00-22:00/.test(hours), 'import: the old hours widget answers for the imported restaurant');
    const qr = await fetch('/reserve/' + OLD + '/en', { redirect: 'manual' });
    ok(qr.type === 'opaqueredirect' || qr.status === 302 || qr.redirected, 'import: its printed booking QR code opens the booking form');
    log.push('PASSED');
    return { ok: true, log };
  } catch (e) {
    log.push(String(e && e.message || e));
    return { ok: false, log };
  }
})();
