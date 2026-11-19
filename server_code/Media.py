# Media — Server Module. Photos and videos for the gallery, the website, specials, photo of the day and events.
#
# Where the files live:
#   - Cloudflare R2 (provider "cloudflare"), when the app secret "cloudflare_media" is set
#     (https://<signing key>@planplate-media.<subdomain>.workers.dev; the Worker is tools/cloudflare/worker.js).
#     The browser shrinks a photo (2000px + a 600px preview, or a video + its poster frame) and uploads straight to the
#     Worker with links signed here (media_ticket); register_cloudflare checks the files arrived. Rows keep the public
#     address in url; version "t" = there's a preview at url + "-thumb". It wins over Cloudinary for NEW uploads, and
#     Cloudinary is then never written to or deleted from (the old PlanPlate and dilettante.lv still show those files):
#     Admin -> Photo storage copies existing photos across (media_move) and can put them back (media_unmove).
#   - Cloudinary (the image host behind dilettante.lv's gallery), when the app secret "cloudinary_url" is set
#     (cloudinary://API_KEY:API_SECRET@CLOUD_NAME). The browser uploads straight to Cloudinary with a signature
#     made here (media_ticket), then tells us what it uploaded (register_upload); we check Cloudinary's signature.
#   - PlanPlate itself otherwise: the browser shrinks a photo to 1600px and sends it (upload_photo); videos come as
#     Anvil Media (upload_video). Served by /_/api/photo/<key>, with byte ranges so phones can play videos.
#   - "example" rows point at pictures in theme/assets (the Dilettante example website).
#
# Website feeds:  /_/api/photo/<key>[?s=thumb]     /_/api/gallery/<slug>  (the <planplate-gallery> feed format)
import base64
import hashlib
import json
import re
import time
import uuid

import anvil
import anvil.server
import anvil.users
from anvil.tables import app_tables

from . import Booking as B
from .Portal import _rest, _child, _nav, _user

IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}
VIDEO_TYPES = {"video/mp4": "mp4", "video/webm": "webm", "video/quicktime": "mov"}
MAX_IMAGE = 6 * 1024 * 1024
MAX_THUMB = 800 * 1024
MAX_VIDEO = 40 * 1024 * 1024       # stored in PlanPlate; Cloudinary's free plan takes up to 100 MB
MAX_VIDEO_CF = 90 * 1024 * 1024    # Cloudflare: the Worker takes requests up to 100 MB
MAX_PHOTOS = 500                   # per restaurant

GALLERY_CHOICES = {
    "theme": ["classic", "bento", "tilt", "cinematic", "editorial"],
    "bg_style": ["solid", "gradient", "spotlight", "aurora", "grain", "paper", "dotted", "stripes", "vignette", "mesh"],
    "picture_style": ["none", "frame", "duotone", "glow", "blob"],
    "size": ["xs", "sm", "md", "lg", "xl"],
    "motion": ["none", "fade", "rise", "slide", "zoom", "stagger"],
    "mobile_layout": ["bleed", "inset", "carousel", "stack"],
}
# The showcase (theme/assets/pp-showcase.js, <planplate-showcase>, Nov 19 2026) replaces the old component on PlanPlate
# websites and new embeds. Its look: the keys below + size, motion, accent, background, heading. The old keys above stay
# for <planplate-gallery> embeds already on restaurants' sites (dilettante.lv).
GALLERY_CHOICES.update({
    "layout": ["mosaic", "masonry", "spotlight", "slideshow", "carousel", "editorial", "grid", "polaroid"],
    "tone": ["page", "light", "dark", "custom"],
    "gap": ["none", "tight", "airy"],
    "corners": ["square", "soft", "round"],
    "frame": ["none", "shadow", "matte"],
    "captions": ["off", "hover", "below"],
    "hover": ["zoom", "lift", "none"],
    "show": ["all", "6", "9", "12"],
    "lightbox": ["on", "off"],
    "autoplay": ["on", "off"],
})
GALLERY_DEFAULT = {"theme": "bento", "bg_style": "gradient", "picture_style": "none", "size": "md", "motion": "rise",
                   "mobile_layout": "bleed", "accent": "#c9a56a", "background": "#1d1b18", "heading": "Our favourites",
                   "layout": "mosaic", "tone": "page", "gap": "tight", "corners": "soft", "frame": "none", "captions": "hover",
                   "hover": "zoom", "show": "all", "lightbox": "on", "autoplay": "on"}
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


# ---------------------------------------------------------------- storage
def _secret(name):
    try:
        import anvil.secrets
        return str(anvil.secrets.get_secret(name) or "").strip()
    except Exception:
        return ""


