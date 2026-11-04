# OldImport — Server Module. Brings the OLD PlanPlate's data (restaurant.planplate.com / client.planplate.com, read-only
# copies of their code in Documents/CLAUDE/planplate-old) into this app, from the CSV files Anvil's Data Tables
# "Download CSV" gives for each old table. Admin -> Import. Admins only.
#
#   old table           -> here
#   users               -> users (email, password hash: the same password keeps working; never overwrites a password)
#   new_staff_access    -> the owner of each restaurant + members (manager / staff)
#   restaurants         -> restaurants (uid -> legacy_id, so the old website code and QR codes keep working),
#                          regular hours -> one "Opening hours" period, special -> special days ("allow reservations"
#                          off -> no online bookings), table_seats -> tables, eating_time -> table time,
#                          resto_message_en/fr/lv -> the guest note per language, contact_email -> email + alerts
#   special_actions     -> "no online bookings" on that date
#   reservations        -> reservations (reservation_uid -> token, so importing twice adds nothing twice)
#   menu_files          -> menu files with their old ids (the CSV has no file inside: each one waits for its upload,
#                          and the old links to it work again once uploaded)
#   gallery_flags       -> gallery photos (still on Cloudinary, restaurants/<old id>/)
#   cloudinary_related  -> the gallery's style
#
# Each file is recognised by its columns, not its name. Importing again updates the same restaurants (found by old id)
# and replaces their hours, special days and tables with the old ones; bookings, photos and people are only added.
import ast
import csv
import io
import json
import re
from datetime import date, datetime, timedelta, timezone

import anvil.server
from anvil.tables import app_tables

from . import Booking as B
from . import common as C

TABLES = {  # columns that identify each old table's CSV
    "users": {"email", "password_hash"},
    "new_staff_access": {"restaurant_id", "user_id", "type_id"},
    "restaurants": {"uid", "restaurant", "regular"},
    "reservations": {"reservation_uid", "mydate", "mytime", "guests"},
    "menu_files": {"menu_id", "file_description"},
    "gallery_flags": {"restaurant_id", "public_id", "secure_url"},
    "cloudinary_related": {"resto_id", "theme", "framing"},
    "special_actions": {"close_reservations", "mydate", "restaurant"},
}
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
MAX_BYTES = 20 * 1048576


# ---------------------------------------------------------------- reading the CSV files
def read_files(files):
    """{old table name: [row dicts]} from the uploaded CSV files, plus the names of files that weren't recognised."""
    out: dict = {}
    unknown = []
    for f in files or []:
        if f is None:
            continue
        raw = f.get_bytes()
        if len(raw) > MAX_BYTES:
            raise ValueError("%s is over 20 MB." % (f.name or "A file"))
        text = raw.decode("utf-8-sig", errors="replace")
        rows = list(csv.DictReader(io.StringIO(text)))
        cols = set((rows[0].keys() if rows else next(csv.reader(io.StringIO(text)), [])) or [])
        cols = {str(c).strip() for c in cols if c}
        kind = next((k for k, need in TABLES.items() if need <= cols), None)
        if kind is None:
            unknown.append(f.name or "file")
            continue
        out.setdefault(kind, []).extend({str(k).strip(): v for k, v in r.items() if k} for r in rows)
    return out, unknown


def _s(v):
    return "" if v is None else str(v).strip()


def _obj(v):
    """A simpleObject cell: JSON, or Python's repr of it."""
    v = _s(v)
    if not v or v.lower() in ("none", "null"):
        return None
    try:
        return json.loads(v)
    except ValueError:
        pass
    try:
        return ast.literal_eval(v)
    except (ValueError, SyntaxError):
        return None


def _bool(v):
    return _s(v).lower() in ("true", "1", "yes", "t", "y")


def _num(v, default=None):
    try:
        return float(_s(v))
    except ValueError:
        return default


def _date(v):
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", _s(v))
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


