"""The demo restaurant, so PlanPlate never looks empty: Maison Lumière, a made-up bistro in Old Montréal (fictional:
any likeness to a real restaurant is a coincidence). Its booking form (#book/maison-lumiere), menu (#menu/maison-lumiere)
and generated website (/_/api/site/maison-lumiere) are public, and the standalone demo website (maison-lumiere-site)
books through it.

Loaded automatically the first time anyone opens the dashboard or the demo's booking form (ensure_loaded), removed or
reloaded from Admin -> Demo data. Removing it is remembered: it doesn't come back by itself.

The demo owner (is_demo=True, an @example.com address, no password) can't sign in. ADMIN_EMAILS get the demo as
managers, so the admin can look around it from their own dashboard. Every row hangs off restaurants owned by demo users,
so remove() deletes exactly what load() added, and real restaurants are never touched.
"""
import datetime as dt

import anvil.users
from anvil.tables import app_tables

from . import common as C

OWNER = ("Camille Moreau", "camille.demo@example.com")
SLUG = "maison-lumiere"
LEGACY_ID = "4d2c1f0a-9b7e-4c3d-8a6f-2e5b7c9d1a30"  # a made-up old-PlanPlate id: shows the old embed code working
GUESTS = [("Élise Martin", "elise.martin@example.com", "+1 514 555 0101"), ("Jonas Berg", "jonas.berg@example.com", "+1 514 555 0102"),
          ("Priya Shah", "priya.shah@example.com", "+1 514 555 0103"), ("Tom O'Neill", "tom.oneill@example.com", "+1 514 555 0104"),
          ("Marta Kalniņa", "marta.k@example.com", "+1 514 555 0105"), ("Lucas Moreau", "lucas.moreau@example.com", "+1 438 555 0106"),
          ("Hana Sato", "hana.sato@example.com", "+1 438 555 0107"), ("Oskar Lind", "oskar.lind@example.com", "+1 438 555 0108"),
          ("Sofia Rossi", "sofia.rossi@example.com", "+1 514 555 0109"), ("Daniel Kim", "daniel.kim@example.com", "+1 514 555 0110"),
          ("Gabrielle Tremblay", "g.tremblay@example.com", "+1 514 555 0111"), ("Noah Fischer", "noah.fischer@example.com", "+1 514 555 0112")]
MENU = [
    ("Entrées", "", [("Soupe à l'oignon", "$14", "Gruyère crouton, slow-cooked onions", ["V"]),
                    ("Huîtres", "$24", "Six Malpeque oysters, shallot mignonette", ["GF"]),
                    ("Pâté de campagne", "$16", "Pickles, grilled sourdough", []),
                    ("Salade de betteraves", "$15", "Roasted beets, chèvre, walnuts", ["V", "GF"])]),
    ("Plats", "Served with seasonal vegetables", [("Confit de canard", "$36", "Lentils du Puy, orange jus", ["GF"]),
                                                  ("Steak frites", "$42", "AAA striploin, béarnaise, hand-cut fries", ["GF"]),
                                                  ("Truite de l'Estrie", "$34", "Brown butter, capers, lemon", []),
                                                  ("Risotto aux champignons", "$29", "Wild mushrooms, parmesan, thyme", ["V", "GF"])]),
    ("Desserts", "", [("Crème brûlée", "$12", "Tahitian vanilla", ["V", "GF"]), ("Tarte Tatin", "$13", "Crème fraîche", ["V"]),
                      ("Pouding chômeur", "$12", "Maple syrup from Saint-Hippolyte", ["V"])]),
    ("Vins", "By the glass", [("Crémant de Bourgogne", "$15", "", ["VG"]), ("Côtes du Rhône", "$13", "", ["VG"]),
                              ("Sancerre", "$17", "", ["VG"])]),
]
DEMO_TABLES: list = []  # rows hang off the demo restaurant (see remove)


def state():
    return C.get_setting("demo", "never")  # "never" | "loaded" | "removed"


def ensure_loaded():
    """Called from the dashboard and the demo's public pages: loads the demo once, unless an admin removed it."""
    if state() != "never":
        return
    try:
        load()
    except Exception as e:  # never let the demo break a real page; Admin -> Demo data can retry
        print("demo restaurant failed to load:", repr(e))
        remove(remember=False)


