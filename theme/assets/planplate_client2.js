/* PlanPlate's OLD embed script (client.planplate.com/_/theme/planplate_client2.js and planplate_client.js), kept so
   restaurant websites that pasted the old code keep working after the move to the new PlanPlate. Same names as before:

     <button iframe_launcher="<old id>">Reserve</button>      a booking pop-up ("<old id>/en" picks the language)
     open_reservation_iframe("<old id>")                     the older script's way to open it
     <div restaurant="<old id>"></div> + get_work_hours("en")  opening hours
     <div menus="<old id>"></div> + get_menu_links("en")       links to the menu files (menu="..." works too)

   Everything is asked of the PlanPlate this file was loaded from (Legacy.py answers the old addresses).
   New websites should use /_/api/embed.js instead (Share & QR page). */
(function () {
  'use strict';
  var me = document.currentScript && document.currentScript.src;
  var BASE = 'https://client.planplate.com';
  try { if (me) BASE = new URL(me).origin; } catch (e) {}

  var style = document.createElement('style');
  style.textContent = '@keyframes pp-old-blink{0%,80%,100%{opacity:.3;transform:scale(1)}40%{opacity:1;transform:scale(1.4)}}';
  (document.head || document.documentElement).appendChild(style);

  function modalFor(ref) {
    var id = 'planplate-' + ref;
    var modal = document.getElementById(id);
    if (modal) return modal;
    modal = document.createElement('div');
    modal.id = id;
    Object.assign(modal.style, { display: 'none', position: 'fixed', zIndex: 2000, left: 0, top: 0, width: '100%', height: '100%',
      backgroundColor: 'rgba(0, 0, 0, 0.7)' });
    var box = document.createElement('div');
    Object.assign(box.style, { position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', backgroundColor: '#fefefe',
      maxWidth: '650px', width: '92vw', height: '90vh', boxShadow: '0 4px 8px 0 rgba(0,0,0,0.2)', borderRadius: '24px', overflow: 'hidden' });
    var wait = document.createElement('div');
    Object.assign(wait.style, { position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      background: '#fff', fontFamily: "Georgia, 'Times New Roman', serif", textAlign: 'center' });
    wait.innerHTML = '<div style="font-size:2.2rem;color:#1f1d1a;margin-bottom:.25rem">PlanPlate</div>' +
      '<div style="font:1rem system-ui,sans-serif;color:#6b6358;margin-bottom:1rem">Reservations made simple</div><div style="display:flex;gap:8px">' +
      [0, .2, .4].map(function (d) { return '<div style="width:10px;height:10px;border-radius:50%;background:#a8834a;animation:pp-old-blink 1.4s infinite ' + d + 's"></div>'; }).join('') + '</div>';
    var close = document.createElement('button');
    close.type = 'button'; close.setAttribute('aria-label', 'Close'); close.innerHTML = '&times;';
    Object.assign(close.style, { position: 'absolute', top: '10px', right: '10px', width: '32px', height: '32px', border: 0, borderRadius: '50%',
      background: '#1f1d1a', color: '#fff', font: 'bold 20px/32px system-ui,sans-serif', cursor: 'pointer', zIndex: 2 });
    var frame = document.createElement('iframe');
    frame.title = 'Book a table';
    frame.src = BASE + '/restaurant/' + ref;
    Object.assign(frame.style, { position: 'absolute', inset: 0, width: '100%', height: '100%', border: 'none' });
    frame.addEventListener('load', function () { wait.style.display = 'none'; });
    box.appendChild(wait); box.appendChild(frame); box.appendChild(close); modal.appendChild(box);
    (document.body || document.documentElement).appendChild(modal);
    function hide() { modal.style.display = 'none'; document.documentElement.style.overflow = ''; }
    close.addEventListener('click', hide);
    modal.addEventListener('click', function (e) { if (e.target === modal) hide(); });
    window.addEventListener('message', function (e) {
      if (e.origin !== BASE || e.source !== frame.contentWindow) return;
      if (e.data === 'close_div' || (e.data && e.data.planplate === 'close')) {
        hide();
        wait.style.display = 'flex';
        var src = frame.src; frame.src = 'about:blank'; setTimeout(function () { frame.src = src; }, 50);  // a fresh form next time
      }
    });
    return modal;
  }

  function show(ref) {
    var m = modalFor(ref);
    m.style.display = 'block';
    document.documentElement.style.overflow = 'hidden';
  }

  function create_iframes() {
    document.querySelectorAll('[iframe_launcher]').forEach(function (el) {
      var ref = String(el.getAttribute('iframe_launcher') || '').trim();
      if (!ref) return;
      modalFor(ref);
      el.onclick = function (e) { if (e) e.preventDefault(); show(ref); };
    });
  }

  function fill(attr, path, language) {
    document.querySelectorAll('[' + attr + ']').forEach(function (el) {
      var ref = String(el.getAttribute(attr) || '').trim();
      if (!ref) return;
      fetch(BASE + path + encodeURIComponent(ref) + '/' + encodeURIComponent(language || 'en'))
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
        .then(function (html) { el.innerHTML = html; })
        .catch(function () { el.innerHTML = 'Failed to load text.'; });
    });
  }

  window.create_iframe = modalFor;
  window.create_iframes = create_iframes;
  window.show_iframe = show;
  window.open_reservation_iframe = show;
  window.get_work_hours = function (language) { fill('restaurant', '/_/api/v1/', language); };
  window.update_work_hours = function (ref, el, language) { el.setAttribute('restaurant', ref); window.get_work_hours(language); };
  window.get_menu_links = function (language) { fill('menus', '/_/api/menus/', language); fill('menu', '/_/api/menus/', language); };
  window.update_menu_links = function (ref, el, language) { el.setAttribute('menus', ref); window.get_menu_links(language); };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', create_iframes); else create_iframes();
})();