def _dt(v):
    v = _s(v).replace("Z", "+00:00")
    if not v:
        return None
    for parse in (datetime.fromisoformat, lambda x: datetime.strptime(x, "%Y-%m-%d %H:%M:%S.%f%z"),
                  lambda x: datetime.strptime(x, "%Y-%m-%d %H:%M:%S%z"), lambda x: datetime.strptime(x[:19], "%Y-%m-%d %H:%M:%S")):
        try:
            d = parse(v)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _hm(v):
    try:
        return B.parse_hm(_s(v)[:5])
    except ValueError:
        return None


# ---------------------------------------------------------------- what the files hold (shown before importing)
def summary(data):
    rs = data.get("restaurants") or []
    known = {r["legacy_id"] for r in app_tables.restaurants.search() if r["legacy_id"]}
    return {"counts": {k: len(v) for k, v in data.items()},
            "restaurants": [{"id": _s(r.get("uid")).lower(), "name": _s(r.get("restaurant")) or "(no name)",
                             "exists": _s(r.get("uid")).lower() in known} for r in rs]}


@anvil.server.callable(require_user=True)
def old_import_preview(files):
    C.require_admin()
    try:
        data, unknown = read_files(files)
    except ValueError as e:
        return C.fail(str(e))
    if not data:
        return C.fail("None of these look like old PlanPlate tables. Download them as CSV from the old app's Data Tables.")
    return C.ok(summary=summary(data), unknown=unknown)


@anvil.server.callable(require_user=True)
def old_import(files, timezone_name="Europe/Riga"):
    me = C.require_admin()
    try:
        data, unknown = read_files(files)
    except ValueError as e:
        return C.fail(str(e))
    if not data.get("restaurants") and not data.get("reservations"):
        return C.fail("Add the restaurants CSV (and the others) from the old app.")
    tz = timezone_name if B.valid_timezone(timezone_name) else "Europe/Riga"
    report = Importer(data, me, tz).run()
    report["unknown"] = unknown
    return C.ok(report=report)