def cloudinary():
    """{"key", "secret", "cloud"} from the app secret "cloudinary_url" (cloudinary://key:secret@cloud), or from the old
    PlanPlate's three secrets cloudinary_cloud + cloudinary_api + cloudinary_secret; None = photos stay in PlanPlate."""
    m = re.match(r"^cloudinary://([^:\s]+):([^@\s]+)@([\w-]+)$", _secret("cloudinary_url"))
    if m:
        return {"key": m.group(1), "secret": m.group(2), "cloud": m.group(3)}
    cloud, key, secret = _secret("cloudinary_cloud"), _secret("cloudinary_api"), _secret("cloudinary_secret")
    if cloud and key and secret:
        return {"key": key, "secret": secret, "cloud": cloud}
    return None


def cloudflare():
    """{"base": "https://planplate-media.x.workers.dev", "key": signing key} from the app secret "cloudflare_media", or None."""
    m = re.match(r"^(https://)([0-9a-f]{32,128})@([\w.-]+)/?$", _secret("cloudflare_media"))
    return {"base": m.group(1) + m.group(3), "key": m.group(2)} if m else None


def remote():
    """True when uploads go to a photo host (Cloudflare or Cloudinary) rather than into PlanPlate's own tables."""
    return bool(cloudflare() or cloudinary())


def cf_link(cf, method, obj, ttl=900, **extra):
    """A signed address on the media Worker: PUT (extra max + kind), POST copy (max + from) or DELETE (none)."""
    import hmac
    import urllib.parse
    exp = int(time.time()) + ttl
    parts = {"PUT": ["max", "kind"], "POST": ["max", "from"], "DELETE": []}[method]
    text = "\n".join([method, obj, str(exp)] + [str(extra[p]) for p in parts]) if parts else "\n".join([method, obj, str(exp), ""])
    sig = hmac.new(cf["key"].encode(), text.encode(), hashlib.sha256).hexdigest()
    q = dict(((p, extra[p]) for p in parts), exp=exp, sig=sig)
    return "%s/%s?%s" % (cf["base"], obj, urllib.parse.urlencode(q))


def cf_object(r, key):
    return "%s/%s" % (folder(r), key)


def _cf_obj_of(row, cf):
    """The bucket key of a cloudflare row (its url without the Worker's address), or ''."""
    u = row["url"] or ""
    return u[len(cf["base"]) + 1:] if cf and u.startswith(cf["base"] + "/") else ""


def _cf_meta(cf, obj):
    """{size, type} of a file in the bucket, or None if it isn't there."""
    import anvil.http
    try:
        m = anvil.http.request("%s/%s?meta=1" % (cf["base"], obj), json=True)
    except Exception:
        return None
    return m if isinstance(m, dict) and m.get("ok") else None


def _cf_delete(cf, obj):
    import anvil.http
    try:
        anvil.http.request(cf_link(cf, "DELETE", obj), method="DELETE", json=True)
        return True
    except Exception as e:
        print("cloudflare delete failed:", obj, e)
        return False


def _cf_copy(cf, obj, source_url, limit):
    """The Worker fetches source_url into obj. Returns {size, type} or raises."""
    import anvil.http
    return anvil.http.request(cf_link(cf, "POST", obj, max=limit, **{"from": source_url}), method="POST", json=True)


def _cf_put(cf, obj, media, kind, limit):
    """Upload bytes we hold (a photo stored in PlanPlate) to obj. Returns {size, type} or raises."""
    import anvil.http
    return anvil.http.request(cf_link(cf, "PUT", obj, max=limit, kind=kind), method="PUT", data=media,
                              headers={"Content-Type": media.content_type}, json=True)


def sign(params, secret):
    """Cloudinary's request signature: the parameters sorted by name, joined with &, then the secret, SHA-1."""
    text = "&".join("%s=%s" % (k, params[k]) for k in sorted(params) if params[k] not in (None, ""))
    return hashlib.sha1((text + secret).encode("utf-8")).hexdigest()


def folder(r):
    """Where uploads go on Cloudinary. With the old PlanPlate ID set: restaurants/<old id>, the old apps' own folder."""
    if r["legacy_id"]:
        return "restaurants/" + r["legacy_id"]
    return "planplate/r" + re.sub(r"\D", "", r.get_id())


def _cl(url, transform):
    return url.replace("/upload/", "/upload/%s/" % transform, 1) if transform and "/upload/" in url else url


