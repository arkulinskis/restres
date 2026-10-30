# Media — Server Module. Photos and videos for the gallery, the website, specials, photo of the day and events.
#
# Where the files live:
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
MAX_PHOTOS = 500                   # per restaurant

GALLERY_CHOICES = {
    "theme": ["classic", "bento", "tilt", "cinematic", "editorial"],
    "bg_style": ["solid", "gradient", "spotlight", "aurora", "grain", "paper", "dotted", "stripes", "vignette", "mesh"],
    "picture_style": ["none", "frame", "duotone", "glow", "blob"],
    "size": ["xs", "sm", "md", "lg", "xl"],
    "motion": ["none", "fade", "rise", "slide", "zoom", "stagger"],
    "mobile_layout": ["bleed", "inset", "carousel", "stack"],
}
GALLERY_DEFAULT = {"theme": "bento", "bg_style": "gradient", "picture_style": "none", "size": "md", "motion": "rise",
                   "mobile_layout": "bleed", "accent": "#c9a56a", "background": "#1d1b18", "heading": "Our favourites"}
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


# ---------------------------------------------------------------- storage
def cloudinary():
    """{"key", "secret", "cloud"} from the app secret "cloudinary_url", or None (photos stay in PlanPlate)."""
    try:
        import anvil.secrets
        url = anvil.secrets.get_secret("cloudinary_url")
    except Exception:
        return None
    m = re.match(r"^\s*cloudinary://([^:\s]+):([^@\s]+)@([\w-]+)\s*$", url or "")
    return {"key": m.group(1), "secret": m.group(2), "cloud": m.group(3)} if m else None


def sign(params, secret):
    """Cloudinary's request signature: the parameters sorted by name, joined with &, then the secret, SHA-1."""
    text = "&".join("%s=%s" % (k, params[k]) for k in sorted(params) if params[k] not in (None, ""))
    return hashlib.sha1((text + secret).encode("utf-8")).hexdigest()


def folder(r):
    return "planplate/r" + re.sub(r"\D", "", r.get_id())


def _cl(url, transform):
    return url.replace("/upload/", "/upload/%s/" % transform, 1) if transform and "/upload/" in url else url


def urls(row, origin=None):
    """Where a photo or video can be seen: url (full size), thumb_url (square-ish preview), poster_url (videos)."""
    origin = origin or anvil.server.get_app_origin()
    p, video = row["provider"], row["kind"] == "video"
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
    return app_tables.photos.add_row(restaurant=r, key=uuid.uuid4().hex, position=last + 1, created=B.now_utc(), by=u, **fields)


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
    return "cloudinary" if cloudinary() else "planplate"


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
            "limits": {"image_mb": MAX_IMAGE // 1048576, "video_mb": MAX_VIDEO // 1048576 if not cloudinary() else 100}}


@anvil.server.callable(require_user=True)
def media_ticket(rid, kind="image"):
    """How the browser should upload: straight to Cloudinary (with a signed form), or to PlanPlate."""
    r = _rest(rid)
    cl = cloudinary()
    if cl is None:
        return {"ok": True, "provider": "planplate", "max_video_mb": MAX_VIDEO // 1048576, "max_image_mb": MAX_IMAGE // 1048576}
    params = {"folder": folder(r), "timestamp": str(int(time.time()))}
    fields = dict(params, api_key=cl["key"], signature=sign(params, cl["secret"]))
    rtype = "video" if kind == "video" else "image"
    return {"ok": True, "provider": "cloudinary", "url": "https://api.cloudinary.com/v1_1/%s/%s/upload" % (cl["cloud"], rtype),
            "fields": fields, "max_video_mb": 100, "max_image_mb": 20}


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
    if row["provider"] == "cloudinary":
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


@anvil.server.http_endpoint("/gallery/:ref")
def gallery_feed(ref, **kw):
    r = find_restaurant(ref)
    if r is None:
        return anvil.server.HttpResponse(404, json.dumps({"error": "No restaurant with that link."}),
                                         headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"})
    return anvil.server.HttpResponse(200, json.dumps(feed(r)), headers={
        "Content-Type": "application/json; charset=utf-8", "Access-Control-Allow-Origin": "*", "Cache-Control": "max-age=60"})