# ---------------------------------------------------------------- the import
class Importer:
    def __init__(self, data, admin, tz):
        self.d, self.admin, self.tz = data, admin, tz
        self.n: dict = {}
        self.warnings: list = []
        self.rest: dict = {}  # old uid -> restaurant row
        self.today = B.now_utc().date()

    def count(self, what, k=1):
        self.n[what] = self.n.get(what, 0) + k

    def warn(self, text):
        if text not in self.warnings and len(self.warnings) < 60:
            self.warnings.append(text)

    def run(self):
        self.users()
        access = self.access()
        for row in self.d.get("restaurants") or []:
            self.restaurant(row, access)
        for uid, r in list(self.rest.items()):
            self.team(uid, r, access)
        self.closures()
        self.reservations()
        self.menu_files()
        self.gallery()
        self.gallery_style()
        return {"counts": self.n, "warnings": self.warnings,
                "restaurants": [{"id": r.get_id(), "name": r["name"], "old_id": uid} for uid, r in self.rest.items()]}

    # ---- people
    def user(self, email, name=""):
        email = _s(email).lower()
        if not email or "@" not in email:
            return None
        u = app_tables.users.get(email=email)
        if u is None:
            u = app_tables.users.add_row(email=email, enabled=True, signed_up=B.now_utc(), display_name=name or None)
            self.count("people added")
            self.warn("%s had no row in the users file: they set a password with 'Forgot password' (or use Google)." % email)
        return u

    def users(self):
        for row in self.d.get("users") or []:
            email = _s(row.get("email")).lower()
            if not email or "@" not in email:
                continue
            u = app_tables.users.get(email=email)
            pw = _s(row.get("password_hash"))
            if u is None:
                app_tables.users.add_row(email=email, enabled=_bool(row.get("enabled")) or not _s(row.get("enabled")),
                                         password_hash=pw or None, confirmed_email=_bool(row.get("confirmed_email")),
                                         signed_up=_dt(row.get("signed_up")) or B.now_utc(), n_password_failures=0)
                self.count("people added")
            elif pw and not u["password_hash"]:
                u["password_hash"] = pw  # their old password works here too; an existing password is never replaced
                self.count("passwords kept")
            else:
                self.count("people already here")

    def access(self):
        out: dict = {}
        for row in self.d.get("new_staff_access") or []:
            uid = _s(row.get("restaurant_id")).lower()
            role = _s(row.get("type_id")).lower()
            if uid and role in ("owner", "manager", "staff") and "@" in _s(row.get("user_id")):
                out.setdefault(uid, []).append((role, _s(row.get("user_id")).lower(), _s(row.get("user_name"))))
        return out

    def team(self, uid, r, access):
        for role, email, name in access.get(uid, []):
            if role == "owner":
                continue
            if app_tables.members.get(restaurant=r, email=email) is not None:
                continue
            app_tables.members.add_row(restaurant=r, email=email, user=self.user(email, name), role=role, invited_by=self.admin,
                                       created=B.now_utc())
            self.count("team members")

    # ---- restaurants
    def restaurant(self, row, access):
        uid = _s(row.get("uid")).lower()
        if not UUID_RE.match(uid):
            self.warn("Skipped a restaurant without a proper old id (%s)." % (_s(row.get("restaurant")) or "no name"))
            return
        if uid.startswith("demo"):
            return
        name = _s(row.get("restaurant"))[:80] or "Restaurant"
        owners = [e for role, e, n in access.get(uid, []) if role == "owner"]
        owner = self.user(owners[0]) if owners else None
        if owner is None:
            owner = self.admin
            self.warn("%s has no owner in new_staff_access: it's yours for now (Settings -> Team to hand it over)." % name)
        msgs = {l: _s(row.get("resto_message_" + l)) for l in B.LANGS}
        msgs = {l: m for l, m in msgs.items() if m and m.lower() != "none"}
        main = "en" if msgs.get("en") or not msgs else next(iter(msgs))
        email = _s(row.get("contact_email")).lower()
        eat = _num(row.get("eating_time"), 2) or 2
        fields: dict = {"name": name, "email": email if "@" in email else "", "notify_email": email if "@" in email else None,
                        "duration_min": int(min(max(round(eat * 60 / 15) * 15, 30), 600)), "form_note": msgs.get(main, "")[:600],
                        "form_notes": {l: m[:600] for l, m in msgs.items() if l != main}, "language": main,
                        "languages": list(B.LANGS), "legacy_id": uid}
        r = app_tables.restaurants.get(legacy_id=uid)
        if r is None:
            defaults: dict = {k: v[0] for k, v in B.SETTINGS.items()}
            defaults.update(auto_threshold=50, max_auto_party=7)  # the old rules: auto-confirm under 51% full, 8+ guests ask
            r = app_tables.restaurants.add_row(owner=owner, slug=B.unique_slug(name), timezone=self.tz, created=B.now_utc(),
                                               position=len(list(app_tables.restaurants.search(owner=owner))), accepting=True,
                                               over_capacity="review", emails_on=True, **dict(defaults, **fields))
            self.count("restaurants added")
        else:
            r.update(**fields)
            self.count("restaurants updated")
        self.rest[uid] = r
        self.hours(r, _obj(row.get("regular")) or [], _obj(row.get("special")) or [])
        self.tables(r, _obj(row.get("table_seats")) or [])

    def hours(self, r, regular, special):
        for p in app_tables.periods.search(restaurant=r):
            p.delete()
        week: dict = {str(i): [] for i in range(7)}
        for e in regular if isinstance(regular, list) else []:
            if not isinstance(e, (list, tuple)) or len(e) < 3 or e[0] not in DAYS:
                continue
            o, c = _s(e[1]), _s(e[2])
            if "Closed" in (o, c) or _hm(o) is None or _hm(c) is None:
                continue
            week[str(DAYS.index(e[0]))].append([o[:5], c[:5]])
        week = {k: B.intervals_text(B.clean_intervals(v)) for k, v in week.items()}
        app_tables.periods.add_row(restaurant=r, name="Opening hours", start=None, end=None, week=week, created=B.now_utc())
        for s in app_tables.special_days.search(restaurant=r):
            s.delete()
        days: dict = {}
        for e in special if isinstance(special, list) else []:
            if not isinstance(e, (list, tuple)) or len(e) < 3:
                continue
            d = _date(e[0])
            if d is None or d < self.today:
                continue
            day = days.setdefault(d, {"closed": False, "hours": [], "no_online": False})
            if "Closed" in (_s(e[1]), _s(e[2])):
                day["closed"] = True
            elif _hm(e[1]) is not None and _hm(e[2]) is not None:
                day["hours"].append([_s(e[1])[:5], _s(e[2])[:5]])
            if len(e) > 3 and e[3] is False:
                day["no_online"] = True
        for d, v in sorted(days.items()):
            hours = [] if v["closed"] else B.intervals_text(B.clean_intervals(v["hours"]))
            closed = v["closed"] or not hours
            app_tables.special_days.add_row(restaurant=r, date=d, label="Closed" if closed else "Special hours", closed=closed,
                                            hours=hours, no_online=bool(v["no_online"]) and not closed)
            self.count("special days")

    def tables(self, r, seats):
        rows = [e for e in (seats if isinstance(seats, list) else []) if isinstance(e, (list, tuple)) and len(e) >= 3]
        if not rows:
            return
        for t in app_tables.dining_tables.search(restaurant=r):
            t.delete()
        for j in app_tables.table_joins.search(restaurant=r):
            j.delete()
        for i, e in enumerate(rows):
            n = int(_num(e[2], 2) or 2)
            app_tables.dining_tables.add_row(restaurant=r, name=_s(e[0])[:20] or "T%d" % (i + 1), seats=max(1, min(n, 40)), min_party=1,
                                             shape="round" if n <= 2 else ("long" if n >= 6 else "square"), area="Main room",
                                             x=12 + (i % 5) * 18, y=18 + (i // 5) * 26, position=i, active=True)
            self.count("tables")

    def closures(self):
        """special_actions: "close reservations" on a date -> that day stays open, without online bookings."""
        for row in self.d.get("special_actions") or []:
            r = self.rest.get(_s(row.get("restaurant")).lower())
            d = _date(row.get("mydate"))
            if r is None or d is None or d < self.today or not _bool(row.get("close_reservations")):
                continue
            s = app_tables.special_days.get(restaurant=r, date=d)
            if s is not None:
                if not s["closed"]:
                    s["no_online"] = True
                continue
            iv, src = B.day_hours(B.Ctx(r), d)
            if not iv:
                continue
            app_tables.special_days.add_row(restaurant=r, date=d, label="Online booking closed", closed=False,
                                            hours=B.intervals_text(iv), no_online=True)
            self.count("special days")

    # ---- bookings
    def reservations(self):
        tokens: dict = {}
        for row in self.d.get("reservations") or []:
            r = self.rest.get(_s(row.get("restaurant")).lower()) or app_tables.restaurants.get(legacy_id=_s(row.get("restaurant")).lower())
            if r is None:
                self.count("bookings skipped (restaurant not imported)")
                continue
            token = re.sub(r"[^0-9a-f]", "", _s(row.get("reservation_uid")).lower())[:32]
            d, t = _date(row.get("mydate")), _hm(row.get("mytime"))
            if len(token) < 16 or d is None or t is None:
                self.count("bookings skipped (incomplete)")
                continue
            have = tokens.get(r.get_id())
            if have is None:
                have = tokens[r.get_id()] = {x["token"] for x in app_tables.reservations.search(restaurant=r)}
            if token in have:
                self.count("bookings already here")
                continue
            walk_in = _s(row.get("email")).lower() == "walk-in" or _s(row.get("name")).lower() == "walk-in"
            past = d < self.today
            if _s(row.get("status")).lower() == "deleted":
                status = "cancelled"
            elif _bool(row.get("done")) or (past and _bool(row.get("seated"))):
                status = "done"
            elif _bool(row.get("seated")):
                status = "seated"
            elif _bool(row.get("approved")):
                status = "confirmed"
            else:
                status = "declined" if past else "pending"
            created = _dt(row.get("reservation_request_time")) or B.now_utc()
            app_tables.reservations.add_row(
                restaurant=r, token=token, date=d, start_min=t, duration=int(r["duration_min"] or 120),
                party=max(1, int(_num(row.get("guests"), 2) or 2)), name="Walk-in" if walk_in else _s(row.get("name"))[:80],
                email="" if walk_in else _s(row.get("email")).lower()[:200], phone="" if walk_in else _s(row.get("phone"))[:40],
                notes=_s(row.get("special_comments"))[:1000], staff_note=_s(row.get("resto_comment"))[:1000], status=status,
                source="walk_in" if walk_in else "online", tables=[], review_reason="", capacity_pct=0, consent=False,
                created=created, updated=B.now_utc(), history=[{"at": B.now_utc().isoformat(), "what": "Imported from the old PlanPlate"}],
                language=None)
            have.add(token)
            self.count("bookings")

    # ---- menu files, photos
    def menu_files(self):
        for row in self.d.get("menu_files") or []:
            r = self.rest.get(_s(row.get("restaurant")).lower())
            key = _s(row.get("menu_id")).lower()
            if r is None or not UUID_RE.match(key):
                continue
            if app_tables.menu_files.get(key=key) is not None:
                continue
            lang = _s(row.get("language")).lower()
            app_tables.menu_files.add_row(restaurant=r, key=key, title=(_s(row.get("file_description")) or "Menu")[:60],
                                          language=lang if lang in B.LANGS else "", file=None, content_type="",
                                          position=len(list(app_tables.menu_files.search(restaurant=r))), created=B.now_utc())
            self.count("menu files waiting for their file")
        if self.n.get("menu files waiting for their file"):
            self.warn("CSV files can't carry the menu PDFs/photos: upload each one again on the Menu page (Menu files). "
                      "Old links to them work again as soon as they're uploaded.")

    def gallery(self):
        from . import Media
        for row in self.d.get("gallery_flags") or []:
            r = self.rest.get(_s(row.get("restaurant_id")).lower())
            url, pid = _s(row.get("secure_url")), _s(row.get("public_id"))
            if r is None or not url.startswith("https://res.cloudinary.com/") or not pid:
                continue
            if app_tables.photos.get(restaurant=r, public_id=pid) is not None:
                continue
            try:
                Media._new_row(r, kind="image", provider="cloudinary", url=url, public_id=pid, in_gallery=True, caption="",
                               format=url.rsplit(".", 1)[-1][:10] if "." in url.rsplit("/", 1)[-1] else "")
                self.count("gallery photos")
            except ValueError as e:
                self.warn(str(e))

    def gallery_style(self):
        from . import Media
        names = {"theme": "theme", "background_options": "bg_style", "framing": "picture_style", "image_size": "size",
                 "motion_on_scroll": "motion", "secondary_color": "accent", "bg_color": "background", "gallery_title": "heading"}
        for row in self.d.get("cloudinary_related") or []:
            r = self.rest.get(_s(row.get("resto_id")).lower())
            if r is None:
                continue
            s = Media.site_row(r)
            style = {new: _s(row.get(old)) for old, new in names.items() if _s(row.get(old))}
            s["gallery"] = Media.clean_style(style, Media.gallery_style(s))
            self.count("gallery styles")