def urls(row, origin=None):
    """Where a photo or video can be seen: url (full size), thumb_url (square-ish preview), poster_url (videos)."""
    origin = origin or anvil.server.get_app_origin()
    p, video = row["provider"], row["kind"] == "video"
    if p == "cloudflare":
        u = row["url"] or ""
        thumb = u + "-thumb" if row["version"] == "t" else ("" if video else u)
        return {"url": u, "thumb_url": thumb, "poster_url": thumb if video else ""}
    if p == "cloudinary":
        u = row["url"] or ""
        if video:
            poster = re.sub(r"\.\w+$", ".jpg", _cl(u, "so_0,c_limit,w_1600,q_auto"))
            return {"url": _cl(u, "q_auto"), "thumb_url": re.sub(r"\.\w+$", ".jpg", _cl(u, "so_0,c_fill,w_480,h_480,q_auto")),
                    "poster_url": poster}
        return {"url": _cl(u, "c_limit,w_1600,q_auto,f_auto"), "thumb_url": _cl(u, "c_fill,w_480,h_480,q_auto,f_auto"), "poster_url": ""}
    if p == "example":
        u = origin + "/_/theme/" + (row["url"] or "")
        return {"url": u, "thumb_url": u, "poster_url": u if not video else ""}
    base = origin + "/_/api/photo/" + row["key"]
    thumb = base + "?s=thumb" if row["thumb"] is not None else ("" if video else base)
    return {"url": base, "thumb_url": thumb, "poster_url": thumb if video else ""}


def view(row, origin=None):
    if row is None:
        return None
    v = {"id": row.get_id(), "key": row["key"], "kind": row["kind"] or "image", "provider": row["provider"],
         "caption": row["caption"] or "", "in_gallery": bool(row["in_gallery"]), "position": row["position"] or 0,
         "width": row["width"], "height": row["height"], "size": row["size"], "created": B.iso(row["created"])}
    v.update(urls(row, origin))
    return v


def by_key(r, key):
    """The restaurant's photo with this key, or None (keys from the browser are never trusted for another restaurant)."""
    if not key or not isinstance(key, str) or not re.match(r"^[0-9a-f]{24,32}$", key):
        return None
    row = app_tables.photos.get(key=key)
    return row if row is not None and row["restaurant"] == r else None


def all_photos(r):
    return sorted(app_tables.photos.search(restaurant=r), key=lambda p: (p["position"] or 0, B._created_key(p)))


def gallery_photos(r):
    return [p for p in all_photos(r) if p["in_gallery"] and (p["kind"] or "image") == "image"]


def _new_row(r, **fields):
    if len(list(app_tables.photos.search(restaurant=r))) >= MAX_PHOTOS:
        raise ValueError("This restaurant has %d photos, the most it can keep. Delete some first." % MAX_PHOTOS)
    last = max([int(p["position"] or 0) for p in app_tables.photos.search(restaurant=r)] or [-1])
    u = anvil.users.get_user()
    fields.setdefault("in_gallery", False)
    key = fields.pop("key", None) or uuid.uuid4().hex
    return app_tables.photos.add_row(restaurant=r, key=key, position=last + 1, created=B.now_utc(), by=u, **fields)


def _clean_caption(text):
    return str(text or "").strip()[:200]


