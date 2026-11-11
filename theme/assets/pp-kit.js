/* pp-kit.js: PlanPlate's browser helpers, reached from Python as window.PP (client_code/pp.py wraps them).
   Dates as "YYYY-MM-DD" strings in the restaurant's local time, the time-zone search field (PP.tzField: wired once
   on document), QR codes (qrcode-generator from cdnjs), clipboard, and photo/video uploads (Cloudinary signed direct
   upload, or shrunk on the device and sent to PlanPlate). The pages themselves are Anvil Forms. */
(function () {
  if (window.PP && window.PP.__v) return;
  var PP = window.PP = { __v: 2 };

  PP.esc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  };
  PP.DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  PP.DAYS3 = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  PP.MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  // Dates travel as "YYYY-MM-DD" strings in the restaurant's local time; never shift them through UTC.
  PP.parseDate = function (iso) { var p = String(iso).split('-'); return new Date(+p[0], +p[1] - 1, +p[2]); };
  PP.isoDate = function (d) { return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); };
  PP.addDays = function (iso, n) { var d = PP.parseDate(iso); d.setDate(d.getDate() + n); return PP.isoDate(d); };
  PP.weekday = function (iso) { return (PP.parseDate(iso).getDay() + 6) % 7; }; // Monday = 0
  PP.fmtDate = function (iso, opts) {
    if (!iso) return '';
    return PP.parseDate(iso.slice(0, 10)).toLocaleDateString(PP.locale || undefined, opts || { weekday: 'long', day: 'numeric', month: 'long' });
  };
  PP.fmtShort = function (iso) { return PP.fmtDate(iso, { weekday: 'short', day: 'numeric', month: 'short' }); };
  PP.fmtStamp = function (iso) {
    if (!iso) return '';
    return new Date(iso).toLocaleString(PP.locale || undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  };
  PP.toMin = function (hm) { var p = String(hm).split(':'); return +p[0] * 60 + +p[1]; };
  PP.hm = function (m) { return String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0'); };
  PP.hoursText = function (iv) { return iv && iv.length ? iv.map(function (p) { return p[0] + '–' + p[1]; }).join(', ') : 'Closed'; };
  PP.plural = function (n, one, many) { return n + ' ' + (n === 1 ? one : (many || one + 's')); };
  PP.STATUS = { pending: 'Awaiting approval', confirmed: 'Confirmed', declined: 'Declined', cancelled: 'Cancelled' };
  PP.SOURCE = { online: 'Online', phone: 'Phone', walk_in: 'Walk-in', staff: 'Staff' };
  PP.status = function (s) { return '<span class="badge ' + PP.esc(s) + '">' + PP.esc(PP.STATUS[s] || s) + '</span>'; };

  var P = 'fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"';
  var ICONS = {
    plus: '<path d="M12 5v14M5 12h14"/>', left: '<path d="m15 18-6-6 6-6"/>', right: '<path d="m9 18 6-6-6-6"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>', check: '<path d="M20 6 9 17l-5-5"/>', down: '<path d="m6 9 6 6 6-6"/>',
    bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    table: '<rect x="3" y="8" width="18" height="6" rx="1"/><path d="M6 14v6M18 14v6"/>',
    cog: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    ext: '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14 21 3"/>',
    list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    timeline: '<path d="M3 6h10M7 12h12M3 18h8"/>',
    link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    phone: '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"/>',
    pin: '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>',
    edit: '<path d="M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    trash: '<path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>',
    join: '<path d="M8 12h8M3 7h5v10H3zM16 7h5v10h-5z"/>', split: '<path d="M3 7h6v10H3zM15 7h6v10h-6zM12 4v16"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
    grid: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>',
    download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    qr: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 14h3v3h-3zM20 14v.01M14 20h.01M17 20h4v-3"/>',
    image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/>',
    star: '<path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/>',
    camera: '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>',
    upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>',
    eye: '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>',
    eyeoff: '<path d="M17.9 17.9A10.1 10.1 0 0 1 12 20c-7 0-11-8-11-8a18.5 18.5 0 0 1 5.1-5.9M9.9 4.2A9.1 9.1 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.2 3.2M1 1l22 22"/><path d="M14.1 14.1a3 3 0 1 1-4.2-4.2"/>',
    video: '<rect x="2" y="5" width="15" height="14" rx="2"/><path d="m17 10 5-3v10l-5-3z"/>',
    print: '<path d="M6 9V2h12v7M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/>',
    sparkle: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8"/>',
    palette: '<circle cx="13.5" cy="6.5" r="1"/><circle cx="17.5" cy="10.5" r="1"/><circle cx="8.5" cy="7.5" r="1"/><circle cx="6.5" cy="12.5" r="1"/><path d="M12 2a10 10 0 0 0 0 20c1.1 0 2-.9 2-2 0-.5-.2-1-.5-1.3-.3-.4-.5-.8-.5-1.3 0-1.1.9-2 2-2h2.4A5.6 5.6 0 0 0 22 9.8C22 5.5 17.5 2 12 2z"/>',
    move: '<path d="M5 9l-3 3 3 3M9 5l3-3 3 3M15 19l-3 3-3-3M19 9l3 3-3 3M2 12h20M12 2v20"/>'
  };
  PP.icon = function (name, cls) { return '<svg class="ic ' + (cls || '') + '" viewBox="0 0 24 24" ' + P + ' aria-hidden="true">' + (ICONS[name] || '') + '</svg>'; };
  // The PlanPlate mark: a plate seen from above.
  PP.mark = function (cls) {
    return '<svg class="' + (cls || 'mark') + '" viewBox="0 0 32 32" aria-hidden="true" fill="none" stroke="currentColor"><circle cx="16" cy="16" r="14" stroke-width="1.4"/><circle cx="16" cy="16" r="9" stroke-width="1"/><path d="M16 10.5v11" stroke-width="1.4" stroke-linecap="round"/></svg>';
  };

  PP.toast = function (msg, isErr) { if (PP.toastHook) PP.toastHook(String(msg), !!isErr); else console.log(msg); };
  PP.copy = function (text, label) {
    function done() { PP.toast((label || 'Copied') + ' to the clipboard'); }
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, fallback);
    else fallback();
    function fallback() {
      var ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); done(); } catch (e) { PP.toast('Copy failed: select the text and copy it', true); }
      ta.remove();
    }
  };
  PP.err = function (e) { return (e && (e.message || e.toString())) || 'Something went wrong.'; };

  // The host stand (Reservations): a two-note chime when a booking arrives, and a screen that stays awake.
  // Browsers only allow sound after the person has touched the page once, so the audio is unlocked on the first tap or key.
  var audio = null;
  function unlockAudio() {
    try {
      var AC = window.AudioContext || window.webkitAudioContext;
      if (!audio && AC) audio = new AC();
      if (audio && audio.state === 'suspended') audio.resume();
    } catch (e) { audio = null; }
  }
  document.addEventListener('pointerdown', unlockAudio, true);
  document.addEventListener('keydown', unlockAudio, true);
  PP.chimes = 0;  // how many times a chime was asked for (the UI test reads it)
  PP.chime = function () {
    PP.chimes += 1;
    if (!audio || audio.state !== 'running') return false;
    var now = audio.currentTime;
    [[700, 0], [900, 0.12]].forEach(function (n) {
      var osc = audio.createOscillator(), gain = audio.createGain(), at = now + n[1];
      osc.type = 'sine'; osc.frequency.setValueAtTime(n[0], at);
      gain.gain.setValueAtTime(0.0001, at);
      gain.gain.exponentialRampToValueAtTime(0.25, at + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.32);
      osc.connect(gain); gain.connect(audio.destination); osc.start(at); osc.stop(at + 0.4);
    });
    return true;
  };
  var wakeLock = null, wakeWanted = false;
  function wakeGrab() {
    if (!wakeWanted || wakeLock || document.hidden || !navigator.wakeLock) return;
    navigator.wakeLock.request('screen').then(function (lock) {
      wakeLock = lock;
      lock.addEventListener('release', function () { if (wakeLock === lock) wakeLock = null; });
      if (!wakeWanted) lock.release();
    }, function () { /* battery saver or an old browser: the screen sleeps as usual */ });
  }
  document.addEventListener('visibilitychange', wakeGrab);  // the browser drops the lock when the tab is hidden
  PP.wake = function (on) {
    wakeWanted = !!on;
    if (wakeWanted) wakeGrab();
    else if (wakeLock) { wakeLock.release(); wakeLock = null; }
  };
  PP.dialogOpen = function () {
    return Array.prototype.some.call(document.querySelectorAll('.anvil-modal-content, .modal-content'), function (e) { return e.getBoundingClientRect().width > 0; });
  };

  PP.appUrl = function () { return location.origin + location.pathname; };
  PP.menuUrl = function (slug) { return PP.appUrl() + '#menu/' + slug; };

  // QR codes (qrcode-generator from cdnjs). PP.qrSvg → an <svg> string; PP.qrPng downloads a print-size PNG.
  function qrMatrix(text) {
    if (!window.qrcode) return null;
    var q = window.qrcode(0, 'M'); q.addData(text); q.make();
    return q;
  }
  PP.qrSvg = function (text, px) {
    var q = qrMatrix(text);
    if (!q) return '<div class="hint">QR codes need an internet connection to load.</div>';
    var n = q.getModuleCount(), m = 2, size = n + m * 2, path = '';
    for (var r = 0; r < n; r++) for (var c = 0; c < n; c++) if (q.isDark(r, c)) path += 'M' + (c + m) + ' ' + (r + m) + 'h1v1h-1z';
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + size + ' ' + size + '" width="' + (px || 160) + '" height="' + (px || 160) + '" shape-rendering="crispEdges" role="img" aria-label="QR code"><rect width="100%" height="100%" fill="#fff"/><path d="' + path + '" fill="#1d1b18"/></svg>';
  };
  PP.qrPng = function (text, filename, caption) {
    var q = qrMatrix(text);
    if (!q) { PP.toast('QR codes need an internet connection to load.', true); return; }
    var n = q.getModuleCount(), cell = 24, m = 4, size = (n + m * 2) * cell, extra = caption ? 90 : 0;
    var cv = document.createElement('canvas'); cv.width = size; cv.height = size + extra;
    var g = cv.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, cv.width, cv.height); g.fillStyle = '#1d1b18';
    for (var r = 0; r < n; r++) for (var c = 0; c < n; c++) if (q.isDark(r, c)) g.fillRect((c + m) * cell, (r + m) * cell, cell, cell);
    if (caption) { g.font = '600 44px Georgia, serif'; g.textAlign = 'center'; g.fillText(caption, size / 2, size + 40); }
    var a = document.createElement('a'); a.href = cv.toDataURL('image/png'); a.download = filename || 'qr.png';
    document.body.appendChild(a); a.click(); a.remove();
  };
  PP.bookUrl = function (slug) { return PP.appUrl() + '#book/' + slug; };
  PP.manageUrl = function (token) { return PP.appUrl() + '#r/' + token; };

  // Time-zone picker. PP.tzField(name, value, id) returns the field's HTML: a hidden input (name = the tz id)
  // and a search box. Type a country, city or offset ("France", "Riga", "GMT+2"); the full list shows on focus.
  // Wired once on document, so any component can use it. Picking fires 'change' on the hidden input.
  // Data: country code|name|zones from the tz database (zone.tab + iso3166.tab).
  var TZ_DATA = "AF|Afghanistan|Asia/Kabul;AL|Albania|Europe/Tirane;DZ|Algeria|Africa/Algiers;AD|Andorra|Europe/Andorra;AO|Angola|Africa/Luanda;AI|Anguilla|America/Anguilla;AQ|Antarctica|Antarctica/McMurdo,Antarctica/Casey,Antarctica/Davis,Antarctica/DumontDUrville,Antarctica/Mawson,Antarctica/Palmer,Antarctica/Rothera,Antarctica/Syowa,Antarctica/Troll,Antarctica/Vostok;AG|Antigua & Barbuda|America/Antigua;AR|Argentina|America/Argentina/Buenos_Aires,America/Argentina/Cordoba,America/Argentina/Salta,America/Argentina/Jujuy,America/Argentina/Tucuman,America/Argentina/Catamarca,America/Argentina/La_Rioja,America/Argentina/San_Juan,America/Argentina/Mendoza,America/Argentina/San_Luis,America/Argentina/Rio_Gallegos,America/Argentina/Ushuaia;AM|Armenia|Asia/Yerevan;AW|Aruba|America/Aruba;AU|Australia|Australia/Lord_Howe,Antarctica/Macquarie,Australia/Hobart,Australia/Melbourne,Australia/Sydney,Australia/Broken_Hill,Australia/Brisbane,Australia/Lindeman,Australia/Adelaide,Australia/Darwin,Australia/Perth,Australia/Eucla;AT|Austria|Europe/Vienna;AZ|Azerbaijan|Asia/Baku;BS|Bahamas|America/Nassau;BH|Bahrain|Asia/Bahrain;BD|Bangladesh|Asia/Dhaka;BB|Barbados|America/Barbados;BY|Belarus|Europe/Minsk;BE|Belgium|Europe/Brussels;BZ|Belize|America/Belize;BJ|Benin|Africa/Porto-Novo;BM|Bermuda|Atlantic/Bermuda;BT|Bhutan|Asia/Thimphu;BO|Bolivia|America/La_Paz;BA|Bosnia & Herzegovina|Europe/Sarajevo;BW|Botswana|Africa/Gaborone;BR|Brazil|America/Noronha,America/Belem,America/Fortaleza,America/Recife,America/Araguaina,America/Maceio,America/Bahia,America/Sao_Paulo,America/Campo_Grande,America/Cuiaba,America/Santarem,America/Porto_Velho,America/Boa_Vista,America/Manaus,America/Eirunepe,America/Rio_Branco;IO|British Indian Ocean Territory|Indian/Chagos;BN|Brunei|Asia/Brunei;BG|Bulgaria|Europe/Sofia;BF|Burkina Faso|Africa/Ouagadougou;BI|Burundi|Africa/Bujumbura;KH|Cambodia|Asia/Phnom_Penh;CM|Cameroon|Africa/Douala;CA|Canada|America/St_Johns,America/Halifax,America/Glace_Bay,America/Moncton,America/Goose_Bay,America/Blanc-Sablon,America/Toronto,America/Iqaluit,America/Atikokan,America/Winnipeg,America/Resolute,America/Rankin_Inlet,America/Regina,America/Swift_Current,America/Edmonton,America/Cambridge_Bay,America/Inuvik,America/Creston,America/Dawson_Creek,America/Fort_Nelson,America/Whitehorse,America/Dawson,America/Vancouver;CV|Cape Verde|Atlantic/Cape_Verde;BQ|Caribbean NL|America/Kralendijk;KY|Cayman Islands|America/Cayman;CF|Central African Rep.|Africa/Bangui;TD|Chad|Africa/Ndjamena;CL|Chile|America/Santiago,America/Punta_Arenas,Pacific/Easter;CN|China|Asia/Shanghai,Asia/Urumqi;CX|Christmas Island|Indian/Christmas;CC|Cocos (Keeling) Islands|Indian/Cocos;CO|Colombia|America/Bogota;KM|Comoros|Indian/Comoro;CG|Congo (Brazzaville)|Africa/Brazzaville;CD|Congo (Kinshasa)|Africa/Kinshasa,Africa/Lubumbashi;CK|Cook Islands|Pacific/Rarotonga;CR|Costa Rica|America/Costa_Rica;HR|Croatia|Europe/Zagreb;CU|Cuba|America/Havana;CW|Curaçao|America/Curacao;CY|Cyprus|Asia/Nicosia,Asia/Famagusta;CZ|Czechia|Europe/Prague;CI|Côte d'Ivoire|Africa/Abidjan;DK|Denmark|Europe/Copenhagen;DJ|Djibouti|Africa/Djibouti;DM|Dominica|America/Dominica;DO|Dominican Republic|America/Santo_Domingo;TL|East Timor|Asia/Dili;EC|Ecuador|America/Guayaquil,Pacific/Galapagos;EG|Egypt|Africa/Cairo;SV|El Salvador|America/El_Salvador;GQ|Equatorial Guinea|Africa/Malabo;ER|Eritrea|Africa/Asmara;EE|Estonia|Europe/Tallinn;SZ|Eswatini (Swaziland)|Africa/Mbabane;ET|Ethiopia|Africa/Addis_Ababa;FK|Falkland Islands|Atlantic/Stanley;FO|Faroe Islands|Atlantic/Faroe;FJ|Fiji|Pacific/Fiji;FI|Finland|Europe/Helsinki;FR|France|Europe/Paris;GF|French Guiana|America/Cayenne;PF|French Polynesia|Pacific/Tahiti,Pacific/Marquesas,Pacific/Gambier;TF|French S. Terr.|Indian/Kerguelen;GA|Gabon|Africa/Libreville;GM|Gambia|Africa/Banjul;GE|Georgia|Asia/Tbilisi;DE|Germany|Europe/Berlin,Europe/Busingen;GH|Ghana|Africa/Accra;GI|Gibraltar|Europe/Gibraltar;GR|Greece|Europe/Athens;GL|Greenland|America/Nuuk,America/Danmarkshavn,America/Scoresbysund,America/Thule;GD|Grenada|America/Grenada;GP|Guadeloupe|America/Guadeloupe;GU|Guam|Pacific/Guam;GT|Guatemala|America/Guatemala;GG|Guernsey|Europe/Guernsey;GN|Guinea|Africa/Conakry;GW|Guinea-Bissau|Africa/Bissau;GY|Guyana|America/Guyana;HT|Haiti|America/Port-au-Prince;HN|Honduras|America/Tegucigalpa;HK|Hong Kong|Asia/Hong_Kong;HU|Hungary|Europe/Budapest;IS|Iceland|Atlantic/Reykjavik;IN|India|Asia/Kolkata;ID|Indonesia|Asia/Jakarta,Asia/Pontianak,Asia/Makassar,Asia/Jayapura;IR|Iran|Asia/Tehran;IQ|Iraq|Asia/Baghdad;IE|Ireland|Europe/Dublin;IM|Isle of Man|Europe/Isle_of_Man;IL|Israel|Asia/Jerusalem;IT|Italy|Europe/Rome;JM|Jamaica|America/Jamaica;JP|Japan|Asia/Tokyo;JE|Jersey|Europe/Jersey;JO|Jordan|Asia/Amman;KZ|Kazakhstan|Asia/Almaty,Asia/Qyzylorda,Asia/Qostanay,Asia/Aqtobe,Asia/Aqtau,Asia/Atyrau,Asia/Oral;KE|Kenya|Africa/Nairobi;KI|Kiribati|Pacific/Tarawa,Pacific/Kanton,Pacific/Kiritimati;KW|Kuwait|Asia/Kuwait;KG|Kyrgyzstan|Asia/Bishkek;LA|Laos|Asia/Vientiane;LV|Latvia|Europe/Riga;LB|Lebanon|Asia/Beirut;LS|Lesotho|Africa/Maseru;LR|Liberia|Africa/Monrovia;LY|Libya|Africa/Tripoli;LI|Liechtenstein|Europe/Vaduz;LT|Lithuania|Europe/Vilnius;LU|Luxembourg|Europe/Luxembourg;MO|Macau|Asia/Macau;MG|Madagascar|Indian/Antananarivo;MW|Malawi|Africa/Blantyre;MY|Malaysia|Asia/Kuala_Lumpur,Asia/Kuching;MV|Maldives|Indian/Maldives;ML|Mali|Africa/Bamako;MT|Malta|Europe/Malta;MH|Marshall Islands|Pacific/Majuro,Pacific/Kwajalein;MQ|Martinique|America/Martinique;MR|Mauritania|Africa/Nouakchott;MU|Mauritius|Indian/Mauritius;YT|Mayotte|Indian/Mayotte;MX|Mexico|America/Mexico_City,America/Cancun,America/Merida,America/Monterrey,America/Matamoros,America/Chihuahua,America/Ciudad_Juarez,America/Ojinaga,America/Mazatlan,America/Bahia_Banderas,America/Hermosillo,America/Tijuana;FM|Micronesia|Pacific/Chuuk,Pacific/Pohnpei,Pacific/Kosrae;MD|Moldova|Europe/Chisinau;MC|Monaco|Europe/Monaco;MN|Mongolia|Asia/Ulaanbaatar,Asia/Hovd;ME|Montenegro|Europe/Podgorica;MS|Montserrat|America/Montserrat;MA|Morocco|Africa/Casablanca;MZ|Mozambique|Africa/Maputo;MM|Myanmar (Burma)|Asia/Yangon;NA|Namibia|Africa/Windhoek;NR|Nauru|Pacific/Nauru;NP|Nepal|Asia/Kathmandu;NL|Netherlands|Europe/Amsterdam;NC|New Caledonia|Pacific/Noumea;NZ|New Zealand|Pacific/Auckland,Pacific/Chatham;NI|Nicaragua|America/Managua;NE|Niger|Africa/Niamey;NG|Nigeria|Africa/Lagos;NU|Niue|Pacific/Niue;NF|Norfolk Island|Pacific/Norfolk;KP|North Korea|Asia/Pyongyang;MK|North Macedonia|Europe/Skopje;MP|Northern Mariana Islands|Pacific/Saipan;NO|Norway|Europe/Oslo;OM|Oman|Asia/Muscat;PK|Pakistan|Asia/Karachi;PW|Palau|Pacific/Palau;PS|Palestine|Asia/Gaza,Asia/Hebron;PA|Panama|America/Panama;PG|Papua New Guinea|Pacific/Port_Moresby,Pacific/Bougainville;PY|Paraguay|America/Asuncion;PE|Peru|America/Lima;PH|Philippines|Asia/Manila;PN|Pitcairn|Pacific/Pitcairn;PL|Poland|Europe/Warsaw;PT|Portugal|Europe/Lisbon,Atlantic/Madeira,Atlantic/Azores;PR|Puerto Rico|America/Puerto_Rico;QA|Qatar|Asia/Qatar;RO|Romania|Europe/Bucharest;RU|Russia|Europe/Kaliningrad,Europe/Moscow,Europe/Kirov,Europe/Volgograd,Europe/Astrakhan,Europe/Saratov,Europe/Ulyanovsk,Europe/Samara,Asia/Yekaterinburg,Asia/Omsk,Asia/Novosibirsk,Asia/Barnaul,Asia/Tomsk,Asia/Novokuznetsk,Asia/Krasnoyarsk,Asia/Irkutsk,Asia/Chita,Asia/Yakutsk,Asia/Khandyga,Asia/Vladivostok,Asia/Ust-Nera,Asia/Magadan,Asia/Sakhalin,Asia/Srednekolymsk,Asia/Kamchatka,Asia/Anadyr;RW|Rwanda|Africa/Kigali;RE|Réunion|Indian/Reunion;AS|Samoa (American)|Pacific/Pago_Pago;WS|Samoa (western)|Pacific/Apia;SM|San Marino|Europe/San_Marino;ST|Sao Tome & Principe|Africa/Sao_Tome;SA|Saudi Arabia|Asia/Riyadh;SN|Senegal|Africa/Dakar;RS|Serbia|Europe/Belgrade;SC|Seychelles|Indian/Mahe;SL|Sierra Leone|Africa/Freetown;SG|Singapore|Asia/Singapore;SK|Slovakia|Europe/Bratislava;SI|Slovenia|Europe/Ljubljana;SB|Solomon Islands|Pacific/Guadalcanal;SO|Somalia|Africa/Mogadishu;ZA|South Africa|Africa/Johannesburg;GS|South Georgia & the South Sandwich Islands|Atlantic/South_Georgia;KR|South Korea|Asia/Seoul;SS|South Sudan|Africa/Juba;ES|Spain|Europe/Madrid,Africa/Ceuta,Atlantic/Canary;LK|Sri Lanka|Asia/Colombo;BL|St Barthelemy|America/St_Barthelemy;SH|St Helena|Atlantic/St_Helena;KN|St Kitts & Nevis|America/St_Kitts;LC|St Lucia|America/St_Lucia;SX|St Maarten (Dutch)|America/Lower_Princes;MF|St Martin (French)|America/Marigot;PM|St Pierre & Miquelon|America/Miquelon;VC|St Vincent|America/St_Vincent;SD|Sudan|Africa/Khartoum;SR|Suriname|America/Paramaribo;SJ|Svalbard & Jan Mayen|Arctic/Longyearbyen;SE|Sweden|Europe/Stockholm;CH|Switzerland|Europe/Zurich;SY|Syria|Asia/Damascus;TW|Taiwan|Asia/Taipei;TJ|Tajikistan|Asia/Dushanbe;TZ|Tanzania|Africa/Dar_es_Salaam;TH|Thailand|Asia/Bangkok;TG|Togo|Africa/Lome;TK|Tokelau|Pacific/Fakaofo;TO|Tonga|Pacific/Tongatapu;TT|Trinidad & Tobago|America/Port_of_Spain;TN|Tunisia|Africa/Tunis;TM|Turkmenistan|Asia/Ashgabat;TC|Turks & Caicos Is|America/Grand_Turk;TV|Tuvalu|Pacific/Funafuti;TR|Türkiye|Europe/Istanbul;UM|US minor outlying islands|Pacific/Midway,Pacific/Wake;UG|Uganda|Africa/Kampala;UA|Ukraine|Europe/Simferopol,Europe/Kyiv;AE|United Arab Emirates|Asia/Dubai;GB|United Kingdom|Europe/London;US|United States|America/New_York,America/Detroit,America/Kentucky/Louisville,America/Kentucky/Monticello,America/Indiana/Indianapolis,America/Indiana/Vincennes,America/Indiana/Winamac,America/Indiana/Marengo,America/Indiana/Petersburg,America/Indiana/Vevay,America/Chicago,America/Indiana/Tell_City,America/Indiana/Knox,America/Menominee,America/North_Dakota/Center,America/North_Dakota/New_Salem,America/North_Dakota/Beulah,America/Denver,America/Boise,America/Phoenix,America/Los_Angeles,America/Anchorage,America/Juneau,America/Sitka,America/Metlakatla,America/Yakutat,America/Nome,America/Adak,Pacific/Honolulu;UY|Uruguay|America/Montevideo;UZ|Uzbekistan|Asia/Samarkand,Asia/Tashkent;VU|Vanuatu|Pacific/Efate;VA|Vatican City|Europe/Vatican;VE|Venezuela|America/Caracas;VN|Vietnam|Asia/Ho_Chi_Minh;VG|Virgin Islands (UK)|America/Tortola;VI|Virgin Islands (US)|America/St_Thomas;WF|Wallis & Futuna|Pacific/Wallis;EH|Western Sahara|Africa/El_Aaiun;YE|Yemen|Asia/Aden;ZM|Zambia|Africa/Lusaka;ZW|Zimbabwe|Africa/Harare;AX|Åland Islands|Europe/Mariehamn";
  var TZ_ALIAS = { 'Asia/Calcutta': 'Asia/Kolkata', 'Asia/Saigon': 'Asia/Ho_Chi_Minh', 'Asia/Katmandu': 'Asia/Kathmandu',
    'Europe/Kiev': 'Europe/Kyiv', 'Asia/Rangoon': 'Asia/Yangon', 'America/Buenos_Aires': 'America/Argentina/Buenos_Aires',
    'America/Godthab': 'America/Nuuk', 'Atlantic/Faeroe': 'Atlantic/Faroe', 'Etc/UTC': 'UTC', 'Etc/GMT': 'UTC', 'GMT': 'UTC',
    'America/Indianapolis': 'America/Indiana/Indianapolis', 'America/Louisville': 'America/Kentucky/Louisville',
    'Asia/Ulan_Bator': 'Asia/Ulaanbaatar', 'Pacific/Enderbury': 'Pacific/Kanton', 'Europe/Uzhgorod': 'Europe/Kyiv', 'Europe/Zaporozhye': 'Europe/Kyiv' };
  var TZ_WORDS = { GB: 'uk england scotland wales britain', US: 'usa america', AE: 'uae emirates dubai', NL: 'holland', CZ: 'czech republic',
    KR: 'korea', CN: 'china beijing', CH: 'swiss', DE: 'germany', TR: 'turkey', CI: 'ivory coast' };
  var tzRows = null;
  function fold(s) { return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
  function tzCity(z) {
    var p = z.split('/'), c = p[p.length - 1].replace(/_/g, ' ');
    return p.length > 2 && p[1] !== 'Argentina' ? c + ' (' + p[1].replace(/_/g, ' ') + ')' : c;
  }
  function tzList() {
    if (tzRows) return tzRows;
    tzRows = [{ id: 'UTC', cc: '', country: 'UTC', city: 'Coordinated Universal Time' }];
    TZ_DATA.split(';').forEach(function (part) {
      var p = part.split('|');
      p[2].split(',').forEach(function (z) { tzRows.push({ id: z, cc: p[0], country: p[1], city: tzCity(z) }); });
    });
    tzRows.forEach(function (r) { r.key = ' ' + fold([r.country, r.cc, r.city, r.id.replace(/[_/]/g, ' '), TZ_WORDS[r.cc] || ''].join(' ')); });
    return tzRows;
  }
  function tzFind(id) { var l = tzList(); for (var i = 0; i < l.length; i++) if (l[i].id === id) return l[i]; return null; }
  function tzClock(r, now) {
    if (r.fmt === undefined) {
      var o = { timeZone: r.id, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' };
      try { r.fmt = new Intl.DateTimeFormat('en-GB', Object.assign({ timeZoneName: 'shortOffset' }, o)); }
      catch (e) { try { r.fmt = new Intl.DateTimeFormat('en-GB', o); } catch (e2) { r.fmt = null; } }
    }
    r.off = ''; r.time = '';
    if (!r.fmt) return;
    var v = {};
    r.fmt.formatToParts(now).forEach(function (p) { v[p.type] = p.value; });
    r.off = v.timeZoneName ? v.timeZoneName.replace(/^GMT$/, 'GMT+0') : '';
    r.time = v.hour + ':' + v.minute;
  }
  // "gmt+3", "UTC-05:00", "+5:30" → "+3", "-5", "+5:30"; anything else → null.
  function tzOffNorm(s) {
    var m = String(s).replace(/^(gmt|utc)/i, '').match(/^([+-])0?(\d{1,2})(?::?(\d\d))?$/);
    return m ? m[1] + (+m[2]) + (m[3] && m[3] !== '00' ? ':' + m[3] : '') : null;
  }
  PP.tzCanon = function (z) { return TZ_ALIAS[z] || z || 'UTC'; };
  PP.tzLabel = function (z) { var r = tzFind(z); return !r ? (z || '') : r.cc ? r.country + ' — ' + r.city : 'UTC'; };
  PP.tzField = function (name, value, id) {
    value = PP.tzCanon(value);
    return '<div class="pp-tz"><input type="hidden" name="' + PP.esc(name) + '" value="' + PP.esc(value) + '">' +
      '<input type="text" class="pp-tz-q"' + (id ? ' id="' + PP.esc(id) + '"' : '') + ' value="' + PP.esc(PP.tzLabel(value)) + '" autocomplete="off" spellcheck="false"' +
      ' role="combobox" aria-expanded="false" aria-autocomplete="list" placeholder="Search a country, city or GMT+2">' +
      PP.icon('down') + '<div class="pp-tz-list" role="listbox" hidden></div></div>';
  };
  function tzParts(box) { return { box: box, val: box.querySelector('input[type=hidden]'), q: box.querySelector('.pp-tz-q'), list: box.querySelector('.pp-tz-list') }; }
  function tzActive(t, el) {
    var old = t.list.querySelector('.pp-tz-o.on');
    if (old) old.classList.remove('on');
    if (!el) return;
    el.classList.add('on');
    var l = t.list, top = el.offsetTop, bot = top + el.offsetHeight;
    if (top < l.scrollTop) l.scrollTop = top - 4;
    else if (bot > l.scrollTop + l.clientHeight) l.scrollTop = bot - l.clientHeight + 4;
  }
  function tzRender(t, query) {
    var now = new Date(), cur = t.val.value;
    var terms = fold(query).trim().split(/\s+/).filter(Boolean);
    var rows = tzList();
    rows.forEach(function (r) { tzClock(r, now); });
    var hits = rows.filter(function (r) {
      return terms.every(function (w) {
        var off = /^(gmt|utc)?[+-]\d/.test(w) ? tzOffNorm(w) : (w === 'gmt' || w === 'utc') ? null : undefined;
        if (off) return tzOffNorm(r.off || 'x') === off;
        return r.key.indexOf(w) >= 0 || fold(r.off).indexOf(w) >= 0;
      });
    });
    if (terms.length) {
      var w = terms[0];
      var score = function (r) { var c = fold(r.country), y = fold(r.city); return c.indexOf(w) === 0 ? 0 : y.indexOf(w) === 0 ? 1 : r.key.indexOf(' ' + w) >= 0 ? 2 : 3; };
      hits = hits.map(function (r, i) { return [score(r), i, r]; }).sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; }).map(function (x) { return x[2]; });
    }
    t.list.innerHTML = hits.length ? hits.map(function (r) {
      return '<div class="pp-tz-o' + (r.id === cur ? ' sel' : '') + '" role="option" aria-selected="' + (r.id === cur) + '" data-tz="' + PP.esc(r.id) + '">' +
        '<b>' + PP.esc(r.country) + '</b><span class="c">' + PP.esc(r.city) + '</span><span class="o">' + PP.esc(r.off) + (r.time ? ' · ' + r.time : '') + '</span></div>';
    }).join('') : '<div class="pp-tz-empty">No time zone matches “' + PP.esc(query) + '”. Try a country or a city.</div>';
    t.list.hidden = false;
    t.q.setAttribute('aria-expanded', 'true');
    tzActive(t, (!terms.length && t.list.querySelector('.sel')) || t.list.querySelector('.pp-tz-o'));
  }
  // Opening empties the box (the current zone stays visible as the placeholder) so typing starts a fresh search.
  function tzOpen(t) {
    t.q.placeholder = PP.tzLabel(t.val.value) || 'Search a country, city or GMT+2';
    t.q.value = '';
    tzRender(t, '');
  }
  function tzClose(t, revert) {
    t.list.hidden = true; t.list.innerHTML = '';
    t.q.setAttribute('aria-expanded', 'false');
    if (revert) { t.q.value = PP.tzLabel(t.val.value); t.q.placeholder = 'Search a country, city or GMT+2'; }
  }
  function tzPick(t, id) {
    var changed = t.val.value !== id;
    t.val.value = id;
    tzClose(t, true);
    if (changed) t.val.dispatchEvent(new Event('change', { bubbles: true }));
  }
  function tzOf(el) { var b = el && el.closest && el.closest('.pp-tz'); return b ? tzParts(b) : null; }
  document.addEventListener('focusin', function (e) {
    if (!e.target.matches || !e.target.matches('.pp-tz-q')) return;
    tzOpen(tzOf(e.target));
  });
  document.addEventListener('click', function (e) {
    var t = tzOf(e.target);
    if (!t) return;
    var o = e.target.closest('.pp-tz-o');
    if (o) tzPick(t, o.dataset.tz);
    else if (e.target === t.q && t.list.hidden) tzOpen(t);
  });
  // Keep focus in the search box while clicking or scrolling the list.
  document.addEventListener('mousedown', function (e) { if (e.target.closest && e.target.closest('.pp-tz-list')) e.preventDefault(); });
  // Capture phase: the form's own listeners (unsaved-changes bar, Escape closing a modal) must not see the search typing.
  document.addEventListener('input', function (e) {
    if (!e.target.matches || !e.target.matches('.pp-tz-q')) return;
    e.stopPropagation(); tzRender(tzOf(e.target), e.target.value);
  }, true);
  document.addEventListener('keydown', function (e) {
    if (!e.target.matches || !e.target.matches('.pp-tz-q')) return;
    var t = tzOf(e.target), on = t.list.querySelector('.pp-tz-o.on'), open = !t.list.hidden;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!open) { tzOpen(t); return; }
      var n = on && (e.key === 'ArrowDown' ? on.nextElementSibling : on.previousElementSibling);
      if (n && n.classList.contains('pp-tz-o')) tzActive(t, n);
    } else if (e.key === 'Enter' && open) {
      e.preventDefault();
      if (on) tzPick(t, on.dataset.tz);
    } else if (e.key === 'Escape' && open) {
      e.stopPropagation(); e.preventDefault(); tzClose(t, true);
    }
  }, true);
  document.addEventListener('focusout', function (e) {
    if (e.target.matches && e.target.matches('.pp-tz-q')) tzClose(tzOf(e.target), true);
  });

  // ---------- Photos and videos (gallery, website, specials, photo of the day, events)
  // PP.upload(file, emit, meta) → Promise of the saved photo {key, url, thumb_url, ...}.
  // The page's form answers the media_* events (pp_ui.mount does it when given the restaurant id):
  //   media_ticket {kind} → where to upload: Cloudinary (signed form) or PlanPlate
  //   media_register {info, meta} (after a Cloudinary upload)   media_upload {image, thumb, ...}   media_video {poster, ...} (+ PP._file)
  //   media_list → {photos}
  PP.pickFiles = function (accept, multiple) {
    return new Promise(function (resolve) {
      var i = document.createElement('input');
      i.type = 'file'; i.accept = accept || 'image/*'; i.multiple = !!multiple;
      i.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0';
      i.onchange = function () { var f = Array.prototype.slice.call(i.files || []); i.remove(); resolve(f); };
      document.body.appendChild(i);
      i.click();
    });
  };
  function loadImg(file) {
    return new Promise(function (resolve, reject) {
      var url = URL.createObjectURL(file), img = new Image();
      img.onload = function () { resolve(img); setTimeout(function () { URL.revokeObjectURL(url); }, 1000); };
      img.onerror = function () { URL.revokeObjectURL(url); reject(new Error('That picture could not be opened. Try a JPEG or PNG.')); };
      img.src = url;
    });
  }
  // Shrink a picture on the device (phones take 4000px photos): longest side `max`, JPEG (PNG kept for logos with transparency).
  PP.shrinkImage = function (file, max, quality) {
    return loadImg(file).then(function (img) {
      var k = Math.min(1, max / Math.max(img.naturalWidth, img.naturalHeight));
      var w = Math.max(1, Math.round(img.naturalWidth * k)), h = Math.max(1, Math.round(img.naturalHeight * k));
      var cv = document.createElement('canvas'); cv.width = w; cv.height = h;
      var g = cv.getContext('2d');
      var png = file.type === 'image/png';
      if (!png) { g.fillStyle = '#fff'; g.fillRect(0, 0, w, h); }
      g.drawImage(img, 0, 0, w, h);
      var type = png ? 'image/png' : 'image/jpeg';
      var dataUrl = cv.toDataURL(type, quality || 0.85);
      if (png && dataUrl.length > 4500000) { type = 'image/jpeg'; dataUrl = cv.toDataURL(type, quality || 0.85); }
      return new Promise(function (resolve) {
        if (!cv.toBlob) return resolve({ dataUrl: dataUrl, w: w, h: h, blob: null });
        cv.toBlob(function (blob) { resolve({ dataUrl: dataUrl, w: w, h: h, blob: blob }); }, type, quality || 0.85);
      });
    });
  };
  function videoPoster(file) {
    return new Promise(function (resolve) {
      var v = document.createElement('video'), url = URL.createObjectURL(file), done = false;
      function finish(x) { if (done) return; done = true; URL.revokeObjectURL(url); resolve(x); }
      v.muted = true; v.playsInline = true; v.preload = 'metadata';
      v.onloadeddata = function () { try { v.currentTime = Math.min(1, (v.duration || 2) / 3); } catch (e) { finish({}); } };
      v.onseeked = function () {
        try {
          var k = Math.min(1, 1280 / Math.max(v.videoWidth, v.videoHeight)), cv = document.createElement('canvas');
          cv.width = Math.round(v.videoWidth * k); cv.height = Math.round(v.videoHeight * k);
          cv.getContext('2d').drawImage(v, 0, 0, cv.width, cv.height);
          finish({ dataUrl: cv.toDataURL('image/jpeg', 0.8), w: v.videoWidth, h: v.videoHeight });
        } catch (e) { finish({}); }
      };
      v.onerror = function () { finish({}); };
      setTimeout(function () { finish({}); }, 5000);
      v.src = url;
    });
  }
  PP.upload = function (file, pyEmit, meta) {
    meta = meta || {};
    var emit = function (name, payload) { try { return Promise.resolve(pyEmit(name, JSON.stringify(payload || {}))); } catch (e) { return Promise.reject(e); } };
    var video = /^video\//.test(file.type || '');
    if (!video && !/^image\//.test(file.type || '')) return Promise.reject(new Error('“' + (file.name || 'That file') + '” is not a photo or a video.'));
    return emit('media_ticket', { kind: video ? 'video' : 'image' }).then(function (t) {
      if (!t || t.ok === false) throw new Error((t && t.error) || 'Upload failed.');
      var maxMb = video ? t.max_video_mb : t.max_image_mb;
      if (video && file.size > maxMb * 1048576) throw new Error('That video is ' + Math.round(file.size / 1048576) + ' MB; the limit is ' + maxMb + ' MB. Shorten it, or use a YouTube link.');
      if (t.provider === 'cloudinary') {
        var body = video ? Promise.resolve(file) : PP.shrinkImage(file, 2000, 0.88).then(function (s) { return s.blob || file; });
        return body.then(function (blob) {
          var fd = new FormData();
          Object.keys(t.fields).forEach(function (k) { fd.append(k, t.fields[k]); });
          fd.append('file', blob, file.name || 'upload');
          return fetch(t.url, { method: 'POST', body: fd }).then(function (r) { return r.json(); }).then(function (info) {
            if (!info || info.error) throw new Error((info && info.error && info.error.message) || 'The photo host refused that file.');
            return emit('media_register', { info: info, meta: meta });
          });
        });
      }
      if (video) {
        return videoPoster(file).then(function (pv) {
          PP._file = file;
          return emit('media_video', Object.assign({ poster: pv.dataUrl || null, width: pv.w || null, height: pv.h || null, type: file.type, size: file.size }, meta));
        });
      }
      return Promise.all([PP.shrinkImage(file, 1600, 0.85), PP.shrinkImage(file, 600, 0.8)]).then(function (s) {
        return emit('media_upload', Object.assign({ image: s[0].dataUrl, thumb: s[1].dataUrl, width: s[0].w, height: s[0].h }, meta));
      });
    }).then(function (res) {
      if (!res || res.ok === false) throw new Error((res && res.error) || 'Upload failed.');
      return res.photo;
    });
  };
  PP.loadScript = function (src) {
    PP._scripts = PP._scripts || {};
    if (!PP._scripts[src]) PP._scripts[src] = new Promise(function (resolve, reject) {
      var s = document.createElement('script'); s.src = src; s.onload = resolve; s.onerror = reject; document.head.appendChild(s);
    });
    return PP._scripts[src];
  };
  PP.siteBase = function () { return PP.appUrl().replace(/\/$/, '') + '/_/api/site/'; };

})();

