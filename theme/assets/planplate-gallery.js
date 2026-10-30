/*!
 * planplate-gallery.js  v2.0.0
 * -----------------------------------------------------------------------
 * A drop-in, self-contained gallery component that auto-populates from
 * the Planplate restaurant gallery API. All markup, CSS, and behavior
 * live in this one file (Shadow DOM scoped), so it's safe to drop on
 * any site regardless of that site's own styles.
 *
 * USAGE
 * -----------------------------------------------------------------------
 * 1. Add this ONE script tag to the <head> (or before </body>):
 *
 *      <script src="planplate-gallery.js"></script>
 *
 * 2. Drop the custom element anywhere in the page body:
 *
 *      <planplate-gallery
 *        restaurant-id="45d3d272-cd15-46d1-85e9-438db74fd6a9"
 *        theme="bento"
 *        accent-color="#c7752f"
 *        background-color="#faf7f2"
 *        text="Our Gallery">
 *      </planplate-gallery>
 *
 * ONE FILE, BOTH ENVIRONMENTS
 * -----------------------------------------------------------------------
 * This exact file works in testing and in production with no edits. The
 * API endpoint is resolved at runtime, first match wins:
 *
 *   1. feed-url attribute            explicit, fully-qualified URL
 *   2. api-base attribute            explicit base, id appended
 *   3. window.PLANPLATE_GALLERY_API_BASE
 *                                    set before this script loads
 *   4. data-api-base on this <script> tag
 *   5. Auto-detect                   if the PAGE is served from the Anvil
 *                                    app (*.anvil.app), the origin and any
 *                                    /debug/<token>/ prefix are read off
 *                                    location, so debug links keep working
 *                                    after their token rotates
 *   6. Auto-detect                   same trick, but read off this script's
 *                                    own src — covers the case where the
 *                                    page is elsewhere but the script is
 *                                    still served by the Anvil app
 *   7. DEV_API_BASE                  used only on localhost / file://
 *   8. PRODUCTION_API_BASE           everything else
 *
 * So: testing on localhost hits DEV_API_BASE, testing inside the Anvil app
 * hits that same app, and a customer site hits production. Set
 * window.PLANPLATE_GALLERY_DEBUG = true to log which one was chosen.
 *
 * ATTRIBUTES
 * -----------------------------------------------------------------------
 *   restaurant-id      (required, unless feed-url is set) UUID used to
 *                        build the API request.
 *   feed-url             (optional) A fully-qualified endpoint URL.
 *                        Takes priority over api-base/restaurant-id.
 *   api-base             (optional) Override the API base URL used with
 *                        restaurant-id.
 *   theme                (optional) Either a name or its numeric index —
 *                        both work interchangeably:
 *                          0 / "classic"    even reflowing grid, clean & neutral
 *                          1 / "bento"      asymmetric grid, one large hero photo (default)
 *                          2 / "tilt"       scattered polaroid photos with a
 *                                           cursor-following 3D tilt on hover
 *                          3 / "cinematic"  dark, moody, glowing accent, hover
 *                                           caption reveal — great at night
 *                          4 / "editorial"  quiet grayscale thumbnails that
 *                                           bloom into color on hover
 *                        Any value outside 0–4 (or an unrecognized name)
 *                        silently falls back to the default theme ("bento").
 *   bg-style             (optional) 0 solid (default) | 1 gradient |
 *                        2 spotlight | 3 aurora | 4 grain | 5 paper |
 *                        6 dotted | 7 stripes | 8 vignette | 9 mesh.
 *                        Every style is generated from your background-color /
 *                        accent-color via color-mix() — no fixed palette.
 *   picture-style        (optional) 0 none (default) | 1 frame | 2 duotone |
 *                        3 glow | 4 blob. Layered on top of any theme.
 *   size                 (optional) 0 xs | 1 sm | 2 md (default) | 3 lg | 4 xl.
 *                        On desktop this sets how wide a photo wants to be
 *                        and the grid fits as many per line as it can.
 *                        On phones (<=700px) it sets the column count
 *                        directly: xs 4, sm 3, md 2, lg 2, xl 1.
 *   motion               (optional) Scroll-triggered reveal, per photo:
 *                        0 none (default) | 1 fade | 2 rise | 3 slide |
 *                        4 zoom | 5 stagger. Each photo reveals once.
 *   accent-color         (optional) Brand color used for glows, borders,
 *                        and highlights. Default: #caa46a.
 *   background-color     (optional) CSS color for the section background.
 *                        If omitted, a sensible default is chosen per theme.
 *
 *   mobile-layout        (optional) How the gallery behaves once it is
 *                        rendering narrower than ~500px:
 *                          "bleed"    (default) edge-to-edge grid, hairline
 *                                     seams, no side padding — reads as an
 *                                     app rather than a shrunken web page
 *                          "inset"    padded and rounded, the 2.0 behaviour
 *                          "carousel" horizontal snapping filmstrip, one
 *                                     large photo at a time with a peek of
 *                                     the next
 *                          "stack"    one full-width 4:5 photo per row
 *   mobile-columns       (optional) Force the column count on narrow
 *                        screens, overriding whatever `size` implies.
 *
 *   -- new in 2.0 --
 *   max-images           (optional) Render at most N photos. Default: all.
 *   order                (optional) "api" (default) | "reverse" | "shuffle".
 *   eager                (optional, boolean) Fetch immediately instead of
 *                        waiting until the gallery nears the viewport.
 *   cache-ttl            (optional) Seconds to reuse a cached feed from
 *                        sessionStorage. Default 300. Set 0 to disable.
 *   max-upscale          (optional) How far past its native pixel size a
 *                        photo may be stretched in the lightbox.
 *                        Default 1 (never upscale). 1.25 allows 25%.
 *   modal-max-width      (optional) Hard ceiling in px for the lightbox
 *                        image before its natural size is known.
 *                        Default 1200 — matches the stored image size.
 *   hide-branding        (optional, boolean) Removes the "Powered by" badge.
 *
 * There is intentionally no title/heading in this component — it is
 * meant to drop into whatever heading the host page already has.
 *
 * All attributes are LIVE. Convenience methods on the element instance:
 *
 *      const el = document.querySelector('planplate-gallery');
 *      el.setTheme('cinematic');
 *      el.setBgStyle('aurora');
 *      el.setPictureStyle('glow');
 *      el.setSize('lg');
 *      el.setMotion('stagger');
 *      el.setAccentColor('#c7752f');
 *      el.setBackgroundColor('#111');
 *      el.setImages([{ url, thumb_url }, ...]);   // manual override
 *      el.reload();                                // re-fetch (skips cache)
 *      el.open(3); el.close(); el.next(); el.prev();
 *
 * EVENTS (all bubble, composed)
 * -----------------------------------------------------------------------
 *   planplate:load    { count, source: 'network'|'cache'|'manual' }
 *   planplate:error   { message, url }
 *   planplate:open    { index, image }
 *   planplate:close   { index }
 *   planplate:change  { index, image }
 *
 * STYLING FROM THE HOST PAGE (Shadow DOM parts)
 * -----------------------------------------------------------------------
 *   planplate-gallery::part(section | gallery | thumb | image |
 *                           modal | modal-image | branding)
 *
 * API RESPONSE FORMAT EXPECTED
 * -----------------------------------------------------------------------
 *   [{ "public_id": "...", "url": "...", "thumb_url": "..." }, ...]
 *
 *   Optional per-image fields, all used when present:
 *     alt / caption     accessible description (strongly recommended —
 *                       without it screen readers get a filename)
 *     width / height    natural pixel size of `url`, prevents layout shift
 *     thumb_width       natural width of `thumb_url`, enables srcset
 *     srcset            a ready-made srcset string, used verbatim
 * -----------------------------------------------------------------------
 */