def _data_url(text, allowed, limit):
    """ "data:image/jpeg;base64,..." → (content type, bytes). Raises ValueError for anything else."""
    m = re.match(r"^data:([\w/+.-]+);base64,(.+)$", str(text or ""), re.S)
    if not m or m.group(1) not in allowed:
        raise ValueError("That file type isn't supported.")
    raw = base64.b64decode(m.group(2))
    if len(raw) > limit:
        raise ValueError("That file is too big (%.1f MB; the limit is %d MB)." % (len(raw) / 1048576.0, limit // 1048576))
    return m.group(1), raw


# ---------------------------------------------------------------- the website's gallery style + the site row
def site_row(r, create=True):
    """The restaurant's website row (one per restaurant), made on first use."""
    s = app_tables.sites.get(restaurant=r)
    if s is None and create:
        s = app_tables.sites.add_row(restaurant=r, path=_free_path(r["slug"] or "restaurant", r), published=False,
                                     palette="ivory", accent="", language=B.language(r), content={}, gallery=dict(GALLERY_DEFAULT),
                                     updated=B.now_utc(), views=0, visits={})
    return s


RESERVED = {"api", "admin", "app", "book", "menu", "gallery", "photo", "site", "www", "planplate", "static", "theme", "login"}


def _free_path(base, r):
    base = B.slugify(base)
    if base in RESERVED:
        base += "-restaurant"
    path, n = base, 2
    while True:
        hit = app_tables.sites.get(path=path)
        if hit is None or hit["restaurant"] == r:
            return path
        path = "%s-%d" % (base, n)
        n += 1


def gallery_style(s):
    g = dict(GALLERY_DEFAULT)
    g.update({k: v for k, v in (s["gallery"] or {}).items() if k in GALLERY_DEFAULT})
    return g


def clean_style(data, old=None):
    out = dict(old or GALLERY_DEFAULT)
    for k, choices in GALLERY_CHOICES.items():
        if data.get(k) in choices:
            out[k] = data[k]
    for k in ("accent", "background"):
        if HEX_RE.match(str(data.get(k) or "")):
            out[k] = data[k].lower()
    if "heading" in data:
        out["heading"] = str(data.get("heading") or "").strip()[:80]
    return out


# ---------------------------------------------------------------- manager callables
def _storage():
    return "cloudflare" if cloudflare() else ("cloudinary" if cloudinary() else "planplate")


def _video_mb():
    return (MAX_VIDEO_CF if cloudflare() else (100 * 1048576 if cloudinary() else MAX_VIDEO)) // 1048576


@anvil.server.callable(require_user=True)
def get_media(rid):
    """Every photo and video of the restaurant (for the photo pickers)."""
    r = _rest(rid)
    return {"ok": True, "photos": [view(p) for p in all_photos(r)], "storage": _storage()}


@anvil.server.callable(require_user=True)
def get_gallery(rid):
    r = _rest(rid, "manager")
    s = site_row(r)
    origin = anvil.server.get_app_origin()
    return {"ok": True, "nav": _nav(r), "photos": [view(p) for p in all_photos(r)], "storage": _storage(),
            "style": gallery_style(s), "slug": r["slug"], "origin": origin,
            "feed_url": origin + "/_/api/gallery/" + r["slug"], "script_url": origin + "/_/theme/planplate-gallery.js",
            "showcase_url": origin + "/_/theme/pp-showcase.js",
            "limits": {"image_mb": MAX_IMAGE // 1048576, "video_mb": _video_mb()}}


@anvil.server.callable(require_user=True)
def media_ticket(rid, kind="image"):
    """How the browser should upload: straight to Cloudflare or Cloudinary (signed), or to PlanPlate."""
    r = _rest(rid)
    cf = cloudflare()
    if cf is not None:
        key, video = uuid.uuid4().hex, kind == "video"
        obj = cf_object(r, key)
        return {"ok": True, "provider": "cloudflare", "key": key,
                "put": cf_link(cf, "PUT", obj, max=MAX_VIDEO_CF if video else MAX_IMAGE, kind="video" if video else "image"),
                "thumb_put": cf_link(cf, "PUT", obj + "-thumb", max=MAX_THUMB * 2, kind="image"),
                "max_video_mb": MAX_VIDEO_CF // 1048576, "max_image_mb": MAX_IMAGE // 1048576}
    cl = cloudinary()
    if cl is None:
        return {"ok": True, "provider": "planplate", "max_video_mb": MAX_VIDEO // 1048576, "max_image_mb": MAX_IMAGE // 1048576}
    params = {"folder": folder(r), "timestamp": str(int(time.time()))}
    fields = dict(params, api_key=cl["key"], signature=sign(params, cl["secret"]))
    rtype = "video" if kind == "video" else "image"
    return {"ok": True, "provider": "cloudinary", "url": "https://api.cloudinary.com/v1_1/%s/%s/upload" % (cl["cloud"], rtype),
            "fields": fields, "max_video_mb": 100, "max_image_mb": 20}


def upload_remote(r, source_url, caption="", in_gallery=False):
    """Copy a picture that is online (e.g. one of the app's own theme pictures) into the restaurant's Cloudflare or
    Cloudinary folder, server-side (the host fetches it). Returns the new photo row, or None when neither is set up or
    the copy fails."""
    cf = cloudflare()
    if cf is not None:
        key = uuid.uuid4().hex
        try:
            info = _cf_copy(cf, cf_object(r, key), source_url, MAX_IMAGE)
        except Exception as e:
            print("cloudflare copy failed:", source_url, e)
            return None
        if not isinstance(info, dict) or str(info.get("type") or "") not in IMAGE_TYPES:
            return None
        return _new_row(r, key=key, kind="image", provider="cloudflare", url="%s/%s" % (cf["base"], cf_object(r, key)),
                        format=IMAGE_TYPES[info["type"]], version="", caption=_clean_caption(caption),
                        in_gallery=bool(in_gallery), size=_num(info.get("size")))
    cl = cloudinary()
    if cl is None:
        return None
    import urllib.parse
    import anvil.http
    params = {"folder": folder(r), "timestamp": str(int(time.time()))}
    body = urllib.parse.urlencode(dict(params, file=source_url, api_key=cl["key"], signature=sign(params, cl["secret"])))
    try:
        info = anvil.http.request("https://api.cloudinary.com/v1_1/%s/image/upload" % cl["cloud"], method="POST", data=body,
                                  headers={"Content-Type": "application/x-www-form-urlencoded"}, json=True)
    except Exception as e:
        print("cloudinary upload failed:", e)
        return None
    if not isinstance(info, dict):
        return None
    url =str(info.get("secure_url") or "")
    if not url.startswith("https://res.cloudinary.com/"):
        return None
    return _new_row(r, kind="image", provider="cloudinary", url=url, public_id=str(info.get("public_id") or ""),
                    version=str(info.get("version") or ""), format=str(info.get("format") or "")[:10],
                    caption=_clean_caption(caption), in_gallery=bool(in_gallery), width=_num(info.get("width")),
                    height=_num(info.get("height")), size=_num(info.get("bytes")))


@anvil.server.callable(require_user=True)
def register_upload(rid, info, meta=None):
    """Record a file the browser uploaded to Cloudinary. Cloudinary signs its answer; we check that signature,
    so nobody can register someone else's picture or a made-up URL."""
    r = _rest(rid)
    cl = cloudinary()
    info, meta = dict(info or {}), dict(meta or {})
    if cl is None:
        return {"ok": False, "error": "Cloudinary isn't set up for this app."}
    pid, version = str(info.get("public_id") or ""), str(info.get("version") or "")
    if not pid.startswith(folder(r) + "/") or sign({"public_id": pid, "version": version}, cl["secret"]) != info.get("signature"):
        return {"ok": False, "error": "That upload couldn't be checked. Please try again."}
    kind = "video" if info.get("resource_type") == "video" else "image"
    url = str(info.get("secure_url") or "")
    if not url.startswith("https://res.cloudinary.com/%s/" % cl["cloud"]):
        return {"ok": False, "error": "That upload couldn't be checked. Please try again."}
    try:
        row = _new_row(r, kind=kind, provider="cloudinary", url=url, public_id=pid, version=version,
                       format=str(info.get("format") or "")[:10], caption=_clean_caption(meta.get("caption")),
                       in_gallery=bool(meta.get("in_gallery")) and kind == "image",
                       width=_num(info.get("width")), height=_num(info.get("height")), size=_num(info.get("bytes")))
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "photo": view(row)}


@anvil.server.callable(require_user=True)
def register_cloudflare(rid, data):
    """Record a file the browser uploaded to Cloudflare with media_ticket's links: {key, kind, thumb, width, height,
    caption, in_gallery}. We look the file up in the bucket (so nothing that didn't arrive gets a row)."""
    r = _rest(rid)
    cf = cloudflare()
    data = dict(data or {})
    if cf is None:
        return {"ok": False, "error": "Cloudflare isn't set up for this app."}
    key = str(data.get("key") or "")
    if not re.match(r"^[0-9a-f]{32}$", key) or app_tables.photos.get(key=key) is not None:
        return {"ok": False, "error": "That upload couldn't be checked. Please try again."}
    video = data.get("kind") == "video"
    obj = cf_object(r, key)
    meta = _cf_meta(cf, obj)
    types = VIDEO_TYPES if video else IMAGE_TYPES
    if meta is None or meta.get("type") not in types:
        return {"ok": False, "error": "That upload couldn't be checked. Please try again."}
    thumb = bool(data.get("thumb")) and _cf_meta(cf, obj + "-thumb") is not None
    try:
        row = _new_row(r, key=key, kind="video" if video else "image", provider="cloudflare", url="%s/%s" % (cf["base"], obj),
                       format=types[meta["type"]], version="t" if thumb else "", caption=_clean_caption(data.get("caption")),
                       in_gallery=bool(data.get("in_gallery")) and not video, width=_num(data.get("width")),
                       height=_num(data.get("height")), size=_num(meta.get("size")))
    except ValueError as e:
        _cf_delete(cf, obj)
        if thumb:
            _cf_delete(cf, obj + "-thumb")
        return {"ok": False, "error": str(e)}
    return {"ok": True, "photo": view(row)}


def _num(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


@anvil.server.callable(require_user=True)
def upload_photo(rid, data):
    """A photo shrunk in the browser: {image: data URL, thumb: data URL, width, height, caption, in_gallery}."""
    r = _rest(rid)
    data = dict(data or {})
    try:
        ctype, raw = _data_url(data.get("image"), IMAGE_TYPES, MAX_IMAGE)
        thumb = None
        if data.get("thumb"):
            tt, traw = _data_url(data.get("thumb"), IMAGE_TYPES, MAX_THUMB)
            thumb = anvil.BlobMedia(tt, traw, name="thumb." + IMAGE_TYPES[tt])
        row = _new_row(r, kind="image", provider="planplate", media=anvil.BlobMedia(ctype, raw, name="photo." + IMAGE_TYPES[ctype]),
                       thumb=thumb, format=IMAGE_TYPES[ctype], caption=_clean_caption(data.get("caption")),
                       in_gallery=bool(data.get("in_gallery")), width=_num(data.get("width")), height=_num(data.get("height")),
                       size=float(len(raw)))
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "photo": view(row)}


@anvil.server.callable(require_user=True)
def upload_video(rid, media, meta=None):
    """A video (Anvil Media from the browser, or a data URL from the local test harness) + an optional poster frame."""
    r = _rest(rid)
    meta = dict(meta or {})
    try:
        if isinstance(media, str):
            ctype, raw = _data_url(media, VIDEO_TYPES, MAX_VIDEO)
        else:
            ctype = (getattr(media, "content_type", "") or "").split(";")[0]
            if ctype not in VIDEO_TYPES:
                raise ValueError("Upload an MP4, WebM or MOV video.")
            raw = media.get_bytes()
            if len(raw) > MAX_VIDEO:
                raise ValueError("That video is too big (%.0f MB; the limit is %d MB). Shorten it, or link a YouTube video instead."
                                 % (len(raw) / 1048576.0, MAX_VIDEO // 1048576))
        poster = None
        if meta.get("poster"):
            pt, praw = _data_url(meta["poster"], IMAGE_TYPES, MAX_THUMB * 2)
            poster = anvil.BlobMedia(pt, praw, name="poster." + IMAGE_TYPES[pt])
        row = _new_row(r, kind="video", provider="planplate", media=anvil.BlobMedia(ctype, raw, name="video." + VIDEO_TYPES[ctype]),
                       thumb=poster, format=VIDEO_TYPES[ctype], caption=_clean_caption(meta.get("caption")),
                       width=_num(meta.get("width")), height=_num(meta.get("height")), size=float(len(raw)))
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "photo": view(row)}


@anvil.server.callable(require_user=True)
def save_photo(rid, data):
    r = _rest(rid, "manager")
    data = dict(data or {})
    row = _child(app_tables.photos, r, data.get("id"))
    upd = {}
    if "caption" in data:
        upd["caption"] = _clean_caption(data["caption"])
    if "in_gallery" in data:
        upd["in_gallery"] = bool(data["in_gallery"]) and (row["kind"] or "image") == "image"
    row.update(**upd)
    return {"ok": True, "photo": view(row)}


@anvil.server.callable(require_user=True)
def order_photos(rid, ids):
    """Put the photos in this order (the gallery shows them so). Photos not listed keep their place after these."""
    r = _rest(rid, "manager")
    mine = {p.get_id(): p for p in app_tables.photos.search(restaurant=r)}
    order = [i for i in dict.fromkeys(ids or []) if i in mine]
    rest = [p for p in all_photos(r) if p.get_id() not in order]
    for n, p in enumerate([mine[i] for i in order] + rest):
        p["position"] = n
    return {"ok": True, "photos": [view(p) for p in all_photos(r)]}


@anvil.server.callable(require_user=True)
def delete_photo(rid, pid):
    """Delete a photo everywhere: gallery, website, specials, posts and events stop showing it."""
    r = _rest(rid, "manager")
    row = _child(app_tables.photos, r, pid)
    for table in (app_tables.specials, app_tables.posts, app_tables.events):
        for x in table.search(restaurant=r, photo=row):
            x["photo"] = None
    cf = cloudflare()
    if row["provider"] == "cloudflare" and cf is not None:
        obj = _cf_obj_of(row, cf)
        if obj:
            _cf_delete(cf, obj)
            if row["version"] == "t":
                _cf_delete(cf, obj + "-thumb")
    elif row["provider"] == "cloudinary" and cf is None:  # with Cloudflare on, Cloudinary is a read-only archive
        _destroy(row)
    row.delete()
    return {"ok": True, "photos": [view(p) for p in all_photos(r)]}


def _destroy(row):
    """Remove the file from Cloudinary too (best effort: a failure leaves an unused file, never a broken page)."""
    cl = cloudinary()
    if cl is None or not row["public_id"]:
        return False
    try:
        import anvil.http
        params = {"public_id": row["public_id"], "timestamp": str(int(time.time()))}
        data = dict(params, api_key=cl["key"], signature=sign(params, cl["secret"]))
        rtype = "video" if row["kind"] == "video" else "image"
        anvil.http.request("https://api.cloudinary.com/v1_1/%s/%s/destroy" % (cl["cloud"], rtype), method="POST", data=data, json=True)
        return True
    except Exception as e:
        print("cloudinary destroy failed:", e)
        return False


@anvil.server.callable(require_user=True)
def save_gallery_style(rid, style):
    r = _rest(rid, "manager")
    s = site_row(r)
    s["gallery"] = clean_style(dict(style or {}), gallery_style(s))
    return {"ok": True, "style": gallery_style(s)}


# ---------------------------------------------------------------- admin: moving photos to Cloudflare (and back)
BACKUP = "cloudinary_backup"   # app_settings: {photo key: {"url", "version", "format", "size"}} of every moved Cloudinary row


def _admin():
    from . import common
    common.require_admin()


def _movable(row):
    return row["provider"] in ("cloudinary", "planplate")


@anvil.server.callable(require_user=True)
def media_storage():
    """Admin -> Photo storage: where new uploads go and how many photos sit where."""
    _admin()
    from . import common
    counts = {}
    for p in app_tables.photos.search():
        counts[p["provider"] or "planplate"] = counts.get(p["provider"] or "planplate", 0) + 1
    cf = cloudflare()
    return {"ok": True, "storage": _storage(), "counts": counts, "cloudflare": cf["base"] if cf else "",
            "cloudinary": bool(cloudinary()), "can_undo": len(common.get_setting(BACKUP) or {})}


def _move_one(row, cf):
    """Copy one photo/video (Cloudinary or stored in PlanPlate) into the bucket, then point the row there."""
    r, video = row["restaurant"], row["kind"] == "video"
    obj = cf_object(r, row["key"])
    limit = MAX_VIDEO_CF if video else MAX_IMAGE
    if row["provider"] == "cloudinary":
        u = urls(row)  # the same sizes the website shows today (1600px, square 480 preview, video poster)
        info = _cf_copy(cf, obj, u["url"], limit)
        thumb = bool(u["thumb_url"]) and _cf_copy(cf, obj + "-thumb", u["thumb_url"], MAX_THUMB * 4) is not None
    else:
        if row["media"] is None:
            raise ValueError("no file stored")
        info = _cf_put(cf, obj, row["media"], "video" if video else "image", limit)
        thumb = row["thumb"] is not None and _cf_put(cf, obj + "-thumb", row["thumb"], "image", MAX_THUMB * 4) is not None
    t = str((info or {}).get("type") or "")
    fmt = (VIDEO_TYPES if video else IMAGE_TYPES).get(t)
    if not fmt:
        raise ValueError("unexpected file type %r" % t)
    upd = {"provider": "cloudflare", "url": "%s/%s" % (cf["base"], obj), "version": "t" if thumb else "", "format": fmt,
           "size": _num(info.get("size"))}
    if row["provider"] == "planplate":
        upd.update(media=None, thumb=None)  # the copy is checked; PlanPlate's own copy isn't needed any more
    return upd


@anvil.server.callable(require_user=True)
def media_move(limit=10, rid=None):
    """Move up to `limit` photos (of one restaurant when rid is given) to Cloudflare (the Admin page calls this again until nothing is left). Cloudinary's
    files stay where they are (the old PlanPlate still shows them); their addresses are kept for media_unmove."""
    _admin()
    from . import common
    cf = cloudflare()
    if cf is None:
        return {"ok": False, "error": "Add the app secret cloudflare_media first."}
    backup = dict(common.get_setting(BACKUP) or {})
    only = {"restaurant": app_tables.restaurants.get_by_id(rid)} if rid else {}
    todo = [p for p in app_tables.photos.search(**only) if _movable(p)]
    moved, errors = 0, []
    for row in todo[:max(1, min(int(limit or 10), 25))]:
        try:
            old = {"url": row["url"], "version": row["version"], "format": row["format"], "size": row["size"]}
            upd = _move_one(row, cf)
            if row["provider"] == "cloudinary":
                backup[row["key"]] = old
                common.set_setting(BACKUP, backup)
            row.update(**upd)
            moved += 1
        except Exception as e:
            errors.append("%s (%s): %s" % (row["caption"] or row["key"][:8], row["restaurant"]["name"] if row["restaurant"] else "?", e))
            print("media_move failed:", row["key"], e)
    left = len([p for p in app_tables.photos.search(**only) if _movable(p)])
    return {"ok": True, "moved": moved, "left": left, "errors": errors, "stuck": bool(errors) and moved == 0}


@anvil.server.callable(require_user=True)
def media_unmove(limit=50):
    """Undo media_move for photos that came from Cloudinary: point them at their Cloudinary files again (the copies in
    Cloudflare are left alone). Photos that were stored in PlanPlate stay on Cloudflare."""
    _admin()
    from . import common
    backup = dict(common.get_setting(BACKUP) or {})
    done = 0
    for key in list(backup)[:max(1, int(limit or 50))]:
        row = app_tables.photos.get(key=key)
        old = backup.pop(key)
        if row is not None and row["provider"] == "cloudflare":
            row.update(provider="cloudinary", url=old.get("url"), version=old.get("version"), format=old.get("format"),
                       size=old.get("size"))
            done += 1
    common.set_setting(BACKUP, backup)
    return {"ok": True, "restored": done, "left": len(backup)}


# ---------------------------------------------------------------- public endpoints
def _range(raw, header):
    """(status, body bytes, extra headers) honouring a single "Range: bytes=a-b" request (Safari needs it for video)."""
    m = re.match(r"^bytes=(\d*)-(\d*)$", (header or "").strip())
    n = len(raw)
    if not m or (not m.group(1) and not m.group(2)):
        return 200, raw, {}
    if m.group(1):
        a = int(m.group(1))
        b = min(int(m.group(2)), n - 1) if m.group(2) else n - 1
    else:
        a, b = max(0, n - int(m.group(2))), n - 1
    if a >= n or a > b:
        return 416, b"", {"Content-Range": "bytes */%d" % n}
    return 206, raw[a:b + 1], {"Content-Range": "bytes %d-%d/%d" % (a, b, n)}


@anvil.server.http_endpoint("/photo/:key")
def photo_file(key, s=None, **kw):
    row = app_tables.photos.get(key=str(key or "")) if re.match(r"^[0-9a-f]{24,32}$", str(key or "")) else None
    if row is None or row["provider"] != "planplate":
        return anvil.server.HttpResponse(404, "Not found", headers={"Content-Type": "text/plain"})
    media = row["thumb"] if (s == "thumb" and row["thumb"] is not None) else row["media"]
    if media is None:
        return anvil.server.HttpResponse(404, "Not found", headers={"Content-Type": "text/plain"})
    headers = {"Content-Type": media.content_type, "Cache-Control": "public, max-age=31536000, immutable",
               "Access-Control-Allow-Origin": "*", "Accept-Ranges": "bytes"}
    if row["kind"] == "video" and media is row["media"]:
        req = getattr(anvil.server, "request", None)
        rng = (getattr(req, "headers", None) or {}).get("range") if req is not None else None
        if rng:
            status, body, extra = _range(media.get_bytes(), rng)
            headers.update(extra)
            return anvil.server.HttpResponse(status, anvil.BlobMedia(media.content_type, body), headers=headers)
    return anvil.server.HttpResponse(200, media, headers=headers)


def find_restaurant(ref):
    """A restaurant by booking-link slug (what websites use) or by row id."""
    ref = str(ref or "").strip()
    if not ref:
        return None
    r = app_tables.restaurants.get(slug=ref.lower())
    if r is None and re.match(r"^[0-9a-fA-F-]{32,36}$", ref):
        r = app_tables.restaurants.get(legacy_id=ref.lower())
    if r is None and ref.startswith("["):
        try:
            r = app_tables.restaurants.get_by_id(ref)
        except Exception:
            r = None
    return r


def feed(r, origin=None):
    """The gallery in the format <planplate-gallery> reads: [{public_id, url, thumb_url, alt, caption, width, height}]."""
    out = []
    for p in gallery_photos(r):
        u = urls(p, origin)
        item = {"public_id": p["public_id"] or p["key"], "url": u["url"], "thumb_url": u["thumb_url"] or u["url"],
                "alt": p["caption"] or "%s photo" % r["name"], "caption": p["caption"] or ""}
        if p["width"] and p["height"]:
            item.update(width=int(p["width"]), height=int(p["height"]))
        out.append(item)
    return out


SHOWCASE_KEYS = ("layout", "tone", "gap", "corners", "frame", "captions", "hover", "show", "lightbox", "autoplay", "size", "motion",
                 "accent", "background", "heading")


@anvil.server.http_endpoint("/showcase/:ref")
def showcase_feed(ref, **kw):
    """What <planplate-showcase> draws: the look chosen on the Gallery page and the photos, so a change there shows on
    every website at once (the pasted code never changes)."""
    r = find_restaurant(ref)
    if r is None:
        return anvil.server.HttpResponse(404, json.dumps({"error": "No restaurant with that link."}),
                                         headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"})
    s = site_row(r, create=False)
    g = gallery_style(s) if s is not None else dict(GALLERY_DEFAULT)
    body = {"restaurant": r["name"], "style": {k: g.get(k) for k in SHOWCASE_KEYS}, "photos": feed(r)}
    return anvil.server.HttpResponse(200, json.dumps(body), headers={
        "Content-Type": "application/json; charset=utf-8", "Access-Control-Allow-Origin": "*", "Cache-Control": "max-age=60"})


@anvil.server.http_endpoint("/gallery/:ref")
def gallery_feed(ref, **kw):
    r = find_restaurant(ref)
    if r is None:
        return anvil.server.HttpResponse(404, json.dumps({"error": "No restaurant with that link."}),
                                         headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"})
    return anvil.server.HttpResponse(200, json.dumps(feed(r)), headers={
        "Content-Type": "application/json; charset=utf-8", "Access-Control-Allow-Origin": "*", "Cache-Control": "max-age=60"})