/* Upload a File picked in Python (FileLoader -> anvil.js.to_js? no: we pick in JS so phones get the camera roll).
   PP.pickAndUpload(accept, multiple, emit, meta, onEach) -> Promise of [{ok, photo|error, name}] */
(function () {
  var PP = window.PP;
  PP.pickAndUpload = function (accept, multiple, emit, meta, onEach) {
    return PP.pickFiles(accept, multiple).then(function (files) {
      var out = [], i = 0;
      function next() {
        if (i >= files.length) return Promise.resolve(out);
        var f = files[i++];
        if (onEach) { try { onEach(i, files.length, f.name || ''); } catch (e) {} }
        return PP.upload(f, emit, meta).then(function (p) { out.push({ ok: true, photo: p, name: f.name }); },
          function (err) { out.push({ ok: false, error: PP.err(err), name: f.name }); }).then(next);
      }
      return next();
    });
  };
  PP.browserTz = function () { try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'; } catch (e) { return 'UTC'; } };
  PP.scrollToId = function (id) { var el = document.getElementById(id); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' }); };
  PP.download = function (text, filename, type) {
    var a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type: type || 'text/plain' }));
    a.download = filename; document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  };
})();

(function () {
  var PP = window.PP;
  // An .ics calendar file for the reservation (floating local time, like the booking itself).
  PP.ics = function (res, restaurant, link) {
    function stamp(date, min) { return date.replace(/-/g, '') + 'T' + PP.hm(min).replace(':', '') + '00'; }
    function clean(s) { return String(s || '').replace(/[\\;,]/g, function (c) { return '\\' + c; }).replace(/\n/g, '\\n'); }
    var now = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+/, '');
    var body = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//PlanPlate//Reservations//EN', 'BEGIN:VEVENT', 'UID:' + res.token + '@planplate', 'DTSTAMP:' + now,
      'DTSTART:' + stamp(res.date, res.start_min), 'DTEND:' + stamp(res.date, res.start_min + res.duration),
      'SUMMARY:' + clean('Table at ' + restaurant.name), 'LOCATION:' + clean(restaurant.address),
      'DESCRIPTION:' + clean(res.party + ' guests. Change or cancel: ' + link), 'END:VEVENT', 'END:VCALENDAR'].join('\r\n');
    var a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([body], { type: 'text/calendar' }));
    a.download = 'reservation.ics';
    document.body.appendChild(a); a.click(); a.remove();
  };

})();
