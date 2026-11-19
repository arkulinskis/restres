/* pp-showcase.js: <planplate-showcase>, the restaurant photo gallery for websites (PlanPlate, Nov 19 2026).
   Replaces <planplate-gallery> on PlanPlate websites and in new embeds (the old file stays for sites that use it).

   On any website:
     <planplate-showcase restaurant="maison-lumiere"></planplate-showcase>
     <script src="https://<planplate>/_/theme/pp-showcase.js" defer></script>
   The look comes from the restaurant's Gallery page (feed /_/api/showcase/<restaurant>: {style, photos}), so a change
   there shows everywhere at once. Attributes: restaurant | feed-url, origin (when the script is served elsewhere),
   look='{"layout":"spotlight"}' (overrides the saved look: the Gallery page's live preview), no-heading, fresh (no cache).

   Layouts: mosaic (justified rows), masonry, spotlight (big photo + strip), slideshow (cinematic, slow zoom),
   carousel (swipe row), editorial (magazine), grid (even squares), polaroid (prints on a table).
   Every layout: lightbox (swipe, arrows, Esc), captions, corners, gaps, frames, hover and scroll motion; reduced motion
   is respected; everything lives in a shadow root, so the website's CSS can't break it (and it can't break the site). */
(function () {
  'use strict';
  if (!window.customElements || customElements.get('planplate-showcase')) return;
  var ME = document.currentScript;
  var ORIGIN = '';
  try { ORIGIN = new URL(ME.src).origin; } catch (e) { ORIGIN = location.origin; }

  var DEF = { layout: 'mosaic', tone: 'page', gap: 'tight', corners: 'soft', frame: 'none', captions: 'hover', hover: 'zoom',
              show: 'all', lightbox: 'on', autoplay: 'on', size: 'md', motion: 'rise', accent: '#c9a56a', background: '#1d1b18', heading: '' };
  // per size: mosaic row height, grid/masonry/polaroid column width, carousel height (px)
  var SIZE = { xs: [150, 150, 280], sm: [190, 190, 340], md: [240, 240, 420], lg: [300, 300, 500], xl: [380, 380, 580] };
  var GAP = { none: 0, tight: 6, airy: 18 };
  var RAD = { square: 0, soft: 10, round: 22 };
  var LIMITED = { mosaic: 1, masonry: 1, grid: 1, editorial: 1, polaroid: 1 };
  var WORDS = {
    en: { all: 'See all %d photos', less: 'Show fewer', close: 'Close', prev: 'Previous photo', next: 'Next photo', open: 'Open photo', photos: 'Photos', none: 'No photos yet.' },
    fr: { all: 'Voir les %d photos', less: 'Voir moins', close: 'Fermer', prev: 'Photo précédente', next: 'Photo suivante', open: 'Ouvrir la photo', photos: 'Photos', none: 'Pas encore de photos.' },
    lv: { all: 'Skatīt visas %d fotogrāfijas', less: 'Rādīt mazāk', close: 'Aizvērt', prev: 'Iepriekšējā', next: 'Nākamā', open: 'Atvērt fotogrāfiju', photos: 'Fotogrāfijas', none: 'Fotogrāfiju vēl nav.' }
  };
  var reduce = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : { matches: false };

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; });
  }
  function lum(hex) {
    var m = /^#?([0-9a-f]{6})$/i.exec(hex || '');
    if (!m) return 0;
    var n = parseInt(m[1], 16), c = [n >> 16 & 255, n >> 8 & 255, n & 255].map(function (v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  }
  function words() {
    var l = (document.documentElement.lang || 'en').slice(0, 2).toLowerCase();
    return WORDS[l] || WORDS.en;
  }
  var ICON = {
    prev: '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M15 5l-7 7 7 7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    next: '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M9 5l7 7-7 7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    x: '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>'
  };

  var CSS = [
    ':host{display:block;container-type:inline-size}',
    '*{box-sizing:border-box}',
    '.ps{--e:cubic-bezier(.2,.8,.2,1);background:var(--bg);color:var(--ink);font:inherit;position:relative}',
    '.ps.t-light,.ps.t-dark,.ps.t-custom{padding:clamp(14px,3.5cqi,40px);border-radius:var(--box-rad,0)}',
    '.ps-h{margin:0 0 .9em;text-align:center;font:inherit;font-size:clamp(1.35rem,3.2cqi,2.1rem);font-weight:500;letter-spacing:-.01em;line-height:1.15}',
    '.ps-empty{text-align:center;opacity:.7;padding:2em 0;margin:0}',
    'figure{margin:0}',
    '.ps-it{position:relative;margin:0;outline:none}',
    '.ps-it[role=button]{cursor:zoom-in}',
    '.ps-it:focus-visible .ps-ph{outline:3px solid var(--acc);outline-offset:3px}',
    '.ps-ph{position:relative;overflow:hidden;border-radius:var(--rad);background:color-mix(in srgb,currentColor 8%,transparent)}',
    '.ps-ph img{display:block;width:100%;height:100%;object-fit:cover;transition:transform .7s var(--e),filter .4s var(--e)}',
    '.h-zoom .ps-it:hover .ps-ph img,.h-zoom .ps-it:focus-visible .ps-ph img{transform:scale(1.06)}',
    '.h-lift .ps-it{transition:transform .3s var(--e)}.h-lift .ps-it:hover{transform:translateY(-4px)}',
    '.h-lift .ps-it:hover .ps-ph{box-shadow:0 18px 40px -18px rgba(0,0,0,.55)}',
    '.f-shadow .ps-ph{box-shadow:0 14px 34px -16px rgba(0,0,0,.55)}',
    '.f-matte .ps-ph{padding:clamp(5px,1.2cqi,10px);background:#fbfaf7;box-shadow:0 1px 2px rgba(0,0,0,.12),0 12px 28px -18px rgba(0,0,0,.5)}',
    '.f-matte .ps-ph img{border-radius:calc(var(--rad)*.6)}',
    /* captions */
    'figcaption{font-size:.88em;line-height:1.4}',
    '.c-off .ps-it figcaption{display:none}',
    '.c-below .ps-it figcaption{padding:.55em .15em 0;opacity:.8}',
    '.c-hover .ps-it figcaption{position:absolute;left:0;right:0;bottom:0;padding:2.2em .9em .75em;color:#fff;border-radius:0 0 var(--rad) var(--rad);background:linear-gradient(transparent,rgba(0,0,0,.62));opacity:0;transform:translateY(6px);transition:opacity .3s var(--e),transform .3s var(--e);pointer-events:none}',
    '.c-hover .ps-it:hover figcaption,.c-hover .ps-it:focus-visible figcaption{opacity:1;transform:none}',
    '@media (hover:none){.c-hover .ps-it figcaption{opacity:1;transform:none}}',
    '.f-matte.c-hover .ps-it figcaption{margin:0 clamp(5px,1.2cqi,10px) clamp(5px,1.2cqi,10px)}',
    /* mosaic: justified rows */
    '.l-mosaic .ps-wrap{display:flex;flex-wrap:wrap;gap:var(--gap)}',
    '.l-mosaic .ps-wrap::after{content:"";flex-grow:999999}',
    '.l-mosaic .ps-it{flex-grow:calc(var(--ar) * 100);flex-basis:calc(var(--ar) * var(--rowh));min-width:0}',
    '.l-mosaic .ps-ph{aspect-ratio:var(--ar)}',
    '@container (max-width:600px){.l-mosaic .ps-it{flex-basis:calc(var(--ar) * var(--rowh) * .62)}}',
    /* masonry */
    '.l-masonry .ps-wrap{columns:var(--colw);column-gap:var(--gap)}',
    '.l-masonry .ps-it{break-inside:avoid;margin-bottom:var(--gap)}',
    '.l-masonry .ps-ph{aspect-ratio:var(--ar)}',
    '@container (max-width:600px){.l-masonry .ps-wrap{columns:2}}',
    /* grid */
    '.l-grid .ps-wrap{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,var(--colw)),1fr));gap:var(--gap)}',
    '.l-grid .ps-ph{aspect-ratio:1}',
    '@container (max-width:600px){.l-grid .ps-wrap{grid-template-columns:repeat(2,minmax(0,1fr))}}',
    /* editorial: a magazine spread, repeating every five photos */
    '.l-editorial .ps-wrap{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:calc(var(--gap) + 18px) calc(var(--gap) + 6px);align-items:start}',
    '.l-editorial .ps-it{grid-column:span 2}.l-editorial .ps-ph{aspect-ratio:1}',
    '.l-editorial .e0{grid-column:span 4;grid-row:span 2}.l-editorial .e0 .ps-ph{aspect-ratio:4/3.1}',
    '.l-editorial .e1 .ps-ph{aspect-ratio:3/4}',
    '.l-editorial .ps-it figcaption{display:flex;gap:.6em;align-items:baseline;position:static;opacity:1;transform:none;background:none;color:inherit;padding:.7em 0 0;font-style:italic}',
    '.l-editorial .ps-it figcaption b{font-style:normal;font-weight:600;font-size:.78em;letter-spacing:.12em;color:var(--acc)}',
    '@container (max-width:600px){.l-editorial .ps-wrap{grid-template-columns:repeat(2,minmax(0,1fr))}.l-editorial .ps-it{grid-column:span 1}.l-editorial .e0{grid-column:span 2;grid-row:auto}}',
    /* polaroid: prints on a table */
    '.l-polaroid .ps-wrap{display:flex;flex-wrap:wrap;justify-content:center;gap:calc(var(--gap) + 16px);padding:10px 0}',
    '.l-polaroid .ps-it{width:min(var(--colw),44%);background:#fffdf8;padding:10px 10px 0;border-radius:3px;box-shadow:0 2px 3px rgba(0,0,0,.14),0 14px 30px -14px rgba(0,0,0,.5);transform:rotate(var(--rot));transition:transform .35s var(--e),box-shadow .35s var(--e)}',
    '.l-polaroid .ps-it:hover,.l-polaroid .ps-it:focus-visible{transform:rotate(0) scale(1.04);z-index:2;box-shadow:0 4px 6px rgba(0,0,0,.14),0 26px 44px -18px rgba(0,0,0,.55)}',
    '.l-polaroid .ps-ph{aspect-ratio:1;border-radius:1px;box-shadow:none;padding:0;background:#ddd}',
    '.l-polaroid .ps-it figcaption{display:block!important;position:static;opacity:1;transform:none;background:none;color:#3b352c;text-align:center;padding:.65em .2em .8em;min-height:2.6em;font:italic 500 .92em/1.3 "Segoe Print","Bradley Hand","Snell Roundhand",Georgia,serif}',
    /* carousel: a swipeable row */
    '.l-carousel .ps-wrap{display:flex;gap:var(--gap);overflow-x:auto;scroll-snap-type:x mandatory;scroll-behavior:smooth;scrollbar-width:none;padding:2px 0 6px;overscroll-behavior-x:contain}',
    '.l-carousel .ps-wrap::-webkit-scrollbar{display:none}',
    '.l-carousel .ps-it{flex:none;height:min(var(--carh),68cqi,70vh);aspect-ratio:var(--ar);max-width:88cqi;scroll-snap-align:center}',
    '.l-carousel .ps-ph{height:100%}',
    '.ps-arrows{position:absolute;inset:auto 0 50%;display:flex;justify-content:space-between;pointer-events:none;padding:0 8px}',
    '.ps-btn{pointer-events:auto;display:grid;place-items:center;width:44px;height:44px;margin:0;padding:0;border:0;border-radius:999px;background:rgba(255,255,255,.9);color:#1d1b18;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.25);transition:transform .2s var(--e),opacity .2s}',
    '.ps-btn:hover{transform:scale(1.07)}.ps-btn:focus-visible{outline:3px solid var(--acc);outline-offset:2px}',
    '.ps-btn[disabled]{opacity:0;pointer-events:none}',
    '@media (hover:none){.l-carousel .ps-arrows{display:none}}',
    /* spotlight + slideshow: one photo on a stage */
    '.ps-stage{position:relative;overflow:hidden;border-radius:var(--rad);background:#0f0e0c;touch-action:pan-y;user-select:none}',
    '.l-spotlight .ps-stage{aspect-ratio:16/10}',
    '.l-slideshow .ps-stage{aspect-ratio:21/9;min-height:280px}',
    '@container (max-width:600px){.l-slideshow .ps-stage{aspect-ratio:4/5}.l-spotlight .ps-stage{aspect-ratio:4/3.4}}',
    '.ps-slide{position:absolute;inset:0;opacity:0;transition:opacity .9s var(--e);visibility:hidden}',
    '.ps-slide.on{opacity:1;visibility:visible;z-index:1}',
    '.ps-slide .bk{position:absolute;inset:-30px;width:calc(100% + 60px);height:calc(100% + 60px);object-fit:cover;filter:blur(26px) brightness(.55) saturate(1.2)}',
    '.ps-slide .fg{position:absolute;inset:0;width:100%;height:100%;object-fit:contain}',
    '.l-slideshow .ps-slide .fg{object-fit:cover}',
    '.l-slideshow .ps-slide.on .fg{animation:ps-kb 9s linear both}',
    '@keyframes ps-kb{from{transform:scale(1.01) translate(0,0)}to{transform:scale(1.12) translate(var(--kx),var(--ky))}}',
    '.ps-cap{position:absolute;left:0;right:0;bottom:0;z-index:2;padding:3.2em clamp(16px,4cqi,40px) clamp(14px,3cqi,30px);color:#fff;background:linear-gradient(transparent,rgba(0,0,0,.6));pointer-events:none;display:flex;align-items:flex-end;gap:1em}',
    '.ps-cap p{margin:0;flex:1;font-size:clamp(1rem,2.4cqi,1.5rem);line-height:1.3;text-shadow:0 1px 8px rgba(0,0,0,.35)}',
    '.l-slideshow .ps-cap p{font-size:clamp(1.15rem,3.4cqi,2.2rem);font-style:italic}',
    '.ps-n{font-size:.8rem;letter-spacing:.12em;opacity:.85;font-variant-numeric:tabular-nums;white-space:nowrap}',
    '.c-off .ps-cap p{visibility:hidden}',
    '.ps-stage .ps-arrows{z-index:3}',
    '.ps-dots{position:absolute;z-index:3;left:0;right:0;top:14px;display:flex;justify-content:center;gap:6px}',
    '.ps-dot{width:8px;height:8px;margin:0;padding:0;border:0;border-radius:99px;background:rgba(255,255,255,.5);cursor:pointer;transition:width .3s var(--e),background-color .3s}',
    '.ps-dot.on{width:22px;background:#fff}',
    '.ps-dot:focus-visible{outline:2px solid var(--acc);outline-offset:2px}',
    '.ps-strip{display:flex;gap:6px;overflow-x:auto;padding:8px 2px 4px;scrollbar-width:thin;scroll-snap-type:x proximity}',
    '.ps-th{flex:none;width:clamp(64px,13cqi,104px);aspect-ratio:1;margin:0;padding:0;border:0;border-radius:calc(var(--rad)*.6);overflow:hidden;cursor:pointer;opacity:.55;scroll-snap-align:center;outline:2px solid transparent;outline-offset:2px;transition:opacity .25s,outline-color .25s;background:none}',
    '.ps-th img{width:100%;height:100%;object-fit:cover;display:block}',
    '.ps-th:hover{opacity:.85}.ps-th.on{opacity:1;outline-color:var(--acc)}.ps-th:focus-visible{outline-color:var(--acc);opacity:1}',
    '.ps-zoom{position:absolute;inset:0;z-index:2;cursor:zoom-in;background:none;border:0;margin:0;padding:0}',
    /* "see all" */
    '.ps-more-wrap{text-align:center;margin-top:calc(var(--gap) + 18px)}',
    '.ps-more{font:inherit;font-size:.95em;font-weight:600;padding:.8em 1.6em;border-radius:999px;border:1.5px solid var(--acc);background:transparent;color:inherit;cursor:pointer;transition:background-color .2s,color .2s}',
    '.ps-more:hover{background:var(--acc);color:#fff}.ps-more:focus-visible{outline:3px solid var(--acc);outline-offset:3px}',
    /* scroll motion */
    '.m-fade .ps-it.wait,.m-rise .ps-it.wait,.m-zoom .ps-it.wait{opacity:0}',
    '.m-rise .ps-it.wait{transform:translateY(22px)}.m-zoom .ps-it.wait{transform:scale(.94)}',
    '.ps-it.show{transition:opacity .7s var(--e),transform .7s var(--e)}',
    '.l-polaroid.m-rise .ps-it.wait{transform:rotate(var(--rot)) translateY(22px)}.l-polaroid.m-zoom .ps-it.wait{transform:rotate(var(--rot)) scale(.94)}',
    /* lightbox */
    '.ps-lb{--e:cubic-bezier(.2,.8,.2,1);position:fixed;inset:0;z-index:2147483600;display:grid;grid-template-rows:1fr auto;background:rgba(10,9,8,.94);color:#f3efe8;animation:ps-in .25s var(--e);touch-action:pan-y}',
    '.ps-lb figure{position:relative;display:grid;place-items:center;min-height:0;padding:56px clamp(8px,6vw,80px) 8px}',
    '.ps-lb img{max-width:100%;max-height:100%;object-fit:contain;border-radius:4px;box-shadow:0 30px 80px -30px rgba(0,0,0,.8);animation:ps-pop .3s var(--e)}',
    '.ps-lb-foot{display:flex;gap:16px;align-items:baseline;justify-content:center;padding:12px 20px 22px;text-align:center}',
    '.ps-lb-foot p{margin:0;max-width:60ch;font-size:1rem;line-height:1.45}',
    '.ps-lb .ps-btn{position:absolute;top:50%;transform:translateY(-50%);background:rgba(255,255,255,.12);color:#fff;box-shadow:none}',
    '.ps-lb .ps-btn:hover{background:rgba(255,255,255,.22);transform:translateY(-50%) scale(1.06)}',
    '.ps-lb .prev{left:clamp(6px,2vw,24px)}.ps-lb .next{right:clamp(6px,2vw,24px)}',
    '.ps-lb .x{top:14px;right:14px;transform:none}.ps-lb .x:hover{transform:scale(1.06)}',
    '@keyframes ps-in{from{opacity:0}}@keyframes ps-pop{from{opacity:.2;transform:scale(.97)}}',
    '@media (prefers-reduced-motion:reduce){*{animation:none!important;transition-duration:.01s!important}.ps-slide{transition:opacity .3s!important}}'
  ].join('\n');

  function figure(p, i, o) {
    var ar = p.width && p.height ? p.width / p.height : 1.5;
    ar = Math.max(0.4, Math.min(3, ar));
    var thumb = p.thumb_url || p.url, big = o.big ? p.url : thumb;
    var set = p.thumb_url && p.thumb_url !== p.url ? ' srcset="' + esc(p.thumb_url) + ' 600w, ' + esc(p.url) + ' 2000w" sizes="' + (o.sizes || '(max-width: 700px) 50vw, 33vw') + '"' : '';
    var alt = p.alt || p.caption || '';
    var cap = o.num ? '<figcaption><b>' + ('0' + (i + 1)).slice(-2) + '</b><span>' + esc(p.caption || '') + '</span></figcaption>'
      : (p.caption || o.alwaysCap ? '<figcaption>' + esc(p.caption || '') + '</figcaption>' : '');
    return '<figure class="ps-it ' + (o.cls || '') + '" data-i="' + i + '" style="--ar:' + ar.toFixed(4) + ';' + (o.style || '') + '"' +
      (o.open ? ' tabindex="0" role="button" aria-label="' + esc(o.open + (alt ? ': ' + alt : '')) + '"' : '') + '>' +
      '<div class="ps-ph"><img src="' + esc(big) + '"' + set + ' alt="' + esc(alt) + '" loading="lazy" decoding="async"></div>' + cap + '</figure>';
  }

  function Showcase() { return Reflect.construct(HTMLElement, [], Showcase); }
  Showcase.prototype = Object.create(HTMLElement.prototype);
  Showcase.prototype.constructor = Showcase;
  Object.setPrototypeOf(Showcase, HTMLElement);
  Object.defineProperty(Showcase, 'observedAttributes', { get: function () { return ['restaurant', 'feed-url', 'look', 'no-heading']; } });

  var P = Showcase.prototype;
  P.connectedCallback = function () {
    if (!this._root) {
      this._root = this.attachShadow({ mode: 'open' });
      this._all = false;
    }
    this._load();
  };
  P.disconnectedCallback = function () { this._stop(); this._closeLb(); };
  P.attributeChangedCallback = function (name, before, now) {
    if (!this._root || before === now) return;
    if (name === 'look' || name === 'no-heading') this._render(); else this._load();
  };
  P._feed = function () {
    var f = this.getAttribute('feed-url');
    if (f) return f;
    var r = (this.getAttribute('restaurant') || '').trim();
    return r ? (this.getAttribute('origin') || ORIGIN).replace(/\/$/, '') + '/_/api/showcase/' + encodeURIComponent(r) : '';
  };
  P._load = function () {
    var self = this, url = this._feed();
    if (!url) return;
    fetch(url, this.hasAttribute('fresh') ? { cache: 'no-store' } : {}).then(function (r) { return r.json(); }).then(function (d) {
      self._data = d && d.photos ? d : { photos: [], style: {} };
      self._render();
    }).catch(function () { self._data = { photos: [], style: {} }; self._render(); });
  };
  P._look = function () {
    var s = {}, k;
    for (k in DEF) s[k] = DEF[k];
    var saved = (this._data && this._data.style) || {};
    for (k in saved) if (saved[k] != null && saved[k] !== '') s[k] = saved[k];
    try { var o = JSON.parse(this.getAttribute('look') || 'null'); if (o) for (k in o) if (o[k] != null) s[k] = o[k]; } catch (e) { /* a bad look attribute: use the saved one */ }
    return s;
  };
  P._stop = function () {
    if (this._timer) clearInterval(this._timer);
    this._timer = null;
    if (this._io) this._io.disconnect();
    this._io = null;
  };

  P._render = function () {
    this._stop();
    var d = this._data;
    if (!d || !this._root) return;
    var s = this._look(), W = words(), photos = (d.photos || []).slice(), self = this;
    var sz = SIZE[s.size] || SIZE.md, bg = 'transparent', ink = 'inherit';
    if (s.tone === 'light') { bg = '#faf8f4'; ink = '#1d1b18'; }
    else if (s.tone === 'dark') { bg = '#14120f'; ink = '#f3efe8'; }
    else if (s.tone === 'custom') { bg = /^#[0-9a-f]{6}$/i.test(s.background) ? s.background : '#1d1b18'; ink = lum(bg) > 0.42 ? '#1d1b18' : '#f6f2ea'; }
    var acc = /^#[0-9a-f]{6}$/i.test(s.accent) ? s.accent : '#c9a56a';
    var vars = '--acc:' + acc + ';--bg:' + bg + ';--ink:' + ink + ';--gap:' + (GAP[s.gap] == null ? 6 : GAP[s.gap]) + 'px;--rad:' + (RAD[s.corners] == null ? 10 : RAD[s.corners]) +
      'px;--rowh:' + sz[0] + 'px;--colw:' + sz[1] + 'px;--carh:' + sz[2] + 'px';
    var motion = reduce.matches ? 'none' : ({ slide: 'rise', stagger: 'rise' }[s.motion] || s.motion);
    var layout = s.layout in { mosaic: 1, masonry: 1, spotlight: 1, slideshow: 1, carousel: 1, editorial: 1, grid: 1, polaroid: 1 } ? s.layout : 'mosaic';
    var cls = ['ps', 'l-' + layout, 'c-' + s.captions, 'h-' + s.hover, 'f-' + s.frame, 'm-' + motion, 't-' + s.tone].join(' ');
    var heading = !this.hasAttribute('no-heading') && s.heading ? '<h2 class="ps-h">' + esc(s.heading) + '</h2>' : '';
    var open = s.lightbox !== 'off' ? W.open : '';
    var body = '', more = '';
    this._photos = photos;
    if (!photos.length) {
      body = '<p class="ps-empty">' + esc(W.none) + '</p>';
    } else if (layout === 'spotlight' || layout === 'slideshow') {
      body = this._stageHtml(photos, layout, W, s);
    } else {
      var limit = LIMITED[layout] && s.show !== 'all' ? parseInt(s.show, 10) || 0 : 0;
      var shown = limit && !this._all ? photos.slice(0, limit) : photos;
      var sizes = { mosaic: '(max-width: 700px) 60vw, 34vw', masonry: '(max-width: 700px) 50vw, 30vw', grid: '(max-width: 700px) 50vw, 25vw',
                    editorial: '(max-width: 700px) 100vw, 60vw', polaroid: '(max-width: 700px) 45vw, 22vw', carousel: '(max-width: 700px) 90vw, 50vw' }[layout];
      body = '<div class="ps-wrap">' + shown.map(function (p, i) {
        var o = { open: open, sizes: sizes, big: layout === 'carousel' || (layout === 'editorial' && i % 5 === 0) || s.size === 'xl' };
        if (layout === 'editorial') { o.cls = 'e' + (i % 5); o.num = true; }
        if (layout === 'polaroid') { o.style = '--rot:' + [-3.2, 2.1, -1.4, 3, -2.4, 1.2, -0.6][i % 7] + 'deg'; o.alwaysCap = true; }
        return figure(p, i, o);
      }).join('') + '</div>';
      if (layout === 'carousel') body += '<div class="ps-arrows"><button class="ps-btn" data-go="-1" aria-label="' + esc(W.prev) + '">' + ICON.prev + '</button><button class="ps-btn" data-go="1" aria-label="' + esc(W.next) + '">' + ICON.next + '</button></div>';
      if (limit && photos.length > limit) {
        more = '<div class="ps-more-wrap"><button class="ps-more" type="button">' + esc(this._all ? W.less : W.all.replace('%d', photos.length)) + '</button></div>';
      }
    }
    this._root.innerHTML = '<style>' + CSS + '</style><div class="' + cls + '" style="' + vars + '" role="region" aria-label="' + esc(s.heading || W.photos) + '">' + heading + body + more + '</div>';
    this._wire(layout, s);
  };

  P._stageHtml = function (photos, layout, W, s) {
    var slides = photos.map(function (p, i) {
      var k = [[-2, -1.5], [2, -1], [-1.5, 1.5], [1.5, 1.2], [0, -2]][i % 5];
      return '<figure class="ps-slide' + (i === 0 ? ' on' : '') + '" data-s="' + i + '" style="--kx:' + k[0] + '%;--ky:' + k[1] + '%"' + (i ? ' aria-hidden="true"' : '') + '>' +
        (layout === 'spotlight' ? '<img class="bk" src="' + esc(p.thumb_url || p.url) + '" alt="" loading="lazy" decoding="async">' : '') +
        '<img class="fg" src="' + esc(p.url) + '" alt="' + esc(p.alt || p.caption || '') + '"' + (i > 1 ? ' loading="lazy"' : '') + ' decoding="async"></figure>';
    }).join('');
    var n = photos.length;
    var html = '<div class="ps-stage" tabindex="0" aria-roledescription="carousel">' + slides +
      (s.lightbox !== 'off' ? '<button class="ps-zoom" type="button" aria-label="' + esc(W.open) + '"></button>' : '') +
      '<div class="ps-cap"><p></p><span class="ps-n"></span></div>' +
      (n > 1 ? '<div class="ps-arrows"><button class="ps-btn" data-step="-1" aria-label="' + esc(W.prev) + '">' + ICON.prev + '</button><button class="ps-btn" data-step="1" aria-label="' + esc(W.next) + '">' + ICON.next + '</button></div>' : '') +
      (layout === 'slideshow' && n > 1 && n <= 24 ? '<div class="ps-dots">' + photos.map(function (p, i) { return '<button class="ps-dot' + (i ? '' : ' on') + '" data-to="' + i + '" aria-label="' + (i + 1) + ' / ' + n + '"></button>'; }).join('') + '</div>' : '') +
      '</div>';
    if (layout === 'spotlight' && n > 1) {
      html += '<div class="ps-strip">' + photos.map(function (p, i) {
        return '<button class="ps-th' + (i ? '' : ' on') + '" data-to="' + i + '" aria-label="' + (i + 1) + ' / ' + n + (p.caption ? ': ' + esc(p.caption) : '') + '"><img src="' + esc(p.thumb_url || p.url) + '" alt="" loading="lazy" decoding="async"></button>';
      }).join('') + '</div>';
    }
    return html;
  };

  P._wire = function (layout, s) {
    var self = this, root = this._root, box = root.querySelector('.ps');
    if (!box) return;
    // open the lightbox from a photo (click, Enter, Space)
    box.addEventListener('click', function (e) {
      var more = e.target.closest('.ps-more');
      if (more) { self._all = !self._all; self._render(); return; }
      var go = e.target.closest('[data-go]');
      if (go) { var w = root.querySelector('.ps-wrap'); w.scrollBy({ left: (+go.dataset.go) * w.clientWidth * 0.8, behavior: reduce.matches ? 'auto' : 'smooth' }); return; }
      var step = e.target.closest('[data-step]');
      if (step) { self._go(self._i + (+step.dataset.step), true); return; }
      var to = e.target.closest('[data-to]');
      if (to) { self._go(+to.dataset.to, true); return; }
      if (e.target.closest('.ps-zoom')) { if (Date.now() - (self._swipeAt || 0) > 400) self._openLb(self._i); return; }
      var it = e.target.closest('.ps-it[role=button]');
      if (it) self._openLb(+it.dataset.i);
    });
    box.addEventListener('keydown', function (e) {
      var it = e.target.closest && e.target.closest('.ps-it[role=button]');
      if (it && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); self._openLb(+it.dataset.i); }
      if (e.target.classList && e.target.classList.contains('ps-stage')) {
        if (e.key === 'ArrowRight') self._go(self._i + 1, true);
        if (e.key === 'ArrowLeft') self._go(self._i - 1, true);
      }
    });
    if (layout === 'carousel') {
      var w = root.querySelector('.ps-wrap'), bs = root.querySelectorAll('[data-go]');
      var edge = function () {
        if (!bs.length) return;
        bs[0].disabled = w.scrollLeft < 4;
        bs[1].disabled = w.scrollLeft + w.clientWidth > w.scrollWidth - 4;
      };
      w.addEventListener('scroll', edge, { passive: true });
      setTimeout(edge, 60);
    }
    if (layout === 'spotlight' || layout === 'slideshow') {
      this._i = 0;
      this._go(0, false);
      var stage = root.querySelector('.ps-stage'), x0 = null;
      stage.addEventListener('pointerdown', function (e) { x0 = e.clientX; });
      stage.addEventListener('pointerup', function (e) {
        if (x0 == null) return;
        var dx = e.clientX - x0; x0 = null;
        if (Math.abs(dx) > 40) { self._swipeAt = Date.now(); self._go(self._i + (dx < 0 ? 1 : -1), true); }
      });
      var hold = function (on) { self._paused = on; };
      stage.addEventListener('pointerenter', function () { hold(true); });
      stage.addEventListener('pointerleave', function () { hold(false); });
      stage.addEventListener('focusin', function () { hold(true); });
      stage.addEventListener('focusout', function () { hold(false); });
      if (s.autoplay !== 'off' && this._photos.length > 1 && !reduce.matches) {
        this._timer = setInterval(function () {
          if (!self._paused && !document.hidden && self._visible !== false && !self._lb) self._go(self._i + 1, false);
        }, layout === 'slideshow' ? 6500 : 5000);
      }
    }
    // only animate what is on screen; pause the slideshow when it's scrolled away
    if ('IntersectionObserver' in window) {
      var items = Array.prototype.slice.call(root.querySelectorAll('.ps-wrap .ps-it'));
      var animate = !box.classList.contains('m-none') && layout !== 'carousel';
      if (animate) items.forEach(function (it) { it.classList.add('wait'); });
      this._io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.target === box) { self._visible = en.isIntersecting; return; }
          if (!en.isIntersecting) return;
          var it = en.target, n = items.indexOf(it);
          it.style.transitionDelay = (n % 6) * 60 + 'ms';
          it.classList.add('show');
          it.classList.remove('wait');
          self._io.unobserve(it);
        });
      }, { rootMargin: '0px 0px -6% 0px', threshold: 0.08 });
      this._io.observe(box);
      if (animate) items.forEach(function (it) { self._io.observe(it); });
    }
  };

  P._go = function (i, user) {
    var n = this._photos.length;
    if (!n) return;
    i = ((i % n) + n) % n;
    this._i = i;
    var root = this._root, p = this._photos[i];
    Array.prototype.forEach.call(root.querySelectorAll('.ps-slide'), function (el) {
      var on = +el.dataset.s === i;
      el.classList.toggle('on', on);
      if (on) el.removeAttribute('aria-hidden'); else el.setAttribute('aria-hidden', 'true');
      if (on) { var img = el.querySelector('.fg'); if (img) img.removeAttribute('loading'); }
    });
    Array.prototype.forEach.call(root.querySelectorAll('[data-to]'), function (el) { el.classList.toggle('on', +el.dataset.to === i); });
    var th = root.querySelector('.ps-th.on');
    if (th && user) th.scrollIntoView({ block: 'nearest', inline: 'center', behavior: reduce.matches ? 'auto' : 'smooth' });
    var cap = root.querySelector('.ps-cap p'), num = root.querySelector('.ps-n');
    if (cap) cap.textContent = p.caption || '';
    if (num) num.textContent = (i + 1) + ' / ' + n;
    var nxt = root.querySelector('.ps-slide[data-s="' + ((i + 1) % n) + '"] .fg');
    if (nxt) nxt.removeAttribute('loading');  // the next photo is ready before it's needed
  };

  // ---------------------------------------------------------------- lightbox
  P._openLb = function (i) {
    if (this._lb || this._look().lightbox === 'off') return;
    var self = this, W = words(), n = this._photos.length;
    var lb = document.createElement('div');
    lb.className = 'ps-lb';
    lb.setAttribute('role', 'dialog'); lb.setAttribute('aria-modal', 'true'); lb.setAttribute('aria-label', W.photos);
    lb.style.setProperty('--acc', this._look().accent || '#c9a56a');
    lb.innerHTML = '<figure><img alt=""></figure><div class="ps-lb-foot"><p></p><span class="ps-n"></span></div>' +
      (n > 1 ? '<button class="ps-btn prev" aria-label="' + esc(W.prev) + '">' + ICON.prev + '</button><button class="ps-btn next" aria-label="' + esc(W.next) + '">' + ICON.next + '</button>' : '') +
      '<button class="ps-btn x" aria-label="' + esc(W.close) + '">' + ICON.x + '</button>';
    // the lightbox lives in its own little shadow root on <body>, so no container on the website can trap it
    var host = document.createElement('div'), shade = host.attachShadow({ mode: 'open' });
    shade.innerHTML = '<style>' + CSS.replace(':host{display:block;container-type:inline-size}', '') + '</style>';
    shade.appendChild(lb);
    document.body.appendChild(host);
    this._lb = { el: host, shade: shade, i: i, back: document.activeElement === this ? this._root.activeElement : document.activeElement, overflow: document.documentElement.style.overflow };
    document.documentElement.style.overflow = 'hidden';
    var show = function (k) {
      k = ((k % n) + n) % n;
      self._lb.i = k;
      var p = self._photos[k], img = lb.querySelector('img');
      img.src = p.url; img.alt = p.alt || p.caption || '';
      img.style.animation = 'none'; void img.offsetWidth; img.style.animation = '';
      lb.querySelector('.ps-lb-foot p').textContent = p.caption || '';
      lb.querySelector('.ps-n').textContent = (k + 1) + ' / ' + n;
      [k + 1, k - 1].forEach(function (j) { var q = self._photos[((j % n) + n) % n]; if (q) { var pre = new Image(); pre.src = q.url; } });
    };
    this._lb.show = show;
    show(i);
    lb.addEventListener('click', function (e) {
      if (e.target.closest('.x') || e.target === lb || e.target.tagName === 'FIGURE') { self._closeLb(); return; }
      if (e.target.closest('.prev')) show(self._lb.i - 1);
      if (e.target.closest('.next')) show(self._lb.i + 1);
    });
    var x0 = null;
    lb.addEventListener('pointerdown', function (e) { x0 = e.clientX; });
    lb.addEventListener('pointerup', function (e) {
      if (x0 == null) return;
      var dx = e.clientX - x0; x0 = null;
      if (Math.abs(dx) > 50) show(self._lb.i + (dx < 0 ? 1 : -1));
    });
    this._keys = function (e) {
      if (!self._lb) return;
      if (e.key === 'Escape') self._closeLb();
      else if (e.key === 'ArrowRight') show(self._lb.i + 1);
      else if (e.key === 'ArrowLeft') show(self._lb.i - 1);
      else if (e.key === 'Tab') {  // keep the keyboard inside the lightbox
        var bs = Array.prototype.slice.call(lb.querySelectorAll('button'));
        var at = bs.indexOf(self._lb.shade.activeElement);
        e.preventDefault();
        bs[(at + (e.shiftKey ? bs.length - 1 : 1)) % bs.length].focus();
      }
    };
    document.addEventListener('keydown', this._keys);
    lb.querySelector('.x').focus();
  };
  P._closeLb = function () {
    if (!this._lb) return;
    var lb = this._lb;
    this._lb = null;
    lb.el.remove();
    document.documentElement.style.overflow = lb.overflow;
    document.removeEventListener('keydown', this._keys);
    if (lb.back && lb.back.focus) lb.back.focus();
  };

  customElements.define('planplate-showcase', Showcase);
})();