def _as(user):
    """Act as `user` for the Portal/Menu/Board calls (they check who is signed in). Returns who was signed in before."""
    before = anvil.users.get_user()
    anvil.users.force_login(user)
    return before


def _back(before):
    if before is None:
        anvil.users.logout()
    else:
        anvil.users.force_login(before)


def load():
    remove(remember=False)
    owner = app_tables.users.get(email=OWNER[1]) or app_tables.users.add_row(email=OWNER[1], enabled=False)
    owner.update(display_name=OWNER[0], is_demo=True, signed_up=C.now() - dt.timedelta(days=200))
    before = _as(owner)
    try:
        _build()
    finally:
        _back(before)
    C.set_setting("demo", "loaded")
    return counts()


def _reserve(Portal, rid, data):
    out = Portal.save_reservation(rid, dict(data, force=True))
    row = app_tables.reservations.get_by_id(out["id"]) if out.get("ok") else None
    if row is not None:
        row.update(consent=True, consent_at=C.now(), pp_consent=True, pp_consent_at=C.now())
    return out


def _build():
    from . import Board, Booking as B, Menu, Portal, Site
    rid = Portal.create_restaurant("Maison Lumière", "America/Toronto", True)["id"]
    r = app_tables.restaurants.get_by_id(rid)
    if r is None:
        raise RuntimeError("the demo restaurant was not created")
    if app_tables.restaurants.get(slug=SLUG) is None:  # a real restaurant may already use the address: then keep the generated one
        r.update(slug=SLUG)
    if app_tables.restaurants.get(legacy_id=LEGACY_ID) is None:
        r.update(legacy_id=LEGACY_ID)
    Portal.save_settings(rid, {
        "description": "A small French bistro in Old Montréal: seasonal cooking, natural wine and a terrace on the square.",
        "address": "88 rue Saint-Paul Ouest, Montréal, QC", "phone": "+1 514 555 0188", "email": "bonjour@maisonlumiere.example",
        "form_note": "We hold tables for 15 minutes. For groups larger than 8, please call us.",
        "form_notes": {"fr": "Nous gardons les tables 15 minutes. Pour les groupes de plus de 8, appelez-nous.",
                       "lv": "Galdiņu turam 15 minūtes. Grupām, kas lielākas par 8, lūdzu, zvaniet."},
        "max_auto_party": 6, "languages": ["fr", "lv"], "msg_confirmed": "Street parking is free after 18:00 on rue Saint-Paul."})
    today = B.local_now(r).date()
    year = today.year
    Portal.save_period(rid, {"name": "Summer terrace %d" % (year + 1), "start": "%d-06-01" % (year + 1), "end": "%d-08-31" % (year + 1),
                             "week": {str(i): [["11:30", "23:00"]] for i in range(7)}})
    Portal.save_special(rid, {"date": "%d-12-24" % year, "to": "%d-12-26" % year, "label": "Christmas", "closed": True})
    Portal.save_special(rid, {"date": "%d-12-31" % year, "label": "New Year's Eve dinner", "closed": False, "hours": [["19:00", "00:00"]]})
    for i, (title, desc, dishes) in enumerate(MENU):
        sid = Menu.save_section(rid, {"title": title, "description": desc})["sections"][i]["id"]
        for name, price, ddesc, tags in dishes:
            Menu.save_item(rid, {"section_id": sid, "name": name, "price": price, "description": ddesc, "tags": tags})
    Board.save_dish_special(rid, {"title": "Bouillabaisse", "price": "$38", "description": "Saffron broth, rouille, the day's catch", "when": "today"})
    Board.save_dish_special(rid, {"title": "Friday oysters", "price": "$3 each", "when": "always", "days": [4]})
    Board.post_photo(rid, {"text": "The first apples from Rougemont are in: tarte Tatin is back on the menu."})
    Board.save_event(rid, {"title": "Jazz on the terrace", "date": (today + dt.timedelta(days=6)).isoformat(), "start": "19:00", "end": "22:00",
                           "kind": "public", "description": "The Lumière trio plays from 19:00. Usual menu, book as normal."})
    Board.save_event(rid, {"title": "Wine dinner: the Loire", "date": (today + dt.timedelta(days=13)).isoformat(), "start": "18:30",
                           "end": "22:30", "kind": "public", "description": "Five wines, five courses. $95 per person."})
    # past visits (regulars, a no-show, a cancellation) ...
    for back, g, st in [(40, 0, "done"), (26, 0, "done"), (12, 0, "done"), (33, 2, "done"), (19, 2, "done"), (5, 2, "done"),
                        (21, 4, "no_show"), (9, 1, "done"), (15, 6, "cancelled"), (3, 8, "done")]:
        name, email, phone = GUESTS[g]
        _reserve(Portal, rid, {"date": (today - dt.timedelta(days=back)).isoformat(), "time": "19:00", "party": 2 + g % 3, "name": name,
                               "email": email, "phone": phone, "source": "online", "status": st})
    # ... today and the next open days, at real dinner times ...
    ctx = B.Ctx(r)
    open_days = [today + dt.timedelta(days=dd) for dd in range(0, 14) if B.start_times(ctx, today + dt.timedelta(days=dd))][:4]
    g = 0
    for k, d in enumerate(open_days):
        times = B.start_times(B.Ctx(r), d)
        dinner = [t for t in times if t >= 18 * 60] or times
        for j in range(5 if k == 0 else 3):
            name, email, phone = GUESTS[g % len(GUESTS)]
            _reserve(Portal, rid, {"date": d.isoformat(), "time": B.hm(dinner[(j * 2) % len(dinner)]), "party": [2, 4, 2, 3, 6][j % 5],
                                   "name": name, "email": email, "phone": phone, "source": ["online", "phone", "walk_in"][g % 3],
                                   "notes": "Window table if possible" if g == 3 else ("Birthday" if g == 5 else "")})
            g += 1
    # ... and two requests waiting for approval
    if open_days:
        d = open_days[-1]
        for n, (time, party, why) in enumerate([("19:30", 2, "The restaurant is 86% booked at this time (auto-approval stops at 80%)."),
                                                ("20:00", 8, "A party of 8 is above the auto-approval limit of 6.")]):
            out = _reserve(Portal, rid, {"date": d.isoformat(), "time": time, "party": party, "name": ["Clara Weiss", "The Johnson party"][n],
                                         "phone": "+1 514 555 02%02d" % n, "email": "request%d@example.com" % n, "source": "online",
                                         "status": "pending", "notes": ["Anniversary dinner", "Company dinner, one vegan"][n]})
            row = app_tables.reservations.get_by_id(out["id"]) if out.get("ok") else None
            if row is not None:
                row.update(review_reason=why, capacity_pct=86 if n == 0 else 40)
    # the guest book's own notes
    from . import Guests
    for gi, note, tags in [(0, "Likes the corner table by the window. Sparkling water.", ["Regular", "VIP"]),
                           (2, "Allergic to shellfish.", ["Regular", "Allergy"]), (4, "Missed a booking once: call to confirm.", [])]:
        key = Guests.key_of(GUESTS[gi][1], GUESTS[gi][2], GUESTS[gi][0])
        app_tables.guests.add_row(restaurant=r, key=key, note=note, tags=tags, vip="VIP" in tags, updated=C.now())
    # the website PlanPlate builds for it, and the admins as managers
    try:
        Site.load_demo_site(rid)
    except Exception as e:  # the website is a bonus: the restaurant itself must load
        print("demo website:", e)
    from . import Accounts
    for email in Accounts.ADMIN_EMAILS:
        Portal.invite_member(rid, email, "manager")
    return rid


def remove(remember=True):
    demo_owners = list(app_tables.users.search(is_demo=True))
    for r in list(app_tables.restaurants.search()):
        if r["owner"] in demo_owners:
            for table in (app_tables.reservations, app_tables.periods, app_tables.special_days, app_tables.dining_tables,
                          app_tables.table_joins, app_tables.members, app_tables.menu_items, app_tables.menu_sections,
                          app_tables.specials, app_tables.posts, app_tables.events, app_tables.sites, app_tables.photos,
                          app_tables.guests, app_tables.menu_files):
                for row in list(table.search(restaurant=r)):
                    row.delete()
            r.delete()
    for u in demo_owners:
        u.delete()
    if remember:
        C.set_setting("demo", "removed")
    return counts()


def counts():
    owners = list(app_tables.users.search(is_demo=True))
    rs = [r for r in app_tables.restaurants.search() if r["owner"] in owners]
    return {"users": len(owners), "restaurants": len(rs),
            "reservations": sum(len(app_tables.reservations.search(restaurant=r)) for r in rs)}