(function () {
  "use strict";

  const VERSION = "2.0.0";
  const TAG = "planplate-gallery";

  // Captured now, because document.currentScript is null once we're async.
  const SCRIPT_EL = document.currentScript || null;
  const SCRIPT_SRC = SCRIPT_EL && SCRIPT_EL.src ? SCRIPT_EL.src : "";

  const existing = customElements.get(TAG);
  if (existing) {
    if (existing.version !== VERSION) {
      console.warn(
        "[planplate-gallery] version " +
        VERSION +
        " was loaded but version " +
        (existing.version || "unknown") +
        " is already registered. The first one wins — remove the " +
        "duplicate <script> tag.",
      );
    }
    return;
  }

  // =======================================================================
  // Endpoint configuration
  // =======================================================================

  // Production endpoint. This is the only line that should ever need to
  // change when the app is published to a custom domain.
  const PRODUCTION_API_BASE = "https://ibnhsvpertsb5ofe.anvil.app/_/api/gallery/";

  // Used only when the page is served from localhost or file://.
  // Safe to point at a debug link — it never reaches customer sites.
  const DEV_API_BASE =
    "https://ibnhsvpertsb5ofe.anvil.app/debug/WH7MWCVAU3KUPVOMULOCFOVQ6AIGQDWA%3D2J7RH5V7F3VBHVWDBNBMFT3N/_/api/gallery/";

  const API_PATH = "_/api/gallery/";
  const DEV_HOST_RE = /^(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|.+\.local)$/i;

  const isDebugLogging = () =>
    Boolean(window.PLANPLATE_GALLERY_DEBUG) ||
    (SCRIPT_EL && SCRIPT_EL.hasAttribute("data-debug"));

  /**
   * Given any URL served by an Anvil app, rebuild the gallery API base
   * from it — preserving the /debug/<token>/ segment when present, which
   * is what makes debug links keep working after the token rotates.
   * Returns null if the URL isn't recognizably an Anvil app URL.
   */
  function deriveAnvilApiBase(href) {
    let u;
    try {
      u = new URL(href, location.href);
    } catch (e) {
      return null;
    }
    if (!/(^|\.)anvil\.app$/i.test(u.hostname)) return null;

    // Anvil serves everything app-internal under /_/ — theme assets,
    // API endpoints, etc. Anything before that is the app root.
    const cut = u.pathname.indexOf("/_/");
    let root = cut >= 0 ? u.pathname.slice(0, cut) : "";

    // If we couldn't find /_/, fall back to detecting the debug prefix.
    if (cut < 0) {
      const dbg = u.pathname.match(/^\/debug\/[^/]+/);
      root = dbg ? dbg[0] : "";
    }

    return u.origin + root + "/" + API_PATH;
  }

  /**
   * Resolve the API base for this page load. See the header comment for
   * the full precedence list. Element-level attributes are handled by the
   * component itself and take priority over everything returned here.
   */
  function resolveGlobalApiBase() {
    if (
      typeof window.PLANPLATE_GALLERY_API_BASE === "string" &&
      window.PLANPLATE_GALLERY_API_BASE.trim()
    ) {
      return { base: window.PLANPLATE_GALLERY_API_BASE.trim(), via: "window global" };
    }

    if (SCRIPT_EL) {
      const attr = SCRIPT_EL.getAttribute("data-api-base");
      if (attr && attr.trim()) {
        return { base: attr.trim(), via: "script data-api-base" };
      }
    }

    const fromPage = deriveAnvilApiBase(location.href);
    if (fromPage) return { base: fromPage, via: "page origin (Anvil)" };

    if (SCRIPT_SRC) {
      const fromScript = deriveAnvilApiBase(SCRIPT_SRC);
      if (fromScript) return { base: fromScript, via: "script origin (Anvil)" };
    }

    if (location.protocol === "file:" || DEV_HOST_RE.test(location.hostname)) {
      return { base: DEV_API_BASE, via: "dev host" };
    }

    return { base: PRODUCTION_API_BASE, via: "production default" };
  }

  const RESOLVED = resolveGlobalApiBase();
  if (isDebugLogging()) {
    console.info(
      "[planplate-gallery] v" +
      VERSION +
      " API base: " +
      RESOLVED.base +
      "  (via " +
      RESOLVED.via +
      ")",
    );
  }

  /**
   * Warm the connection to the API's origin as early as possible.
   *
   * This runs once, at script-load time, well before any individual
   * gallery decides whether/when to fetch (lazy galleries wait until
   * they're within 400px of the viewport). DNS lookup + TCP + TLS can
   * each cost a network round trip; doing that work while the browser
   * is still parsing the rest of the page means it's already done by
   * the time the fetch actually fires.
   *
   * `crossorigin="anonymous"` matters here: the fetch is issued with
   * `credentials: "omit"`, which is an anonymous-mode request. Without
   * a matching crossorigin attribute the browser opens a second,
   * separate connection instead of reusing this warmed one.
   */
  function warmApiConnection(base) {
    let origin;
    try {
      origin = new URL(base, location.href).origin;
    } catch (e) {
      return; // not an absolute URL we can hint at
    }
    if (!origin || origin === "null") return;

    const already = document.head.querySelector(
      'link[rel="preconnect"][data-planplate-hint="' + origin + '"]',
    );
    if (already) return;

    ["preconnect", "dns-prefetch"].forEach((rel) => {
      const link = document.createElement("link");
      link.rel = rel;
      link.href = origin;
      link.dataset.planplateHint = origin;
      if (rel === "preconnect") link.crossOrigin = "anonymous";
      document.head.appendChild(link);
    });
  }
  warmApiConnection(RESOLVED.base);

  // =======================================================================
  // Option tables
  // =======================================================================

  const VALID_THEMES = ["classic", "bento", "tilt", "cinematic", "editorial"];
  const DEFAULT_THEME = "bento";
  const DEFAULT_ACCENT = "#caa46a";

  const VALID_BG_STYLES = [
    "solid",
    "gradient",
    "spotlight",
    "aurora",
    "grain",
    "paper",
    "dotted",
    "stripes",
    "vignette",
    "mesh",
  ];
  const DEFAULT_BG_STYLE = "solid";

  const VALID_PICTURE_STYLES = ["none", "frame", "duotone", "glow", "blob"];
  const DEFAULT_PICTURE_STYLE = "none";

  const VALID_SIZES = ["xs", "sm", "md", "lg", "xl"];
  const DEFAULT_SIZE = "md";

  const VALID_MOTIONS = ["none", "fade", "rise", "slide", "zoom", "stagger"];
  const DEFAULT_MOTION = "none";
  const STAGGER_STEP_SECONDS = 0.09;
  const STAGGER_MAX_STEPS = 10;

  const VALID_ORDERS = ["api", "reverse", "shuffle"];
  const DEFAULT_ORDER = "api";

  const VALID_MOBILE_LAYOUTS = ["bleed", "inset", "carousel", "stack"];
  const DEFAULT_MOBILE_LAYOUT = "bleed";

  /**
   * Width buckets, measured against the component's own rendered width
   * rather than the viewport. See _measureWidth for why the viewport is
   * not trustworthy on a page that lacks a viewport meta tag.
   */
  const WIDTH_BUCKETS = [
    { name: "xs", max: 500 },
    { name: "sm", max: 768 },
    { name: "md", max: 1024 },
    { name: "lg", max: Infinity },
  ];

  let warnedAboutViewport = false;

  const THEME_DEFAULT_BG = {
    classic: "#ffffff",
    bento: "#f7f7f5",
    tilt: "#f5efe3",
    cinematic: "#0e0e13",
    editorial: "#fbfaf8",
  };

  const TILT_RESTING_DEGREES = [-5, 4, -3, 6, -6, 3, -4, 5, -2, 5];

  /**
   * Contrast target, from WCAG 2.1: 4.5:1 for normal body text (AA).
   * Used to keep the "no photos yet" / error status text readable
   * against whatever background-color the customer picked.
   */
  const CONTRAST_TEXT = 4.5;

  /**
   * The luminance at which black and white text contrast EQUALLY well.
   *
   * The intuitive guess is 0.5 — "past halfway, go dark" — and it is wrong.
   * The contrast formula is (L1 + 0.05) / (L2 + 0.05); that 0.05 models
   * ambient screen flare, and it is not symmetric. Setting the two options
   * equal gives (L + 0.05)^2 = 1.05 * 0.05, so L = sqrt(0.0525) - 0.05
   * = 0.1791.
   *
   * Practical consequence: a mid-grey like #808080 (L = 0.216) reads better
   * with BLACK text, not white, even though it looks like a "dark" colour.
   * Using 0.5 as the pivot picks the wrong colour across a wide band of
   * ordinary mid-tones.
   */
  const LUMINANCE_PIVOT = 0.1791;

  // Lightbox behaviour
  const DEFAULT_MODAL_MAX_WIDTH = 1200; // matches stored image size
  const DEFAULT_MAX_UPSCALE = 1; // never stretch past native pixels
  const SWIPE_COMMIT_FRACTION = 0.22; // of stage width, before it advances
  const SWIPE_VELOCITY = 0.45; // px/ms — a fast flick commits regardless
  const SWIPE_BASE_MS = 300; // settle duration when there is no flick
  const SWIPE_MIN_MS = 170; // settle animation floor
  const SWIPE_MAX_MS = 420; // and ceiling
  const DISMISS_DISTANCE = 120; // vertical drag before the viewer closes
  // Decelerating curve: fast start, gentle landing. Matches the feel of a
  // flick continuing under its own momentum rather than a linear slide.
  const SWIPE_EASING = "cubic-bezier(0.22, 0.61, 0.36, 1)";
  const CLOSE_ANIM_MS = 170;
  const DEFAULT_CACHE_TTL = 300; // seconds
  const FETCH_RETRY_DELAY = 1200; // ms before the single auto-retry

  // Body scroll lock is process-wide: several galleries can share a page.
  const scrollLock = {
    depth: 0,
    prevOverflow: "",
    prevPaddingRight: "",
    engage() {
      if (this.depth++ > 0) return;
      const body = document.body;
      const barWidth = window.innerWidth - document.documentElement.clientWidth;
      this.prevOverflow = body.style.overflow;
      this.prevPaddingRight = body.style.paddingRight;
      body.style.overflow = "hidden";
      if (barWidth > 0) {
        const current = parseFloat(getComputedStyle(body).paddingRight) || 0;
        body.style.paddingRight = current + barWidth + "px";
      }
    },
    release() {
      if (this.depth === 0) return;
      if (--this.depth > 0) return;
      document.body.style.overflow = this.prevOverflow;
      document.body.style.paddingRight = this.prevPaddingRight;
    },
  };

  // =======================================================================
  // Small utilities
  // =======================================================================

  /**
   * An attribute value can be a numeric index into `list` or a name from
   * `list`. Anything out of range quietly falls back to `fallback`.
   */
  function resolveEnumValue(raw, list, fallback) {
    const value = (raw == null ? "" : String(raw)).trim();
    if (value === "") return fallback;
    if (/^-?\d+$/.test(value)) {
      const idx = parseInt(value, 10);
      return idx >= 0 && idx < list.length ? list[idx] : fallback;
    }
    const clean = value.toLowerCase();
    return list.includes(clean) ? clean : fallback;
  }

  /** Only ever hand http(s) and protocol-relative URLs to an <img src>. */
  function safeImageUrl(raw) {
    if (typeof raw !== "string") return "";
    const value = raw.trim();
    if (!value) return "";
    if (value.startsWith("//") || value.startsWith("/")) return value;
    try {
      const proto = new URL(value, location.href).protocol;
      return proto === "http:" || proto === "https:" ? value : "";
    } catch (e) {
      return "";
    }
  }

  function toPositiveInt(raw, fallback) {
    const n = parseInt(raw, 10);
    return Number.isFinite(n) && n > 0 ? n : fallback;
  }

  function toPositiveFloat(raw, fallback) {
    const n = parseFloat(raw);
    return Number.isFinite(n) && n > 0 ? n : fallback;
  }

  function shuffled(list) {
    const out = list.slice();
    for (let i = out.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      const t = out[i];
      out[i] = out[j];
      out[j] = t;
    }
    return out;
  }

  /**
   * Best available accessible description for a photo. A filename is a
   * poor last resort, so it's cleaned up rather than dumped raw.
   */
  function altTextFor(img, index, total) {
    const explicit = img && (img.alt || img.caption || img.title);
    if (typeof explicit === "string" && explicit.trim()) return explicit.trim();
    return "Photo " + (index + 1) + " of " + total;
  }

  /**
   * Parse whatever a browser hands back from getComputedStyle into
   * 8-bit sRGB. Covers rgb()/rgba(), color(srgb ...) for wide-gamut
   * inputs, and hex. Any alpha is composited over white, since that is
   * the safest assumption about what sits behind the section.
   */
  function parseColor(value) {
    if (!value) return null;
    const str = String(value).trim().toLowerCase();
    if (str === "transparent") return [255, 255, 255];

    let m = str.match(/^#([0-9a-f]{3,8})$/);
    if (m) {
      let h = m[1];
      if (h.length === 3 || h.length === 4) {
        h = h.split("").map((c) => c + c).join("");
      }
      if (h.length !== 6 && h.length !== 8) return null;
      const a = h.length === 8 ? parseInt(h.slice(6, 8), 16) / 255 : 1;
      return composite(
        [
          parseInt(h.slice(0, 2), 16),
          parseInt(h.slice(2, 4), 16),
          parseInt(h.slice(4, 6), 16),
        ],
        a,
      );
    }

    m = str.match(/^rgba?\(([^)]+)\)$/);
    if (m) {
      const parts = m[1].split(/[\s,/]+/).filter(Boolean).map(parseFloat);
      if (parts.length < 3 || parts.some((n) => !Number.isFinite(n))) return null;
      const a = parts.length > 3 ? parts[3] : 1;
      return composite([parts[0], parts[1], parts[2]], a);
    }

    m = str.match(/^color\(\s*srgb\s+([^)]+)\)$/);
    if (m) {
      const parts = m[1].split(/[\s/]+/).filter(Boolean).map(parseFloat);
      if (parts.length < 3 || parts.some((n) => !Number.isFinite(n))) return null;
      const a = parts.length > 3 ? parts[3] : 1;
      return composite(
        [parts[0] * 255, parts[1] * 255, parts[2] * 255],
        a,
      );
    }

    return null;
  }

  function composite(rgb, alpha) {
    const a = Math.min(1, Math.max(0, Number.isFinite(alpha) ? alpha : 1));
    return rgb.map((c) => {
      const v = Math.min(255, Math.max(0, c));
      return Math.round(v * a + 255 * (1 - a));
    });
  }

  /**
   * Relative luminance, WCAG 2.1 formula. Each channel is gamma-expanded
   * back to linear light before weighting. The weights are lopsided
   * (green 0.7152 vs blue 0.0722) because human vision is far more
   * sensitive to green — which is why a saturated blue reads as much
   * darker than a saturated green of the same "brightness".
   */
  function relativeLuminance(rgb) {
    const lin = rgb.map((c8) => {
      const c = c8 / 255;
      return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2];
  }

  function contrastRatio(a, b) {
    const hi = Math.max(a, b);
    const lo = Math.min(a, b);
    return (hi + 0.05) / (lo + 0.05);
  }

  function mixRgb(from, to, amount) {
    return from.map((c, i) => Math.round(c + (to[i] - c) * amount));
  }

  function rgbToCss(rgb) {
    return "rgb(" + rgb[0] + ", " + rgb[1] + ", " + rgb[2] + ")";
  }

  /**
   * How physically wide is this element, in the units that actually matter?
   *
   * A page with no <meta name="viewport"> is laid out by mobile browsers at
   * a virtual width of roughly 980px and then scaled down to fit the screen.
   * getBoundingClientRect happily reports ~940px, every max-width media
   * query resolves to "desktop", and the visitor gets the full desktop grid
   * shrunk to a third of its size — photos the size of postage stamps.
   *
   * screen.width still reports the real device width, so the ratio between
   * it and the layout viewport recovers the scale factor being applied.
   */
  function effectiveWidth(el) {
    const doc = el.ownerDocument;
    const view = doc.defaultView;
    const raw = el.getBoundingClientRect().width || el.offsetWidth || 0;
    if (!view) return { width: raw, scale: 1, raw: raw };

    const layout = doc.documentElement.clientWidth || view.innerWidth || raw;
    const screenW = (view.screen && view.screen.width) || layout;
    // Clamped at 1: a 2560px monitor showing a 1400px window is not "zoomed in".
    const scale = layout > 0 ? Math.min(1, screenW / layout) : 1;
    return { width: Math.round(raw * scale), scale: scale, raw: Math.round(raw) };
  }

  function bucketFor(width) {
    for (let i = 0; i < WIDTH_BUCKETS.length; i++) {
      if (width < WIDTH_BUCKETS[i].max) return WIDTH_BUCKETS[i].name;
    }
    return "lg";
  }

  const prefersReducedMotion = () =>
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // =======================================================================
  // Styles — built once and shared by every instance via adoptedStyleSheets
  // (falls back to a cloned <style> where that isn't supported).
  // =======================================================================

  const CSS = `
      :host {
        display: block;
        --gallery-bg: #ffffff;
        --gallery-accent: ${DEFAULT_ACCENT};
        box-sizing: border-box;
      }
      :host([hidden]) { display: none; }
      *, *::before, *::after { box-sizing: inherit; }

      .pg-section {
        position: relative;
        overflow: hidden;
        width: 100%;
        padding: 64px 20px;
        text-align: center;
        background-color: var(--gallery-bg);
        transition: background-color 0.35s ease;
      }

      .pg-gallery {
        position: relative;
        z-index: 1;
        max-width: 1240px;
        margin: 0 auto;
      }

      /* Every non-solid bg-style gets its own padded "mat" frame around
         the photo grid, with the pattern painted directly behind that
         padding, so the effect never depends on peeking through gaps. */
      .pg-section[data-bg]:not([data-bg="solid"]) .pg-gallery {
        padding: 30px;
        border-radius: 22px;
      }
      .pg-gallery::before {
        content: '';
        position: absolute;
        inset: 0;
        z-index: -1;
        border-radius: inherit;
        pointer-events: none;
      }
      @media (max-width: 640px) {
        .pg-section[data-bg]:not([data-bg="solid"]) .pg-gallery { padding: 16px; border-radius: 16px; }
      }

      /* ================================================================
         BACKGROUND STYLES (bg-style 0–9)
         All derived from --gallery-bg / --gallery-accent via color-mix(),
         so they adapt to whatever colors are configured.
         ================================================================ */

      /* 1 — gradient */
      .pg-section[data-bg="gradient"] .pg-gallery::before {
        background: linear-gradient(165deg,
          color-mix(in srgb, var(--gallery-bg) 100%, white 30%) 0%,
          var(--gallery-bg) 45%,
          color-mix(in srgb, var(--gallery-bg) 100%, black 26%) 100%);
      }

      /* 2 — spotlight */
      .pg-section[data-bg="spotlight"] .pg-gallery::before {
        background:
          radial-gradient(ellipse 90% 70% at 50% 0%,
            color-mix(in srgb, var(--gallery-accent) 65%, transparent), transparent 72%),
          var(--gallery-bg);
      }

      /* 3 — aurora */
      .pg-section[data-bg="aurora"] .pg-gallery::before { background: var(--gallery-bg); }
      .pg-gallery::after {
        content: '';
        position: absolute;
        inset: 0;
        z-index: -1;
        border-radius: inherit;
        pointer-events: none;
      }
      .pg-section[data-bg="aurora"] .pg-gallery::after {
        inset: -18%;
        background: conic-gradient(from 0deg,
          color-mix(in srgb, var(--gallery-accent) 95%, transparent),
          transparent 26%,
          color-mix(in srgb, var(--gallery-accent) 70%, white 30%) 55%,
          transparent 76%,
          color-mix(in srgb, var(--gallery-accent) 95%, transparent));
        filter: blur(30px);
        opacity: 0.85;
        animation: pg-aurora-spin 22s linear infinite;
      }
      @keyframes pg-aurora-spin { to { transform: rotate(360deg); } }

      /* 4 — grain */
      .pg-section[data-bg="grain"] .pg-gallery::before {
        background-color: color-mix(in srgb, var(--gallery-bg) 100%, var(--gallery-accent) 10%);
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.85'/%3E%3C/svg%3E");
        mix-blend-mode: overlay;
      }

      /* 5 — paper */
      .pg-section[data-bg="paper"] .pg-gallery::before {
        background-color: color-mix(in srgb, var(--gallery-bg) 78%, #d8c9a3 22%);
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.45'/%3E%3C/svg%3E");
        mix-blend-mode: multiply;
      }

      /* 6 — dotted */
      .pg-section[data-bg="dotted"] .pg-gallery::before {
        background-color: var(--gallery-bg);
        background-image: radial-gradient(
          color-mix(in srgb, var(--gallery-accent) 90%, transparent) 2.6px,
          transparent 2.8px);
        background-size: 18px 18px;
      }

      /* 7 — stripes */
      .pg-section[data-bg="stripes"] .pg-gallery::before {
        background-color: var(--gallery-bg);
        background-image: repeating-linear-gradient(135deg,
          transparent, transparent 14px,
          color-mix(in srgb, var(--gallery-accent) 35%, transparent) 14px,
          color-mix(in srgb, var(--gallery-accent) 35%, transparent) 17px);
      }

      /* 8 — vignette */
      .pg-section[data-bg="vignette"] .pg-gallery::before {
        background:
          radial-gradient(ellipse at center, transparent 25%,
            color-mix(in srgb, black 72%, var(--gallery-accent) 28%) 100%),
          var(--gallery-bg);
      }

      /* 9 — mesh */
      .pg-section[data-bg="mesh"] .pg-gallery::before {
        background-color: var(--gallery-bg);
        background-image:
          radial-gradient(circle at 12% 15%,
            color-mix(in srgb, var(--gallery-accent) 90%, transparent), transparent 48%),
          radial-gradient(circle at 88% 12%,
            color-mix(in srgb, var(--gallery-accent) 70%, white 30%), transparent 52%),
          radial-gradient(circle at 50% 100%,
            color-mix(in srgb, var(--gallery-accent) 75%, black 20%), transparent 58%);
        filter: blur(26px);
        opacity: 0.9;
      }

      /* Ambient glow bleeding past the frame for the three "lit" styles. */
      .pg-section[data-bg="aurora"] .pg-gallery,
      .pg-section[data-bg="mesh"] .pg-gallery,
      .pg-section[data-bg="spotlight"] .pg-gallery {
        box-shadow: 0 0 100px 24px color-mix(in srgb, var(--gallery-accent) 40%, transparent);
      }

      /* ================================================================
         PICTURE STYLES (picture-style 0–4)
         ================================================================ */

      /* 1 — frame */
      [data-picture="frame"] .pg-thumb,
      [data-picture="frame"] .pg-bento-cell {
        padding: 8px;
        background: #fdfdfb;
        box-shadow: 0 10px 24px rgba(0,0,0,0.18);
      }
      [data-picture="frame"] .pg-thumb img,
      [data-picture="frame"] .pg-bento-cell img {
        border-radius: 2px;
      }

      /* 2 — duotone */
      [data-picture="duotone"] .pg-thumb img,
      [data-picture="duotone"] .pg-bento-cell img {
        filter: grayscale(100%) contrast(1.1);
      }
      [data-picture="duotone"] .pg-thumb::after,
      [data-picture="duotone"] .pg-bento-cell::after {
        content: '';
        position: absolute;
        inset: 0;
        background: var(--gallery-accent);
        mix-blend-mode: color;
        opacity: 0.6;
        pointer-events: none;
        transition: opacity 0.35s ease;
      }
      [data-picture="duotone"] .pg-thumb:hover::after,
      [data-picture="duotone"] .pg-bento-cell:hover::after {
        opacity: 0.12;
      }

      /* 3 — glow */
      [data-picture="glow"] .pg-thumb,
      [data-picture="glow"] .pg-bento-cell {
        transition: box-shadow 0.35s ease, transform 0.35s ease;
      }
      [data-picture="glow"] .pg-thumb:hover,
      [data-picture="glow"] .pg-bento-cell:hover {
        box-shadow:
          0 0 0 3px color-mix(in srgb, var(--gallery-accent) 70%, transparent),
          0 0 26px 4px color-mix(in srgb, var(--gallery-accent) 55%, transparent);
        transform: translateY(-3px);
        z-index: 3;
      }

      /* 4 — blob */
      [data-picture="blob"] .pg-thumb,
      [data-picture="blob"] .pg-bento-cell {
        border-radius: 42% 58% 65% 35% / 45% 40% 60% 55%;
        transition: border-radius 0.5s ease, transform 0.35s ease;
      }
      [data-picture="blob"] .pg-thumb:hover,
      [data-picture="blob"] .pg-bento-cell:hover {
        border-radius: 18px;
        transform: scale(1.04);
        z-index: 3;
      }

      /* ================================================================
         SIZE (size 0–4)
         ================================================================ */
      /* Desktop: size picks how wide a photo wants to be, and the grid
         fits as many as the container allows. */
      [data-size="xs"] { --pg-col: 140px; --pg-col-max: 160px; }
      [data-size="sm"] { --pg-col: 180px; --pg-col-max: 220px; }
      [data-size="md"] { --pg-col: 220px; --pg-col-max: 290px; }
      [data-size="lg"] { --pg-col: 280px; --pg-col-max: 360px; }
      [data-size="xl"] { --pg-col: 360px; --pg-col-max: 460px; }

      [data-size="xs"] .pg-bento { grid-auto-rows: 90px; }
      [data-size="sm"] .pg-bento { grid-auto-rows: 110px; }
      [data-size="lg"] .pg-bento { grid-auto-rows: 170px; }
      [data-size="xl"] .pg-bento { grid-auto-rows: 210px; }

      /* ================================================================
         NARROW LAYOUTS — keyed off data-w, which JS sets from the
         component's own measured width, corrected for page scaling.
         Media queries are deliberately NOT used here: they read the
         layout viewport, which lies on any page without a viewport
         meta tag and reports ~980px on a 390px phone.
         ================================================================ */
      [data-w="xs"], [data-w="sm"], [data-w="md"] {
        --pg-cols: var(--pg-cols-override, var(--pg-cols-auto, 2));
      }
      [data-w="xs"] .pg-thumb,   [data-w="xs"] .pg-skeleton,
      [data-w="sm"] .pg-thumb,   [data-w="sm"] .pg-skeleton,
      [data-w="md"] .pg-thumb,   [data-w="md"] .pg-skeleton {
        flex: 0 1 calc(
          (100% - (var(--pg-cols) - 1) * var(--pg-gap)) / var(--pg-cols)
        );
        max-width: none;
      }

      /* Phone. Deliberately generous: two photos across is a gallery,
         three is a contact sheet. */
      [data-w="xs"][data-size="xs"] { --pg-cols-auto: 3; }
      [data-w="xs"][data-size="sm"] { --pg-cols-auto: 2; }
      [data-w="xs"][data-size="md"] { --pg-cols-auto: 2; }
      [data-w="xs"][data-size="lg"] { --pg-cols-auto: 1; }
      [data-w="xs"][data-size="xl"] { --pg-cols-auto: 1; }

      /* Large phone / small tablet */
      [data-w="sm"][data-size="xs"] { --pg-cols-auto: 4; }
      [data-w="sm"][data-size="sm"] { --pg-cols-auto: 3; }
      [data-w="sm"][data-size="md"] { --pg-cols-auto: 3; }
      [data-w="sm"][data-size="lg"] { --pg-cols-auto: 2; }
      [data-w="sm"][data-size="xl"] { --pg-cols-auto: 2; }

      /* Tablet */
      [data-w="md"][data-size="xs"] { --pg-cols-auto: 5; }
      [data-w="md"][data-size="sm"] { --pg-cols-auto: 4; }
      [data-w="md"][data-size="md"] { --pg-cols-auto: 4; }
      [data-w="md"][data-size="lg"] { --pg-cols-auto: 3; }
      [data-w="md"][data-size="xl"] { --pg-cols-auto: 2; }

      [data-w="xs"] .pg-bento { grid-template-columns: repeat(2, 1fr); grid-auto-rows: 150px; }
      [data-w="sm"] .pg-bento { grid-template-columns: repeat(3, 1fr); }

      [data-w="xs"] .pg-section,
      [data-w="sm"] .pg-section { --pg-gap: 10px; padding: 34px 14px 38px; }

      /* ---------------- mobile-layout: bleed (default) ----------------
         Edge to edge with a hairline seam. Side padding is what makes a
         phone gallery read as a shrunken web page rather than an app. */
      [data-w="xs"][data-mobile="bleed"] {
        --pg-gap: 3px;
      }
      [data-w="xs"][data-mobile="bleed"] .pg-section { padding: 34px 0 38px; }
      .pg-section[data-w="xs"][data-mobile="bleed"] .pg-gallery,
      .pg-section[data-w="xs"][data-mobile="stack"] .pg-gallery,
      .pg-section[data-w="xs"][data-mobile="carousel"] .pg-gallery {
        padding: 0;
        border-radius: 0;
      }
      [data-w="xs"][data-mobile="bleed"] .pg-thumb,
      [data-w="xs"][data-mobile="bleed"] .pg-skeleton,
      [data-w="xs"][data-mobile="bleed"] .pg-bento,
      [data-w="xs"][data-mobile="bleed"] .pg-bento-cell {
        border-radius: 0;
      }
      [data-w="xs"][data-mobile="bleed"] .pg-bento { gap: 3px; }
      [data-w="xs"][data-mobile="bleed"] .pg-bento-cell { box-shadow: none; }

      /* ---------------- mobile-layout: stack ----------------
         One large photo per screen. Slowest to browse, strongest impact. */
      [data-w="xs"][data-mobile="stack"] {
        --pg-cols-auto: 1;
        --pg-gap: 4px;
      }
      [data-w="xs"][data-mobile="stack"] .pg-section { padding: 34px 0 38px; }
      [data-w="xs"][data-mobile="stack"] .pg-gallery { padding: 0; }
      [data-w="xs"][data-mobile="stack"] .pg-thumb {
        aspect-ratio: 4 / 5;
        border-radius: 0;
      }

      /* ---------------- mobile-layout: carousel ----------------
         A snapping filmstrip. The peek of the next photo at the right
         edge is what tells a thumb there is more to see. */
      [data-w="xs"][data-mobile="carousel"] .pg-grid,
      [data-w="xs"][data-mobile="carousel"] .pg-bento {
        display: flex;
        flex-wrap: nowrap;
        overflow-x: auto;
        overscroll-behavior-x: contain;
        scroll-snap-type: x mandatory;
        scroll-padding-left: 14px;
        padding: 2px 14px 10px;
        gap: 10px;
        scrollbar-width: none;
        -webkit-overflow-scrolling: touch;
      }
      [data-w="xs"][data-mobile="carousel"] .pg-grid::-webkit-scrollbar,
      [data-w="xs"][data-mobile="carousel"] .pg-bento::-webkit-scrollbar {
        display: none;
      }
      [data-w="xs"][data-mobile="carousel"] .pg-section { padding: 34px 0 38px; }
      [data-w="xs"][data-mobile="carousel"] .pg-gallery { padding: 0; }
      [data-w="xs"][data-mobile="carousel"] .pg-thumb,
      [data-w="xs"][data-mobile="carousel"] .pg-skeleton,
      [data-w="xs"][data-mobile="carousel"] .pg-bento-cell {
        flex: 0 0 82%;
        max-width: none;
        scroll-snap-align: center;
        aspect-ratio: 4 / 5;
        border-radius: 12px;
      }
      /* The hero span is meaningless once the grid becomes a strip. */
      [data-w="xs"][data-mobile="carousel"] .pg-bento-hero {
        grid-column: auto;
        grid-row: auto;
      }

      /* ================================================================
         MOTION (motion 0–5)
         ================================================================ */
      [data-motion="fade"] .pg-thumb,
      [data-motion="fade"] .pg-bento-cell {
        opacity: 0;
        transition: opacity 0.8s ease;
      }
      [data-motion="fade"] .pg-thumb.pg-in-view,
      [data-motion="fade"] .pg-bento-cell.pg-in-view {
        opacity: 1;
      }

      [data-motion="rise"] .pg-thumb,
      [data-motion="rise"] .pg-bento-cell {
        opacity: 0;
        transform: translateY(32px);
        transition: opacity 0.7s ease, transform 0.7s ease;
      }
      [data-motion="rise"] .pg-thumb.pg-in-view,
      [data-motion="rise"] .pg-bento-cell.pg-in-view {
        opacity: 1;
        transform: translateY(0);
      }

      [data-motion="slide"] .pg-thumb,
      [data-motion="slide"] .pg-bento-cell {
        opacity: 0;
        transition: opacity 0.7s ease, transform 0.7s ease;
      }
      [data-motion="slide"] .pg-thumb:nth-child(odd),
      [data-motion="slide"] .pg-bento-cell:nth-child(odd) { transform: translateX(-60px); }
      [data-motion="slide"] .pg-thumb:nth-child(even),
      [data-motion="slide"] .pg-bento-cell:nth-child(even) { transform: translateX(60px); }
      [data-motion="slide"] .pg-thumb.pg-in-view,
      [data-motion="slide"] .pg-bento-cell.pg-in-view {
        opacity: 1;
        transform: translateX(0);
      }

      [data-motion="zoom"] .pg-thumb,
      [data-motion="zoom"] .pg-bento-cell {
        opacity: 0;
        transform: scale(0.88);
        transition: opacity 0.6s ease, transform 0.6s ease;
      }
      [data-motion="zoom"] .pg-thumb.pg-in-view,
      [data-motion="zoom"] .pg-bento-cell.pg-in-view {
        opacity: 1;
        transform: scale(1);
      }

      [data-motion="stagger"] .pg-thumb,
      [data-motion="stagger"] .pg-bento-cell {
        opacity: 0;
        transform: translateY(24px);
        transition: opacity 0.6s ease, transform 0.6s ease;
        transition-delay: var(--pg-stagger-delay, 0s);
      }
      [data-motion="stagger"] .pg-thumb.pg-in-view,
      [data-motion="stagger"] .pg-bento-cell.pg-in-view {
        opacity: 1;
        transform: translateY(0);
      }

      /* ---------------- Flowing grid (classic / tilt / cinematic / editorial)
         One wrapping container, not two hard-coded rows. The old split
         collapsed to a single column the moment the viewport got narrow,
         which is most of the time — and left a double gutter and an
         orphaned photo where the two rows met. */
      .pg-grid {
        display: flex;
        flex-wrap: wrap;
        gap: var(--pg-gap, 16px);
        justify-content: center;
      }
      .pg-thumb,
      .pg-skeleton {
        flex: 1 1 var(--pg-col, 220px);
        max-width: var(--pg-col-max, 290px);
      }

      /* Thumbs are real <button>s: keyboard, focus ring and semantics free. */
      .pg-thumb,
      .pg-bento-cell {
        appearance: none;
        border: 0;
        padding: 0;
        margin: 0;
        font: inherit;
        color: inherit;
        text-align: inherit;
      }

      .pg-thumb {
        position: relative;
        flex: 1 1 220px;
        max-width: 290px;
        aspect-ratio: 1 / 1;
        overflow: hidden;
        border-radius: 6px;
        cursor: pointer;
        background: #eee;
      }
      .pg-thumb img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
        transition: transform 0.45s ease;
      }
      .pg-thumb:hover img { transform: scale(1.07); }

      .pg-thumb::before {
        content: '';
        position: absolute;
        inset: 0;
        background: rgba(0,0,0,0.18);
        opacity: 0;
        transition: opacity 0.3s ease;
        pointer-events: none;
      }
      .pg-thumb:hover::before { opacity: 1; }

      .pg-thumb:focus-visible,
      .pg-bento-cell:focus-visible {
        outline: 3px solid var(--gallery-accent);
        outline-offset: 3px;
        z-index: 4;
      }

      /* ---------------- Bento theme ---------------- */
      .pg-bento {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        grid-auto-rows: 130px;
        grid-auto-flow: dense;
        gap: 14px;
      }
      .pg-bento-cell {
        position: relative;
        overflow: hidden;
        border-radius: 10px;
        cursor: pointer;
        background: #ddd;
        box-shadow: 0 6px 18px rgba(0,0,0,0.12);
        transition: transform 0.35s ease, box-shadow 0.35s ease;
      }
      .pg-bento-cell img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
        transition: transform 0.5s ease;
      }
      .pg-bento-cell:hover {
        transform: translateY(-4px);
        box-shadow: 0 16px 34px rgba(0,0,0,0.22);
        z-index: 2;
      }
      .pg-bento-cell:hover img { transform: scale(1.06); }
      .pg-bento-hero { grid-column: span 2; grid-row: span 2; }

      [data-w="xs"] .pg-bento { gap: 10px; }
      [data-w="xs"] .pg-bento-hero { grid-column: span 2; grid-row: span 2; }

      /* ---------------- Tilt theme ---------------- */
      [data-theme="tilt"] .pg-grid { perspective: 1200px; }
      [data-theme="tilt"] .pg-thumb {
        background: #fffdf8;
        padding: 10px 10px 26px 10px;
        border-radius: 3px;
        box-shadow: 0 10px 24px rgba(30,20,10,0.25);
        transform: rotate(calc(var(--rot, 0deg) * var(--pg-rot-scale, 1)))
                   rotateX(var(--rx, 0deg)) rotateY(var(--ry, 0deg));
        transform-style: preserve-3d;
        transition: transform 0.2s ease-out, box-shadow 0.25s ease;
      }
      [data-theme="tilt"] .pg-thumb:hover {
        box-shadow: 0 20px 40px rgba(30,20,10,0.32);
        z-index: 2;
      }
      [data-theme="tilt"] .pg-thumb img { border-radius: 2px; }
      [data-theme="tilt"] .pg-thumb::before { display: none; }

      /* ---------------- Cinematic theme ---------------- */
      [data-theme="cinematic"] .pg-thumb {
        border-radius: 8px;
        box-shadow: 0 0 0 1px rgba(255,255,255,0.07), 0 14px 32px rgba(0,0,0,0.55);
      }
      [data-theme="cinematic"] .pg-thumb img {
        filter: saturate(0.85) brightness(0.9);
        transition: filter 0.4s ease, transform 0.5s ease;
      }
      [data-theme="cinematic"] .pg-thumb:hover img {
        filter: saturate(1.05) brightness(1.02);
        transform: scale(1.06);
      }
      [data-theme="cinematic"] .pg-thumb::before {
        background: linear-gradient(to top, rgba(0,0,0,0.75), transparent 55%);
        opacity: 1;
      }
      [data-theme="cinematic"] .pg-thumb:hover {
        box-shadow: 0 0 0 1px var(--gallery-accent), 0 18px 40px rgba(0,0,0,0.6);
      }
      .pg-caption {
        position: absolute;
        left: 0;
        right: 0;
        bottom: 0;
        padding: 10px 12px;
        color: #fdfbf7;
        font-size: 11px;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        transform: translateY(10px);
        opacity: 0;
        transition: transform 0.3s ease, opacity 0.3s ease;
        pointer-events: none;
      }
      .pg-caption-dot {
        display: inline-block;
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: var(--gallery-accent);
        margin-right: 6px;
        vertical-align: middle;
      }
      [data-theme="cinematic"] .pg-thumb:hover .pg-caption,
      [data-theme="cinematic"] .pg-thumb:focus-visible .pg-caption {
        transform: translateY(0);
        opacity: 1;
      }

      /* ---------------- Editorial theme ---------------- */
      [data-theme="editorial"] .pg-grid { --pg-gap: 26px; }
      [data-theme="editorial"] .pg-thumb {
        border-radius: 2px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
      }
      [data-theme="editorial"] .pg-thumb::before { display: none; }
      [data-theme="editorial"] .pg-thumb img {
        filter: grayscale(100%) contrast(1.03);
        transition: filter 0.5s ease, transform 0.5s ease;
      }
      [data-theme="editorial"] .pg-thumb:hover img {
        filter: grayscale(0%);
        transform: scale(1.03);
      }
      [data-theme="editorial"] .pg-thumb:hover {
        box-shadow: 0 10px 24px rgba(0,0,0,0.14);
      }

      /* ---------------- Status / retry ---------------- */
      .pg-status {
        font-size: 15px;
        color: var(--pg-ink-soft, #777);
        padding: 20px 0;
      }
      .pg-status.pg-error { color: #b23c3c; }
      .pg-retry {
        display: inline-block;
        margin-top: 12px;
        padding: 8px 18px;
        font: inherit;
        font-size: 14px;
        letter-spacing: 0.5px;
        color: inherit;
        background: transparent;
        border: 1px solid currentColor;
        border-radius: 999px;
        cursor: pointer;
        transition: background 0.2s ease, color 0.2s ease;
      }
      .pg-retry:hover {
        background: var(--gallery-accent);
        border-color: var(--gallery-accent);
        color: #fff;
      }
      .pg-retry:focus-visible {
        outline: 3px solid var(--gallery-accent);
        outline-offset: 2px;
      }

      /* Skeleton loading state */
      .pg-skeleton {
        flex: 1 1 220px;
        max-width: 290px;
        aspect-ratio: 1 / 1;
        border-radius: 6px;
        background: linear-gradient(90deg, #eee 25%, #f5f5f5 37%, #eee 63%);
        background-size: 400% 100%;
        animation: pg-shimmer 1.4s ease infinite;
      }
      .pg-bento .pg-skeleton {
        flex: none;
        max-width: none;
        aspect-ratio: auto;
        border-radius: 10px;
      }
      .pg-grid .pg-skeleton { aspect-ratio: 1 / 1; }
      .pg-bento .pg-skeleton.pg-bento-hero { grid-column: span 2; grid-row: span 2; }
      @keyframes pg-shimmer {
        0% { background-position: 100% 50%; }
        100% { background-position: 0 50%; }
      }

      /* ================================================================
         LIGHTBOX
         Built on <dialog> + showModal(), which gives us the top layer,
         a real focus trap, Escape handling and focus restoration for
         free — all of which used to be hand-rolled or missing.
         ================================================================ */
      .pg-modal {
        position: fixed;
        inset: 0;
        width: 100%;
        height: 100%;
        max-width: none;
        max-height: none;
        margin: 0;
        padding: 0;
        border: 0;
        overflow: hidden;
        background: rgba(0, 0, 0, var(--pg-dim, 0.93));
        color: #fff;
        opacity: 0;
        transition: opacity 0.22s ease;

        /* Space reserved around the photo. The horizontal gutter keeps the
           image clear of the edge navigation targets on wide screens; the
           vertical one leaves room for the close button and counter. */
        --pg-gutter-x: 40px;
        --pg-gutter-y: 104px;

        /* Ceiling on how large the photo may be drawn. Replaced per image
           by JS with the photo's own natural size, so a 1200px photo is
           never stretched to 1900px on a big monitor and never looks soft. */
        --pg-cap-w: 1200px;
        --pg-cap-h: 1200px;
        touch-action: none;
      }
      .pg-modal[open] { display: block; }
      .pg-modal.pg-open { opacity: 1; }
      .pg-modal::backdrop { background: rgba(0, 0, 0, 0.6); }

      @media (min-width: 900px) {
        .pg-modal { --pg-gutter-x: 190px; }
      }
      @media (max-width: 640px) {
        .pg-modal { --pg-gutter-y: 88px; }
      }

      /* The stage fills the dialog; clicking its empty area closes. */
      .pg-stage {
        position: absolute;
        inset: 0;
        overflow: hidden;
        touch-action: none;
        cursor: zoom-out;
      }

      /* Three slides side by side, the middle one centred. Dragging moves
         the whole track, so the neighbouring photo is genuinely there and
         genuinely moving with the finger — not faded in afterwards. */
      .pg-track {
        position: absolute;
        top: 0;
        bottom: 0;
        left: -100%;
        width: 300%;
        display: flex;
        transform: translate3d(0, 0, 0);
        will-change: transform;
      }
      .pg-slide {
        flex: 0 0 33.3333%;
        display: flex;
        align-items: center;
        justify-content: center;
        min-width: 0;
      }

      .pg-modal-img {
        display: block;
        width: auto;
        height: auto;
        max-width: min(var(--pg-cap-w), calc(100vw - var(--pg-gutter-x)));
        max-height: min(var(--pg-cap-h), calc(100vh - var(--pg-gutter-y)));
        max-height: min(var(--pg-cap-h), calc(100svh - var(--pg-gutter-y)));
        object-fit: contain;
        box-shadow: 0 20px 60px rgba(0,0,0,0.55);
        border-radius: 3px;
        cursor: default;
        opacity: 0;
        transform: scale(0.97);
        transition: opacity 0.2s ease, transform 0.2s ease;
        -webkit-user-drag: none;
        user-select: none;
      }
      .pg-modal-img.pg-visible {
        opacity: 1;
        transform: scale(1);
      }
      /* While a finger is down the track follows it exactly, no transition. */
      .pg-modal[data-dragging="1"] .pg-modal-img { transition: none; }
      /* Neighbours are already loaded, so they must not fade in on arrival. */
      .pg-slide .pg-modal-img.pg-visible { transition: none; }

      .pg-spinner {
        position: absolute;
        width: 34px;
        height: 34px;
        border: 2px solid rgba(255,255,255,0.25);
        border-top-color: #fff;
        border-radius: 50%;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.2s ease 0.15s;
        animation: pg-spin 0.8s linear infinite;
      }
      .pg-modal[data-loading="1"] .pg-spinner { opacity: 1; }
      @keyframes pg-spin { to { transform: rotate(360deg); } }

      /* ---------------- Edge navigation targets ----------------
         The whole left and right edge navigates, so nobody has to aim
         at a 64px circle. The chevron is just the visible hint; the
         hit area is the full column. Kept clear of the close button
         and counter so those stay reachable. */
      .pg-zone {
        position: absolute;
        top: 68px;
        bottom: 68px;
        width: clamp(76px, 20vw, 200px);
        z-index: 6;
        display: flex;
        align-items: center;
        justify-content: center;
        appearance: none;
        border: 0;
        padding: 0;
        margin: 0;
        background: transparent;
        color: #fff;
        cursor: pointer;
        /* The drag handler lives on the dialog and sees events over these
           zones, so the browser must not claim the gesture first. */
        touch-action: none;
        -webkit-tap-highlight-color: transparent;
        transition: background 0.25s ease;
      }
      .pg-zone[hidden],
      .pg-branding[hidden],
      .pg-modal-hint[hidden] { display: none !important; }
      .pg-zone-prev { left: 0; }
      .pg-zone-next { right: 0; }

      .pg-modal[data-dragging="1"] .pg-zone { background: transparent; }
      .pg-zone-prev:hover {
        background: linear-gradient(to right, rgba(255,255,255,0.13), transparent);
      }
      .pg-zone-next:hover {
        background: linear-gradient(to left, rgba(255,255,255,0.13), transparent);
      }
      .pg-zone:focus-visible {
        outline: 3px solid var(--gallery-accent);
        outline-offset: -6px;
      }

      /* The chevron keeps the original circular look. */
      .pg-arrow {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 64px;
        height: 64px;
        font-size: 30px;
        line-height: 1;
        border-radius: 50%;
        background: rgba(255,255,255,0.08);
        transition: background 0.2s ease, transform 0.15s ease;
        pointer-events: none;
      }
      .pg-zone:hover .pg-arrow { background: rgba(255,255,255,0.22); }
      .pg-zone:active .pg-arrow { transform: scale(0.92); }

      /* ---------------- Close button ---------------- */
      .pg-modal-close {
        position: absolute;
        /* Clear of the notch / dynamic island on phones. */
        top: calc(16px + env(safe-area-inset-top, 0px));
        right: calc(16px + env(safe-area-inset-right, 0px));
        z-index: 8;
        width: calc(52px * var(--pg-ui, 1));
        height: calc(52px * var(--pg-ui, 1));
        display: flex;
        align-items: center;
        justify-content: center;
        appearance: none;
        border: none;
        border-radius: 50%;
        /* Strong enough to stay visible over a bright photo. */
        background: rgba(20,20,22,0.55);
        border: 1px solid rgba(255,255,255,0.22);
        color: #fff;
        font-size: calc(26px * var(--pg-ui, 1));
        line-height: 1;
        cursor: pointer;
        transition: background 0.2s ease, transform 0.15s ease;
        user-select: none;
        touch-action: none;
        backdrop-filter: blur(6px);
      }
      .pg-modal-close:hover { background: rgba(40,40,44,0.8); }
      .pg-modal-close:active { transform: scale(0.92); }
      .pg-modal-close:focus-visible {
        outline: 3px solid var(--gallery-accent);
        outline-offset: 2px;
      }
      /* Hit slop: the drawn circle stays 46px, the target is 78px. */
      .pg-modal-close::before {
        content: '';
        position: absolute;
        inset: -16px;
      }

      .pg-modal-counter {
        position: absolute;
        bottom: calc(22px + env(safe-area-inset-bottom, 0px));
        left: 50%;
        transform: translateX(-50%);
        z-index: 8;
        color: rgba(255,255,255,0.85);
        font-size: calc(14px * var(--pg-ui, 1));
        letter-spacing: 1px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        pointer-events: none;
      }
      .pg-modal-hint {
        position: absolute;
        bottom: 22px;
        right: 22px;
        z-index: 8;
        color: rgba(255,255,255,0.42);
        font-size: 12px;
        letter-spacing: 0.4px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        pointer-events: none;
      }
      @media (max-width: 640px) {
        .pg-modal-hint { display: none; }
        .pg-arrow { width: 52px; height: 52px; font-size: 24px; }
        .pg-zone { top: 78px; bottom: 62px; }
      }
      /* Pointer-coarse devices get swipe instead, so the chevrons can
         shrink back out of the photo's way. */
      @media (hover: none) and (pointer: coarse) {
        .pg-arrow { background: rgba(255,255,255,0.06); }
      }

      /* ---------------- Branding badge ---------------- */
      .pg-branding {
        position: absolute;
        bottom: 14px;
        right: 16px;
        z-index: 4;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 11px;
        letter-spacing: 0.3px;
        color: rgba(255,255,255,0.92);
        background: rgba(0,0,0,0.55);
        backdrop-filter: blur(3px);
        padding: 5px 11px;
        border-radius: 999px;
        opacity: 0.8;
        transition: opacity 0.25s ease;
        white-space: nowrap;
      }
      .pg-branding:hover { opacity: 1; }
      .pg-branding strong { font-weight: 700; }
      @media (max-width: 480px) {
        .pg-branding {
          position: static;
          display: table;
          margin: 18px auto 0;
          font-size: 10px;
        }
      }

      /* Screen-reader-only live region for load status. */
      .pg-sr {
        position: absolute;
        width: 1px;
        height: 1px;
        overflow: hidden;
        clip: rect(0 0 0 0);
        clip-path: inset(50%);
        white-space: nowrap;
      }

      /* ================================================================
         TOUCH / SMALL SCREEN CORRECTIONS
         Three themes hang their whole identity on :hover, which never
         fires on a phone. Without these, mobile visitors get the muted
         "before" state permanently and no hint that photos are tappable.
         ================================================================ */
      /* Polaroid mats are sized for 290px photos; at half that they swallow
         the picture, and the resting rotations make neighbours collide once
         the columns get tight. Tilt and editorial opt out of full bleed —
         both depend on the mat around each photo. */
      [data-w="xs"][data-theme="tilt"],
      [data-w="sm"][data-theme="tilt"] { --pg-rot-scale: 0.45; --pg-gap: 14px; }
      [data-w="xs"][data-theme="tilt"] .pg-thumb { padding: 6px 6px 16px 6px; border-radius: 3px; }
      [data-w="xs"][data-theme="tilt"] .pg-section,
      [data-w="xs"][data-theme="editorial"] .pg-section { padding-left: 14px; padding-right: 14px; }
      [data-w="xs"][data-theme="editorial"] .pg-grid { --pg-gap: 12px; }

      @media (hover: none) and (pointer: coarse) {
        /* Nothing reveals the caption on touch, so keep it visible —
           it doubles as the "this opens" affordance. */
        [data-theme="cinematic"] .pg-caption {
          transform: translateY(0);
          opacity: 0.92;
        }
        /* Full grayscale with no way to undo it makes food look grey and
           unappetising. Keep the muted editorial register, lose the morgue. */
        [data-theme="editorial"] .pg-thumb img { filter: grayscale(45%) contrast(1.03); }
        [data-picture="duotone"] .pg-thumb img,
        [data-picture="duotone"] .pg-bento-cell img { filter: grayscale(55%) contrast(1.08); }
        [data-picture="duotone"] .pg-thumb::after,
        [data-picture="duotone"] .pg-bento-cell::after { opacity: 0.32; }
      }

      /* ---------------- Reduced motion ---------------- */
      @media (prefers-reduced-motion: reduce) {
        .pg-section[data-bg="aurora"] .pg-gallery::after { animation: none; }
        [data-motion] .pg-thumb,
        [data-motion] .pg-bento-cell {
          opacity: 1 !important;
          transform: none !important;
          transition: none !important;
        }
        .pg-modal,
        .pg-modal-img,
        .pg-thumb img,
        .pg-bento-cell,
        .pg-bento-cell img { transition: none !important; }
        .pg-spinner { animation-duration: 2s; }
      }
  `;

  const MARKUP = `
    <section class="pg-section" part="section">
      <div class="pg-gallery" part="gallery"></div>
      <p class="pg-sr" role="status" aria-live="polite"></p>
      <div class="pg-branding" part="branding">Powered by <strong>PlanPlate</strong> Galleries</div>
    </section>

    <dialog class="pg-modal" part="modal" aria-label="Photo viewer">
      <div class="pg-stage">
        <div class="pg-track">
          <div class="pg-slide"><img class="pg-modal-img" part="modal-image" alt="" draggable="false" /></div>
          <div class="pg-slide"><img class="pg-modal-img" part="modal-image" alt="" draggable="false" /></div>
          <div class="pg-slide"><img class="pg-modal-img" part="modal-image" alt="" draggable="false" /></div>
        </div>
        <div class="pg-spinner" aria-hidden="true"></div>
      </div>
      <button type="button" class="pg-zone pg-zone-prev" aria-label="Previous photo">
        <span class="pg-arrow" aria-hidden="true">&#8249;</span>
      </button>
      <button type="button" class="pg-zone pg-zone-next" aria-label="Next photo">
        <span class="pg-arrow" aria-hidden="true">&#8250;</span>
      </button>
      <button type="button" class="pg-modal-close" aria-label="Close viewer">&times;</button>
      <div class="pg-modal-counter" aria-live="polite"></div>
      <div class="pg-modal-hint">&#8592; &#8594; to browse &middot; Esc to close</div>
    </dialog>
  `;

  // One stylesheet object shared by every instance where supported.
  let SHEET = null;
  const supportsAdopted =
    "adoptedStyleSheets" in Document.prototype &&
    "replaceSync" in CSSStyleSheet.prototype;
  if (supportsAdopted) {
    SHEET = new CSSStyleSheet();
    SHEET.replaceSync(CSS);
  }

  const TEMPLATE = document.createElement("template");
  TEMPLATE.innerHTML = supportsAdopted ? MARKUP : "<style>" + CSS + "</style>" + MARKUP;

  // =======================================================================
  // Component
  // =======================================================================

  class PlanplateGallery extends HTMLElement {
    static get version() {
      return VERSION;
    }

    static get observedAttributes() {
      return [
        "restaurant-id",
        "feed-url",
        "api-base",
        "theme",
        "bg-style",
        "picture-style",
        "size",
        "motion",
        "accent-color",
        "background-color",
        "max-images",
        "order",
        "mobile-layout",
        "mobile-columns",
        "hide-branding",
      ];
    }

    constructor() {
      super();
      const root = this.attachShadow({ mode: "open" });
      if (supportsAdopted) root.adoptedStyleSheets = [SHEET];
      root.appendChild(TEMPLATE.content.cloneNode(true));

      this._raw = []; // exactly what the API returned
      this._images = []; // after order / max-images
      this._currentIndex = 0;
      this._theme = DEFAULT_THEME;
      this._bgStyle = DEFAULT_BG_STYLE;
      this._pictureStyle = DEFAULT_PICTURE_STYLE;
      this._size = DEFAULT_SIZE;
      this._motion = DEFAULT_MOTION;
      this._order = DEFAULT_ORDER;

      this._motionObserver = null;
      this._lazyObserver = null;
      this._resizeObserver = null;
      this._widthBucket = "";
      this._metrics = null;
      this._onViewportChange = () => this._applyWidth();
      this._abort = null;
      this._fetchQueued = false;
      this._loading = false;
      this._retried = false;
      this._fetchedOnce = false;
      this._openerEl = null;
      this._preloads = [];
      this._settling = false;
      this._settleDone = null;
      this._settleTimer = 0;
      this._dragX = 0;
      this._suppressClick = false;
      this._tiltFrame = 0;

      const q = (sel) => root.querySelector(sel);
      this._els = {
        section: q(".pg-section"),
        gallery: q(".pg-gallery"),
        live: q(".pg-sr"),
        branding: q(".pg-branding"),
        modal: q(".pg-modal"),
        stage: q(".pg-stage"),
        track: q(".pg-track"),
        modalCounter: q(".pg-modal-counter"),
        closeBtn: q(".pg-modal-close"),
        prevZone: q(".pg-zone-prev"),
        nextZone: q(".pg-zone-next"),
        hint: q(".pg-modal-hint"),
      };

      this._bindModal();
    }

    // ------------------------------------------------------------------
    // Lifecycle
    // ------------------------------------------------------------------
    connectedCallback() {
      this._applyTheme(this.getAttribute("theme"));
      this._applyBgStyle(this.getAttribute("bg-style"));
      this._applyPictureStyle(this.getAttribute("picture-style"));
      this._applySize(this.getAttribute("size"));
      this._applyMotion(this.getAttribute("motion"));
      this._applyAccent(this.getAttribute("accent-color"));
      this._applyBackground();
      this._applyInk();
      this._applyBranding();
      this._applyMobileLayout();
      this._applyWidth();
      this._watchWidth();
      this._order = resolveEnumValue(
        this.getAttribute("order"),
        VALID_ORDERS,
        DEFAULT_ORDER,
      );

      if (this.hasAttribute("eager")) {
        this._queueFetch();
      } else {
        this._armLazyFetch();
      }
    }

    disconnectedCallback() {
      if (this._abort) this._abort.abort();
      if (this._motionObserver) this._motionObserver.disconnect();
      if (this._lazyObserver) this._lazyObserver.disconnect();
      if (this._resizeObserver) this._resizeObserver.disconnect();
      this._motionObserver = this._lazyObserver = this._resizeObserver = null;
      const view = this.ownerDocument.defaultView;
      if (view) {
        view.removeEventListener("resize", this._onViewportChange);
        view.removeEventListener("orientationchange", this._onViewportChange);
      }
      // A modal left open during an SPA route change used to lock the
      // page's scroll forever. Tear it down properly.
      if (this._els.modal.open) {
        this._els.modal.close();
      }
    }

    attributeChangedCallback(name, oldVal, newVal) {
      if (oldVal === newVal) return;
      switch (name) {
        case "theme":
          this._applyTheme(newVal);
          this._applyBackground(); // theme shifts the default bg
          this._applyInk();
          this._rerender(); // bento and grid are different structures
          break;
        case "bg-style":
          this._applyBgStyle(newVal);
          break;
        case "picture-style":
          this._applyPictureStyle(newVal);
          break;
        case "size":
          this._applySize(newVal);
          break;
        case "motion":
          this._applyMotion(newVal);
          this._setupMotionObserver(true);
          break;
        case "accent-color":
          this._applyAccent(newVal);
          this._applyInk();
          break;
        case "background-color":
          this._applyBackground();
          this._applyInk();
          break;
        case "hide-branding":
          this._applyBranding();
          break;
        case "mobile-layout":
        case "mobile-columns":
          this._applyMobileLayout();
          break;
        case "max-images":
        case "order":
          this._order = resolveEnumValue(
            this.getAttribute("order"),
            VALID_ORDERS,
            DEFAULT_ORDER,
          );
          this._applyImageSubset();
          this._rerender();
          break;
        case "restaurant-id":
        case "api-base":
        case "feed-url":
          if (this.isConnected) this._queueFetch();
          break;
      }
    }

    // ------------------------------------------------------------------
    // Public API
    // ------------------------------------------------------------------
    setTheme(v) { this.setAttribute("theme", v); }
    setBgStyle(v) { this.setAttribute("bg-style", v); }
    setPictureStyle(v) { this.setAttribute("picture-style", v); }
    setSize(v) { this.setAttribute("size", v); }
    setMotion(v) { this.setAttribute("motion", v); }
    setAccentColor(v) { this.setAttribute("accent-color", v); }
    setBackgroundColor(v) { this.setAttribute("background-color", v); }
    setOrder(v) { this.setAttribute("order", v); }
    setMobileLayout(v) { this.setAttribute("mobile-layout", v); }
    setMobileColumns(v) { this.setAttribute("mobile-columns", v); }
    setMaxImages(v) { this.setAttribute("max-images", v); }

    /** Re-fetch from the API, bypassing the session cache. */
    reload() {
      this._retried = false;
      this._queueFetch({ noCache: true });
    }

    /** Supply images directly, skipping the API entirely. */
    setImages(images) {
      this._raw = Array.isArray(images) ? images.filter(this._isUsable) : [];
      this._applyImageSubset();
      this._rerender();
      this._emit("load", { count: this._images.length, source: "manual" });
    }

    /** The images currently rendered, after order and max-images. */
    get images() {
      return this._images.slice();
    }

    get resolvedApiBase() {
      return this._apiBase();
    }

    open(index) { this._openModal(parseInt(index, 10) || 0); }
    close() { this._closeModal(); }
    next() { this._showNext(); }
    prev() { this._showPrev(); }

    // ------------------------------------------------------------------
    // Attribute -> DOM
    // ------------------------------------------------------------------
    _applyTheme(theme) {
      this._theme = resolveEnumValue(theme, VALID_THEMES, DEFAULT_THEME);
      this._els.section.setAttribute("data-theme", this._theme);
    }

    _applyBgStyle(v) {
      this._bgStyle = resolveEnumValue(v, VALID_BG_STYLES, DEFAULT_BG_STYLE);
      this._els.section.setAttribute("data-bg", this._bgStyle);
    }

    _applyPictureStyle(v) {
      this._pictureStyle = resolveEnumValue(
        v,
        VALID_PICTURE_STYLES,
        DEFAULT_PICTURE_STYLE,
      );
      this._els.section.setAttribute("data-picture", this._pictureStyle);
    }

    _applySize(v) {
      this._size = resolveEnumValue(v, VALID_SIZES, DEFAULT_SIZE);
      this._els.section.setAttribute("data-size", this._size);
    }

    _applyMotion(v) {
      this._motion = resolveEnumValue(v, VALID_MOTIONS, DEFAULT_MOTION);
      this._els.section.setAttribute("data-motion", this._motion);
    }

    _applyAccent(color) {
      this.style.setProperty(
        "--gallery-accent",
        color && color.trim() ? color : DEFAULT_ACCENT,
      );
    }

    _applyBackground() {
      const explicit = this.getAttribute("background-color");
      const bg =
        explicit && explicit.trim()
          ? explicit
          : THEME_DEFAULT_BG[this._theme] || "#ffffff";
      this.style.setProperty("--gallery-bg", bg);
    }

    /**
     * Derive the status/secondary-text colour from whatever background
     * the customer picked, instead of hoping a hardcoded #777 happens to
     * work against it.
     *
     *   1. Measure the background's relative luminance.
     *   2. Pick a direction using LUMINANCE_PIVOT (see the constant — the
     *        obvious 0.5 midpoint is the wrong number).
     *   3. Prefer a tinted near-black or near-white that keeps a trace of
     *        the background hue, because pure #000 on a warm cream reads
     *        as harsh. Fall back to pure black/white only if the tint
     *        cannot clear 4.5:1.
     *   4. Soften that colour toward the background for a lower-emphasis
     *        "secondary text" tone, as long as it still clears 4.5:1.
     */
    _applyInk() {
      if (!this.isConnected) return;

      const view = this.ownerDocument.defaultView;
      if (!view) return;

      const bg =
        parseColor(view.getComputedStyle(this._els.section).backgroundColor) ||
        [255, 255, 255];
      const bgL = relativeLuminance(bg);
      const goDark = bgL > LUMINANCE_PIVOT;

      // Tinted candidate: scale toward black, or lift toward white. Scaling
      // keeps the channel ratios, so the hue survives.
      const tinted = goDark
        ? mixRgb(bg, [0, 0, 0], 0.82)
        : mixRgb(bg, [255, 255, 255], 0.9);
      const pure = goDark ? [11, 11, 12] : [255, 255, 255];

      const ink =
        contrastRatio(relativeLuminance(tinted), bgL) >= CONTRAST_TEXT
          ? tinted
          : pure;

      // Status text is normal-sized, so it needs the full 4.5:1 too.
      // Soften toward the background only while that holds.
      let soft = mixRgb(ink, bg, 0.32);
      if (contrastRatio(relativeLuminance(soft), bgL) < CONTRAST_TEXT) {
        soft = ink;
      }

      this.style.setProperty("--pg-ink-soft", rgbToCss(soft));
    }

    _applyMobileLayout() {
      const layout = resolveEnumValue(
        this.getAttribute("mobile-layout"),
        VALID_MOBILE_LAYOUTS,
        DEFAULT_MOBILE_LAYOUT,
      );
      this._els.section.setAttribute("data-mobile", layout);

      const cols = toPositiveInt(this.getAttribute("mobile-columns"), 0);
      if (cols) {
        this._els.section.style.setProperty("--pg-cols-override", cols);
      } else {
        this._els.section.style.removeProperty("--pg-cols-override");
      }
    }

    /**
     * Classify the component by how wide it actually renders, and expose
     * that as data-w for the stylesheet. This replaces media queries
     * entirely, which buys three things:
     *   - correct layout on pages with no viewport meta tag
     *   - correct layout inside a narrow sidebar or CMS column, where the
     *       viewport is wide but the gallery is not
     *   - correct layout inside an iframe embed
     */
    _applyWidth() {
      if (!this.isConnected) return;

      const metrics = effectiveWidth(this);
      if (!metrics.width) return;
      this._metrics = metrics;

      const bucket = bucketFor(metrics.width);
      if (bucket !== this._widthBucket) {
        this._widthBucket = bucket;
        this._els.section.setAttribute("data-w", bucket);
      }

      /*
       * Scale compensation for modal chrome.
       *
       * Layout decisions use the EFFECTIVE width — how big the gallery
       * really is on the glass. On a page with no viewport meta tag the
       * browser can lay things out at a virtual width and then scale the
       * whole page down to fit the screen, which would otherwise leave
       * the lightbox's close button drawn at a fraction of its real
       * physical size. Dividing by the scale factor cancels that out.
       */
      const compensation = Math.min(3, 1 / Math.max(0.2, metrics.scale));
      // Same correction for modal chrome, so the close button is a real
      // 52px target on the physical screen rather than 21px.
      this.style.setProperty("--pg-ui", compensation.toFixed(2));

      if (metrics.scale < 0.9 && !warnedAboutViewport) {
        warnedAboutViewport = true;
        const hasMeta = Boolean(
          this.ownerDocument.querySelector('meta[name="viewport"]'),
        );
        console.warn(
          "[planplate-gallery] This page is being laid out at " +
            (this.ownerDocument.documentElement.clientWidth || 0) +
            "px and scaled down to fit a " +
            ((this.ownerDocument.defaultView.screen || {}).width || 0) +
            "px screen" +
            (hasMeta
              ? "."
              : ", because there is no <meta name=\"viewport\"> tag.") +
            " The gallery has compensated, but every other element on the " +
            "page is still being shrunk. Add this to <head>:\n" +
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
        );
      }
    }

    _watchWidth() {
      const view = this.ownerDocument.defaultView;
      if (view && "ResizeObserver" in view) {
        this._resizeObserver = new view.ResizeObserver(() => this._applyWidth());
        this._resizeObserver.observe(this);
      }
      // The page scale factor can change without the element resizing,
      // so orientation and viewport events are still worth listening to.
      if (view) {
        view.addEventListener("resize", this._onViewportChange, { passive: true });
        view.addEventListener("orientationchange", this._onViewportChange, {
          passive: true,
        });
      }
    }

    /** Layout diagnostics. Log this from the console on a real device. */
    get diagnostics() {
      const m = this._metrics || effectiveWidth(this);
      return {
        renderedWidth: m.raw,
        effectiveWidth: m.width,
        pageScale: Number(m.scale.toFixed(3)),
        widthBucket: this._widthBucket,
        mobileLayout: this._els.section.getAttribute("data-mobile"),
        hasViewportMeta: Boolean(
          this.ownerDocument.querySelector('meta[name="viewport"]'),
        ),
        imageCount: this._images.length,
      };
    }

    _applyBranding() {
      this._els.branding.hidden = this.hasAttribute("hide-branding");
    }

    _emit(name, detail) {
      this.dispatchEvent(
        new CustomEvent("planplate:" + name, {
          detail: detail,
          bubbles: true,
          composed: true,
        }),
      );
    }

    _announce(message) {
      this._els.live.textContent = message;
    }

    // ------------------------------------------------------------------
    // Data fetching
    // ------------------------------------------------------------------
    _apiBase() {
      const attr = this.getAttribute("api-base");
      return attr && attr.trim() ? attr.trim() : RESOLVED.base;
    }

    _feedUrl() {
      const explicit = this.getAttribute("feed-url");
      if (explicit && explicit.trim()) return explicit.trim();

      const restaurantId = this.getAttribute("restaurant-id");
      if (!restaurantId || !restaurantId.trim()) return null;

      const base = this._apiBase();
      const sep = base.endsWith("/") ? "" : "/";
      return base + sep + encodeURIComponent(restaurantId.trim());
    }

    /** Start loading as the gallery approaches the viewport, not before. */
    _armLazyFetch() {
      if (this._fetchedOnce) return;
      if (!("IntersectionObserver" in window)) {
        this._queueFetch();
        return;
      }
      this._lazyObserver = new IntersectionObserver(
        (entries, observer) => {
          if (entries.some((e) => e.isIntersecting)) {
            observer.disconnect();
            this._lazyObserver = null;
            this._queueFetch();
          }
        },
        { rootMargin: "400px 0px" },
      );
      this._lazyObserver.observe(this);
    }

    /**
     * Changing restaurant-id and api-base together fires two attribute
     * callbacks. Coalescing into a microtask means one request, not two
     * racing ones that can land out of order.
     */
    _queueFetch(opts) {
      this._fetchOpts = Object.assign({}, this._fetchOpts, opts);
      if (this._fetchQueued) return;
      this._fetchQueued = true;
      Promise.resolve().then(() => {
        this._fetchQueued = false;
        const o = this._fetchOpts || {};
        this._fetchOpts = null;
        this._fetchImages(o);
      });
    }

    _cacheKey(url) {
      return "planplate-gallery:" + url;
    }

    _cacheTtl() {
      const raw = this.getAttribute("cache-ttl");
      if (raw != null && raw.trim() !== "") {
        const n = parseInt(raw, 10);
        if (Number.isFinite(n) && n >= 0) return n;
      }
      return DEFAULT_CACHE_TTL;
    }

    _readCache(url) {
      const ttl = this._cacheTtl();
      if (!ttl) return null;
      try {
        const raw = sessionStorage.getItem(this._cacheKey(url));
        if (!raw) return null;
        const entry = JSON.parse(raw);
        if (!entry || (Date.now() - entry.t) / 1000 > ttl) return null;
        return Array.isArray(entry.d) ? entry.d : null;
      } catch (e) {
        return null; // private mode, quota, corrupt entry — all non-fatal
      }
    }

    _writeCache(url, data) {
      if (!this._cacheTtl()) return;
      try {
        sessionStorage.setItem(
          this._cacheKey(url),
          JSON.stringify({ t: Date.now(), d: data }),
        );
      } catch (e) {
        /* storage full or blocked — caching is optional */
      }
    }

    _isUsable(img) {
      return Boolean(img && (safeImageUrl(img.url) || safeImageUrl(img.thumb_url)));
    }

    _fetchImages(opts) {
      const options = opts || {};
      const url = this._feedUrl();

      if (!url) {
        this._renderStatus(
          'Add a restaurant-id (or feed-url) attribute to load this gallery.',
          true,
          false,
        );
        return;
      }

      this._fetchedOnce = true;

      if (!options.noCache) {
        const cached = this._readCache(url);
        if (cached) {
          this._ingest(cached, "cache");
          return;
        }
      }

      // Supersede any request still in flight.
      if (this._abort) this._abort.abort();
      const controller = new AbortController();
      this._abort = controller;

      this._loading = true;
      this._renderSkeleton();
      this._announce("Loading photos");

      fetch(url, {
        credentials: "omit",
        signal: controller.signal,
        headers: { Accept: "application/json" },
      })
        .then((res) => {
          if (!res.ok) throw new Error("HTTP " + res.status);
          return res.json();
        })
        .then((data) => {
          if (controller.signal.aborted || this._abort !== controller) return;
          this._loading = false;
          this._abort = null;

          if (!Array.isArray(data)) throw new Error("Feed was not an array");

          this._writeCache(url, data);
          this._ingest(data, "network");
        })
        .catch((err) => {
          if (err && err.name === "AbortError") return;
          if (this._abort !== controller) return;
          this._loading = false;
          this._abort = null;

          // One silent retry covers the common transient blip.
          if (!this._retried) {
            this._retried = true;
            setTimeout(() => {
              if (this.isConnected) this._fetchImages({ noCache: true });
            }, FETCH_RETRY_DELAY);
            return;
          }

          console.error("[planplate-gallery] Failed to load images:", err);
          this._renderStatus("These photos didn't load.", true, true);
          this._announce("Photos could not be loaded");
          this._emit("error", { message: String(err && err.message), url: url });
        });
    }

    _ingest(data, source) {
      this._retried = false;
      const usable = data.filter(this._isUsable);

      if (!usable.length) {
        this._raw = [];
        this._images = [];
        this._renderStatus("No photos here yet.", false, false);
        this._announce("No photos available");
        this._emit("load", { count: 0, source: source });
        return;
      }

      this._raw = usable;
      this._applyImageSubset();
      this._rerender();
      this._announce(this._images.length + " photos loaded");
      this._emit("load", { count: this._images.length, source: source });
    }

    _applyImageSubset() {
      let list = this._raw.slice();
      if (this._order === "reverse") list.reverse();
      else if (this._order === "shuffle") list = shuffled(list);

      const max = toPositiveInt(this.getAttribute("max-images"), 0);
      if (max) list = list.slice(0, max);

      this._images = list;
      if (this._currentIndex >= list.length) this._currentIndex = 0;
    }

    // ------------------------------------------------------------------
    // Rendering — status states
    // ------------------------------------------------------------------
    _renderSkeleton() {
      const gallery = this._els.gallery;
      gallery.textContent = "";

      // Match the skeleton to the layout that's about to replace it,
      // otherwise the page visibly re-flows the moment photos arrive.
      if (this._theme === "bento") {
        const grid = document.createElement("div");
        grid.className = "pg-bento";
        for (let i = 0; i < 7; i++) {
          const sk = document.createElement("div");
          sk.className = "pg-skeleton" + (i === 0 ? " pg-bento-hero" : "");
          grid.appendChild(sk);
        }
        gallery.appendChild(grid);
        return;
      }

      const grid = document.createElement("div");
      grid.className = "pg-grid";
      for (let i = 0; i < 8; i++) {
        const sk = document.createElement("div");
        sk.className = "pg-skeleton";
        grid.appendChild(sk);
      }
      gallery.appendChild(grid);
    }

    _renderStatus(message, isError, withRetry) {
      const gallery = this._els.gallery;
      gallery.textContent = "";

      const status = document.createElement("div");
      status.className = "pg-status" + (isError ? " pg-error" : "");

      const text = document.createElement("div");
      text.textContent = message;
      status.appendChild(text);

      if (withRetry) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "pg-retry";
        btn.textContent = "Try again";
        btn.addEventListener("click", () => {
          this._retried = false;
          this._queueFetch({ noCache: true });
        });
        status.appendChild(btn);
      }

      gallery.appendChild(status);
    }

    // ------------------------------------------------------------------
    // Rendering — photos
    // ------------------------------------------------------------------
    _rerender() {
      // A theme switch mid-request used to wipe the skeleton and show
      // "no photos". Keep the loading state instead.
      if (this._loading) {
        this._renderSkeleton();
        return;
      }

      const gallery = this._els.gallery;
      const images = this._images;

      if (!images.length) {
        if (this._fetchedOnce) this._renderStatus("No photos here yet.", false, false);
        return;
      }

      gallery.textContent = "";
      if (this._theme === "bento") this._renderBento(gallery, images);
      else this._renderGrid(gallery, images);

      this._setupMotionObserver();
    }

    /**
     * One wrapping container that reflows to whatever the viewport allows.
     * The photo count no longer dictates the structure, so there is no
     * seam between rows and no orphaned last photo.
     */
    _renderGrid(gallery, images) {
      const grid = document.createElement("div");
      grid.className = "pg-grid";
      images.forEach((img, index) => {
        grid.appendChild(this._buildThumb(img, index));
      });
      gallery.appendChild(grid);
    }

    _renderBento(gallery, images) {
      const grid = document.createElement("div");
      grid.className = "pg-bento";
      images.forEach((img, index) => {
        grid.appendChild(this._buildThumb(img, index, true));
      });
      gallery.appendChild(grid);
    }

    /**
     * One thumbnail. A real <button> rather than a div with role=button:
     * keyboard activation, focus ring and semantics all come for free.
     */
    _buildThumb(img, index, isBento) {
      const total = this._images.length;

      const wrap = document.createElement("button");
      wrap.type = "button";
      wrap.className = isBento
        ? "pg-bento-cell" + (index === 0 ? " pg-bento-hero" : "")
        : "pg-thumb";
      wrap.setAttribute("part", "thumb");
      wrap.setAttribute(
        "aria-label",
        "Open photo " + (index + 1) + " of " + total,
      );

      const imageEl = document.createElement("img");
      imageEl.setAttribute("part", "image");
      imageEl.src = safeImageUrl(img.thumb_url) || safeImageUrl(img.url);
      imageEl.loading = "lazy";
      imageEl.decoding = "async";
      imageEl.alt = altTextFor(img, index, total);

      // Serve a sharper file to big cells and a smaller one to phones,
      // when the feed gives us enough information to build candidates.
      const srcset = this._buildSrcset(img);
      if (srcset) {
        imageEl.srcset = srcset;
        imageEl.sizes = isBento
          ? "(max-width: 640px) 50vw, 300px"
          : "(max-width: 640px) 45vw, 290px";
      }

      // Intrinsic size stops the grid jumping as photos stream in.
      const w = toPositiveInt(img.thumb_width || img.width, 0);
      const h = toPositiveInt(img.height, 0);
      if (w && h) {
        imageEl.width = w;
        imageEl.height = h;
      }

      wrap.appendChild(imageEl);

      if (this._theme === "tilt") this._applyTilt(wrap, index);

      if (this._theme === "cinematic") {
        const caption = document.createElement("div");
        caption.className = "pg-caption";
        const dot = document.createElement("span");
        dot.className = "pg-caption-dot";
        caption.appendChild(dot);
        caption.appendChild(document.createTextNode("View photo"));
        wrap.appendChild(caption);
      }

      wrap.addEventListener("click", () => this._openModal(index, wrap));
      return wrap;
    }

    _buildSrcset(img) {
      if (typeof img.srcset === "string" && img.srcset.trim()) {
        return img.srcset.trim();
      }
      const thumb = safeImageUrl(img.thumb_url);
      const full = safeImageUrl(img.url);
      const thumbW = toPositiveInt(img.thumb_width, 0);
      const fullW = toPositiveInt(img.width, 0);
      if (!thumb || !full || thumb === full || !thumbW || !fullW) return "";
      if (fullW <= thumbW) return "";
      return thumb + " " + thumbW + "w, " + full + " " + fullW + "w";
    }

    /** Cursor-following 3D tilt, throttled to one write per frame. */
    _applyTilt(wrap, index) {
      const rot = TILT_RESTING_DEGREES[index % TILT_RESTING_DEGREES.length];
      wrap.style.setProperty("--rot", rot + "deg");
      if (prefersReducedMotion()) return;

      let pending = null;
      wrap.addEventListener("pointermove", (e) => {
        pending = { x: e.clientX, y: e.clientY };
        if (this._tiltFrame) return;
        this._tiltFrame = requestAnimationFrame(() => {
          this._tiltFrame = 0;
          if (!pending) return;
          const rect = wrap.getBoundingClientRect();
          const px = (pending.x - rect.left) / rect.width;
          const py = (pending.y - rect.top) / rect.height;
          wrap.style.setProperty("--ry", ((px - 0.5) * 16).toFixed(2) + "deg");
          wrap.style.setProperty("--rx", ((0.5 - py) * 16).toFixed(2) + "deg");
        });
      });
      wrap.addEventListener("pointerleave", () => {
        pending = null;
        wrap.style.setProperty("--rx", "0deg");
        wrap.style.setProperty("--ry", "0deg");
      });
    }

    // ------------------------------------------------------------------
    // Scroll-triggered motion
    // ------------------------------------------------------------------
    _setupMotionObserver(reset) {
      if (this._motionObserver) {
        this._motionObserver.disconnect();
        this._motionObserver = null;
      }

      const items = Array.from(
        this.shadowRoot.querySelectorAll(".pg-thumb, .pg-bento-cell"),
      );
      if (!items.length) return;

      // Switching motion type mid-page: clear the revealed flag so the
      // new animation actually gets a chance to run.
      if (reset) items.forEach((el) => el.classList.remove("pg-in-view"));

      if (this._motion === "none" || prefersReducedMotion()) {
        items.forEach((el) => el.classList.add("pg-in-view"));
        return;
      }

      if (this._motion === "stagger") {
        items.forEach((el, i) => {
          const delay = (i % STAGGER_MAX_STEPS) * STAGGER_STEP_SECONDS;
          el.style.setProperty("--pg-stagger-delay", delay.toFixed(2) + "s");
        });
      }

      this._motionObserver = new IntersectionObserver(
        (entries, observer) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add("pg-in-view");
              observer.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.15, rootMargin: "0px 0px -40px 0px" },
      );

      items.forEach((el) => this._motionObserver.observe(el));
    }

    // ------------------------------------------------------------------
    // Lightbox
    // ------------------------------------------------------------------
    _bindModal() {
      const els = this._els;

      els.closeBtn.addEventListener("click", () => this._closeModal());
      els.prevZone.addEventListener("click", () => this._go(-1));
      els.nextZone.addEventListener("click", () => this._go(1));

      Array.prototype.forEach.call(els.track.children, (slide) => {
        const img = slide.firstElementChild;
        img.addEventListener("load", () => this._onSlideLoad(img));
        img.addEventListener("error", () => this._onSlideError(img));
      });

      els.modal.addEventListener("keydown", (e) => {
        if (e.key === "ArrowRight") {
          e.preventDefault();
          this._go(1);
        } else if (e.key === "ArrowLeft") {
          e.preventDefault();
          this._go(-1);
        }
      });

      els.modal.addEventListener("cancel", (e) => {
        e.preventDefault();
        this._closeModal();
      });

      els.modal.addEventListener("close", () => {
        scrollLock.release();
        els.modal.classList.remove("pg-open");
        els.modal.style.removeProperty("--pg-dim");
        this._clearPreloads();
        this._emit("close", { index: this._currentIndex });
      });

      this._bindSwipe();
    }

    // ---------------- slide plumbing ----------------

    _slides() {
      return Array.prototype.slice.call(this._els.track.children);
    }

    _stageWidth() {
      return this._els.stage.clientWidth || this.ownerDocument.documentElement.clientWidth || 1;
    }

    _wrap(index) {
      const total = this._images.length;
      return total ? ((index % total) + total) % total : 0;
    }

    /** Point one slide at one photo. Same src is a no-op, so no reload. */
    _fillSlide(slide, index) {
      const total = this._images.length;
      const img = slide.firstElementChild;
      const wrapped = this._wrap(index);
      const photo = this._images[wrapped];
      if (!photo) return;

      const url = safeImageUrl(photo.url) || safeImageUrl(photo.thumb_url);
      slide.dataset.index = String(wrapped);

      if (img.getAttribute("src") !== url) {
        img.classList.remove("pg-visible");
        img.removeAttribute("srcset");
        img.setAttribute("src", url);
      }
      img.alt = altTextFor(photo, wrapped, total);

      if (img.complete && img.naturalWidth) this._onSlideLoad(img);
    }

    /** Centre slide carries the accessible content; the others are decorative. */
    _syncSlideRoles() {
      const slides = this._slides();
      slides.forEach((slide, i) => {
        const centre = i === 1;
        slide.setAttribute("aria-hidden", centre ? "false" : "true");
        slide.firstElementChild.setAttribute("tabindex", "-1");
      });
    }

    _positionSlides() {
      const slides = this._slides();
      this._fillSlide(slides[0], this._currentIndex - 1);
      this._fillSlide(slides[1], this._currentIndex);
      this._fillSlide(slides[2], this._currentIndex + 1);
      this._syncSlideRoles();
      this._syncChrome();
    }

    _syncChrome() {
      const els = this._els;
      const total = this._images.length;
      els.modalCounter.textContent = this._currentIndex + 1 + " / " + total;
      const multi = total > 1;
      els.prevZone.hidden = !multi;
      els.nextZone.hidden = !multi;
      els.hint.hidden = !multi;
    }

    // ---------------- transport ----------------

    _setTrack(x, y) {
      this._els.track.style.transform =
        "translate3d(" + (x || 0).toFixed(1) + "px, " + (y || 0).toFixed(1) + "px, 0)";
    }

    /**
     * Animate the track, then hand off to `done` once it lands. A timer
     * rather than transitionend, which browsers drop if the element is
     * re-styled mid-flight.
     */
    _animateTrack(x, y, duration, done) {
      const track = this._els.track;
      this._settleDone = done || null;

      if (duration <= 0 || prefersReducedMotion()) {
        this._settling = false;
        track.style.transition = "none";
        if (done) done();
        this._setTrack(0, 0);
        return;
      }

      this._settling = true;
      track.getBoundingClientRect(); // commit the current transform first
      track.style.transition = "transform " + Math.round(duration) + "ms " + SWIPE_EASING;
      this._setTrack(x, y);
      clearTimeout(this._settleTimer);
      this._settleTimer = setTimeout(() => this._finishSettle(), duration + 40);
    }

    /**
     * Land the in-flight animation immediately. Called both when it ends
     * naturally and when a new drag interrupts it — that interruption is
     * most of what makes fast repeated swipes feel responsive rather than
     * queued.
     */
    _finishSettle() {
      if (!this._settling) return;
      clearTimeout(this._settleTimer);
      this._settling = false;

      const track = this._els.track;
      const done = this._settleDone;
      this._settleDone = null;

      track.style.transition = "none";
      if (done) done();
      this._setTrack(0, 0);
      track.getBoundingClientRect(); // flush, so the next drag starts clean
    }

    /**
     * Rotate the slide elements rather than reassigning all three sources.
     *
     * Moving a DOM node never reloads its image, and shifting one slide
     * from front to back displaces the track by exactly one slide width —
     * which cancels the translate we just animated to. The result is that
     * resetting the transform to zero is invisible: no flash, no reload,
     * no decode.
     */
    _recycle(direction) {
      const track = this._els.track;
      const slides = this._slides();

      this._currentIndex = this._wrap(this._currentIndex + direction);

      if (direction > 0) {
        track.appendChild(slides[0]);
        this._fillSlide(track.children[2], this._currentIndex + 1);
      } else {
        track.insertBefore(slides[2], slides[0]);
        this._fillSlide(track.children[0], this._currentIndex - 1);
      }

      this._syncSlideRoles();
      this._syncChrome();
      this._preloadNeighbours();
      this._emit("change", {
        index: this._currentIndex,
        image: this._images[this._currentIndex],
      });
    }

    _go(direction, velocity) {
      if (this._images.length < 2) return;
      if (this._settling) this._finishSettle();

      const width = this._stageWidth();
      const current = this._dragX || 0;
      const remaining = Math.abs(-direction * width - current);
      // Baseline speed = whatever covers the remaining distance in 300ms.
      // A genuine flick beats that and lands sooner; a button press gets a
      // steady 300ms regardless of how wide the screen is.
      const baseline = remaining / SWIPE_BASE_MS;
      const speed = Math.max(velocity || 0, baseline);
      const duration = Math.min(
        SWIPE_MAX_MS,
        Math.max(SWIPE_MIN_MS, remaining / speed),
      );

      this._dragX = 0;
      this._animateTrack(-direction * width, 0, duration, () =>
        this._recycle(direction),
      );
    }

    _showNext() { this._go(1); }
    _showPrev() { this._go(-1); }

    // ---------------- direct manipulation ----------------

    /**
     * Gestures are bound to the dialog, not the stage.
     *
     * The edge navigation zones sit above the stage, so binding to the
     * stage meant a drag starting anywhere near the left or right edge
     * was swallowed by a button and never reached the swipe handler — on
     * a phone that is about 40% of the screen where nothing happened.
     * Listening on the dialog means the gesture works over the buttons
     * too; a plain tap still reaches them normally, and only a drag that
     * actually travelled suppresses the click.
     */
    _bindSwipe() {
      const modal = this._els.modal;

      let active = false;
      let startX = 0;
      let startY = 0;
      let startT = 0;
      let lastX = 0;
      let lastT = 0;
      let velocity = 0;
      let dx = 0;
      let dy = 0;
      let axis = "";
      let downTarget = null;
      let pointerId = null;

      const reset = () => {
        active = false;
        axis = "";
        dx = dy = 0;
        pointerId = null;
        this._dragX = 0;
        modal.removeAttribute("data-dragging");
        modal.style.removeProperty("--pg-dim");
      };

      modal.addEventListener("pointerdown", (e) => {
        if (e.button !== 0) return;
        // Interrupting a settle mid-flight keeps rapid swipes responsive.
        if (this._settling) this._finishSettle();

        active = true;
        startX = lastX = e.clientX;
        startY = e.clientY;
        startT = lastT = performance.now();
        velocity = 0;
        dx = dy = 0;
        axis = "";
        downTarget = e.target;
        pointerId = e.pointerId;
        this._els.track.style.transition = "none";
      });

      modal.addEventListener("pointermove", (e) => {
        if (!active) return;
        dx = e.clientX - startX;
        dy = e.clientY - startY;

        // Sampled over the recent past, not the whole gesture — a flick at
        // the end of a slow drag should still register as a flick.
        const now = performance.now();
        if (now - lastT > 8) {
          velocity = (e.clientX - lastX) / (now - lastT);
          lastX = e.clientX;
          lastT = now;
        }

        if (!axis && Math.abs(dx) + Math.abs(dy) > 8) {
          axis = Math.abs(dx) > Math.abs(dy) ? "x" : "y";
          modal.setAttribute("data-dragging", "1");
          // Now that it is a drag rather than a tap, take the pointer so
          // the gesture survives leaving whichever element it began on.
          if (pointerId !== null && modal.setPointerCapture) {
            try {
              modal.setPointerCapture(pointerId);
            } catch (err) {
              /* pointer already released */
            }
          }
          this._suppressClick = true;
        }
        if (!axis) return;

        if (axis === "x") {
          // Only one photo: resist rather than expose an empty slide.
          const damped = this._images.length > 1 ? dx : dx * 0.25;
          this._dragX = damped;
          this._setTrack(damped, 0);
        } else {
          this._dragX = 0;
          this._setTrack(0, dy);
          // Dimming the backdrop as it falls away is the cue that a
          // downward drag will dismiss.
          const fade = Math.max(0.25, 0.93 - Math.abs(dy) / 700);
          modal.style.setProperty("--pg-dim", fade.toFixed(2));
        }
      });

      const finish = () => {
        if (!active) return;
        const width = this._stageWidth();
        const moved = Math.abs(dx) + Math.abs(dy);
        const wasTarget = downTarget;
        const dragX = dx;
        const dragY = dy;
        const dragAxis = axis;
        const speed = Math.abs(velocity);

        active = false;
        modal.removeAttribute("data-dragging");

        // A tap on the empty area beside the photo closes the viewer.
        if (moved < 8) {
          reset();
          this._setTrack(0, 0);
          // Only the empty space around the photo closes. Taps on a zone
          // or a button fall through to that element's own click handler.
          const cls = wasTarget && wasTarget.classList;
          if (
            cls &&
            (cls.contains("pg-stage") ||
              cls.contains("pg-slide") ||
              cls.contains("pg-track"))
          ) {
            this._closeModal();
          }
          return;
        }

        if (dragAxis === "x" && this._images.length > 1) {
          const commit =
            Math.abs(dragX) > width * SWIPE_COMMIT_FRACTION ||
            speed > SWIPE_VELOCITY;
          if (commit) {
            const direction = dragX < 0 ? 1 : -1;
            // Only honour the flick's speed if it points the same way as
            // the committed direction, otherwise it fights the animation.
            const useSpeed = Math.sign(-velocity) === direction ? speed : 0;
            modal.style.removeProperty("--pg-dim");
            this._go(direction, useSpeed);
            active = false;
            axis = "";
            return;
          }
        } else if (dragAxis === "y" && dragY > DISMISS_DISTANCE) {
          reset();
          this._closeModal();
          return;
        }

        // Nothing committed — spring back to centre.
        reset();
        this._animateTrack(0, 0, SWIPE_MIN_MS, null);
      };

      modal.addEventListener("pointerup", finish);
      modal.addEventListener("pointercancel", () => {
        if (!active) return;
        reset();
        this._animateTrack(0, 0, SWIPE_MIN_MS, null);
      });

      // A drag that ends over a zone would otherwise fire that zone's
      // click and navigate a second time. Swallow exactly one click.
      modal.addEventListener(
        "click",
        (e) => {
          if (!this._suppressClick) return;
          this._suppressClick = false;
          e.stopPropagation();
          e.preventDefault();
        },
        true,
      );
    }

    // ---------------- open / close ----------------

    _openModal(index, opener) {
      if (!this._images.length) return;
      if (index < 0 || index >= this._images.length) return;

      this._currentIndex = index;
      this._openerEl = opener || null;

      const modal = this._els.modal;
      this._els.track.style.transition = "none";
      this._setTrack(0, 0);
      this._positionSlides();

      if (!modal.open) {
        scrollLock.engage();
        modal.showModal();
        requestAnimationFrame(() => modal.classList.add("pg-open"));
      }

      this._preloadNeighbours();
      this._emit("open", { index: index, image: this._images[index] });
    }

    _closeModal() {
      const modal = this._els.modal;
      if (!modal.open) return;

      if (this._settling) this._finishSettle();
      modal.classList.remove("pg-open");

      const done = () => {
        if (modal.open) modal.close();
        if (this._openerEl && this._openerEl.isConnected) {
          this._openerEl.focus({ preventScroll: true });
        }
        this._openerEl = null;
      };
      if (prefersReducedMotion()) done();
      else setTimeout(done, CLOSE_ANIM_MS);
    }

    // ---------------- per-slide sizing ----------------

    /**
     * Cap each photo at its own pixel dimensions so it is never upscaled.
     * The cap is written onto the <img> rather than the dialog, so it
     * only ever governs this one slide.
     */
    _sizeSlide(img) {
      const ceiling = toPositiveInt(
        this.getAttribute("modal-max-width"),
        DEFAULT_MODAL_MAX_WIDTH,
      );

      const upscale = toPositiveFloat(
        this.getAttribute("max-upscale"),
        DEFAULT_MAX_UPSCALE,
      );
      const natW = img.naturalWidth || ceiling;
      const natH = img.naturalHeight || ceiling;
      img.style.setProperty("--pg-cap-w", Math.round(natW * upscale) + "px");
      img.style.setProperty("--pg-cap-h", Math.round(natH * upscale) + "px");
    }

    _onSlideLoad(img) {
      this._sizeSlide(img);
      img.classList.add("pg-visible");
      if (img.parentElement === this._els.track.children[1]) {
        this._els.modal.removeAttribute("data-loading");
      }
    }

    _onSlideError(img) {
      const slide = img.parentElement;
      const photo = this._images[Number(slide && slide.dataset.index) || 0];
      const fallback = photo ? safeImageUrl(photo.thumb_url) : "";

      if (fallback && img.getAttribute("src") !== fallback) {
        img.setAttribute("src", fallback);
        return;
      }
      this._els.modal.removeAttribute("data-loading");
      img.alt = "This photo could not be loaded.";
      img.classList.add("pg-visible");
      this._emit("error", { message: "Image failed to load", url: img.src });
    }

    /**
     * The three slides already hold the immediate neighbours decoded and
     * on screen. This warms index +/-2 so a second swipe arriving before
     * the first has settled is just as smooth.
     */
    _preloadNeighbours() {
      this._clearPreloads();
      const total = this._images.length;
      if (total < 3) return;

      [2, -2].forEach((offset) => {
        const photo = this._images[this._wrap(this._currentIndex + offset)];
        const url = photo && (safeImageUrl(photo.url) || safeImageUrl(photo.thumb_url));
        if (!url) return;
        const loader = new Image();
        loader.decoding = "async";
        loader.src = url;
        this._preloads.push(loader);
      });
    }

    _clearPreloads() {
      this._preloads.forEach((el) => {
        el.src = "";
      });
      this._preloads = [];
    }

  }

  customElements.define(TAG, PlanplateGallery);
  window.PlanplateGallery = PlanplateGallery;
})();