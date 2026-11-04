"""Server tests against the strict mock of Anvil (tools/testing/mock).

    python tools/testing/test_server.py          -> prints ALL OK, or the first failure

call(name, ...) runs a server function the way the browser does: by name, with require_user enforced,
and the reply must be JSON (a datetime or a row in a reply fails here, like it would break the page).
Add tests for every new server function: the happy path, bad input, and someone who isn't allowed.
"""
import datetime as dt
import importlib
import json
import os
import pathlib
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
_tmp = pathlib.Path(tempfile.mkdtemp())
shutil.copytree(PROJECT / "server_code", _tmp / "app")
(_tmp / "app" / "__init__.py").write_text("")
os.environ["ANVIL_APP_YAML"] = str(PROJECT / "anvil.yaml")  # the mock's tables follow the app's own schema
sys.path[:0] = [str(HERE / "mock"), str(_tmp)]
import anvil.server  # noqa: E402
import anvil.users  # noqa: E402
from anvil.tables import app_tables as T  # noqa: E402

MODS = {p.stem: importlib.import_module("app." + p.stem) for p in sorted((PROJECT / "server_code").glob("*.py"))}
now = dt.datetime.now(dt.timezone.utc)


def call(name, *args):
    r = anvil.server.call(name, *args)
    json.dumps(r)  # strict: must be JSON-able
    return r


def as_user(row):
    anvil.users.CURRENT[0] = row
    anvil.server.session.use(row.get_id() if row is not None else None)


def denied(name, *args):
    try:
        call(name, *args)
    except anvil.server.PermissionDenied:
        return True
    return False


def ok(r, msg=""):
    assert isinstance(r, dict) and r.get("ok"), (msg, r)
    return r


def bad(r, msg=""):
    assert isinstance(r, dict) and r.get("ok") is False and r.get("error"), (msg, r)
    return r


def person(email, name=None, **kw):
    return T.users.add_row(email=email, enabled=True, signed_up=now, display_name=name, **kw)



from app import Booking as B, Portal as P, Public as G, Menu as M
from app import Media as MD, Board as BD, Site as S
import anvil.email  # noqa: E402
anvil.server.ORIGIN[0] = "https://planplate-test.anvil.app"  # the address the old tests expect

# ---------------------------------------------------------------------------------- PlanPlate's booking rules (from before the rebuild)
MODS["common"].set_setting("demo", "removed")  # the demo restaurant is tested on its own, at the end
TODAY = now.date()


def next_weekday(wd, min_days=2):
    d = TODAY + dt.timedelta(days=min_days)
    while d.weekday() != wd:
        d += dt.timedelta(days=1)
    return d


def ok(r, msg=''):
    assert r.get('ok'), (msg, r)
    return r


ana = T.users.add_row(email='ana@example.com', signed_up=now)
bob = T.users.add_row(email='bob@example.com', signed_up=now)
anvil.users.CURRENT[0] = ana
assert P.get_me()['display_name'] == 'Ana' and P.get_me()['alerts']['pending'] == 0

# ---- create restaurants: sample setup, slug, duplicate, ~10 restaurants
rid = ok(P.create_restaurant('Le Petit Jardin', 'UTC', True))['id']
r = T.restaurants.get_by_id(rid)
assert r['slug'] == 'le-petit-jardin' and r['duration_min'] == 120 and r['auto_threshold'] == 80
assert len(T.dining_tables.search(restaurant=r)) == 9 and len(T.periods.search(restaurant=r)) == 1
assert not P.create_restaurant('  ')['ok']
for i in range(9):
    ok(P.create_restaurant('Branch %d' % i, 'Europe/Riga', False))
assert P.create_restaurant('Le Petit Jardin')['id'] and T.restaurants.search(slug='le-petit-jardin-2')
dash = P.get_dashboard()
assert len(dash['restaurants']) == 11 and dash['restaurants'][0]['tables'] == 9 and dash['restaurants'][0]['seats'] == 32, dash['restaurants'][0]
json.dumps(dash)

# ---- opening hours: regular + summer + winter Mondays, special days override
# (fixed dates in 2037, which has the same weekdays as 2026, so they never land on the near booking days below)
H = P.get_hours(rid)
reg = H['periods'][0]
assert reg['name'] == 'Regular hours' and reg['week']['0'] == [] and reg['week']['4'] == [['12:00', '15:00'], ['18:00', '23:00']]
week = {str(i): [['09:00', '17:00']] for i in range(7)}
ok(P.save_period(rid, {'name': 'Summer 2037', 'start': '2037-06-01', 'end': '2037-08-31', 'week': dict(week, **{'0': [['09:00', '17:00']]})}))
ok(P.save_period(rid, {'name': 'Winter 2037', 'start': '2037-11-01', 'end': '2038-02-28', 'week': {'0': [['10:00', '12:00']], '1': [['17:00', '00:00']]}}))
assert not P.save_period(rid, {'name': 'Bad', 'start': '2037-05-02', 'end': '2037-05-01', 'week': {}})['ok']
ctx = B.Ctx(r)
summer_mon, winter_mon, spring_mon = dt.date(2037, 7, 6), dt.date(2037, 11, 16), dt.date(2037, 4, 6)
assert B.day_hours(ctx, summer_mon)[0] == [[540, 1020]] and B.day_hours(ctx, summer_mon)[1]['label'] == 'Summer 2037'
assert B.day_hours(ctx, winter_mon)[0] == [[600, 720]] and B.day_hours(ctx, winter_mon)[1]['label'] == 'Winter 2037'
assert B.day_hours(ctx, spring_mon)[0] == [] and B.day_hours(ctx, spring_mon)[1]['label'] == 'Regular hours'  # regular: closed Mondays
assert B.day_hours(ctx, dt.date(2037, 11, 17))[0] == [[1020, 1440]], 'closing at 00:00 means midnight'
assert B.day_hours(ctx, dt.date(2037, 11, 18))[0] == [], 'winter period has no Wednesday hours: closed'
H = ok(P.save_special(rid, {'date': '2037-12-24', 'to': '2037-12-26', 'label': 'Christmas', 'closed': True}, '2037-12'))
assert [c for c in H['calendar'] if c['date'] == '2037-12-25'][0]['kind'] == 'special'
ok(P.save_special(rid, {'date': '2037-11-16', 'label': 'Chef\'s dinner', 'closed': False, 'hours': [['19:00', '23:30'], ['18:00', '19:30']]}))
ctx = B.Ctx(r)
assert B.day_hours(ctx, winter_mon)[0] == [[1080, 1410]], 'special hours override, overlapping intervals merge'
assert B.day_hours(ctx, dt.date(2037, 12, 25))[0] == [] and B.day_hours(ctx, dt.date(2037, 12, 25))[1]['closed']
assert not P.save_special(rid, {'date': '2037-11-20', 'closed': False, 'hours': []})['ok']
H = P.get_hours(rid, '2037-11')
assert len(H['calendar']) == 30 and H['month'] == '2037-11' and len(H['periods']) == 3
json.dumps(H)

# ---- tables and joins
TB = P.get_tables(rid)
tid = {t['name']: t['id'] for t in TB['tables']}
assert len(TB['joins']) == 1 and TB['joins'][0]['days'] == [4, 5] and 18 in TB['open_hours']
assert not P.save_table(rid, {'name': 't1', 'seats': 2})['ok'], 'names are unique'
TB = ok(P.save_table(rid, {'name': 'Bar', 'seats': 3, 'shape': 'round'}))
assert any(t['name'] == 'Bar' for t in TB['tables'])
ok(P.save_table(rid, {'id': tid['T9'], 'min_party': 4}))
bad = P.save_join(rid, {'tables': [tid['T8'], tid['T9']], 'hours': [19], 'days': [5]})
assert not bad['ok'] and 'T8' in bad['error'], bad
ok(P.save_join(rid, {'tables': [tid['T4'], tid['T5'], tid['T6']], 'hours': [12, 13, 14], 'days': [], 'seats': 10}))
fri = next_weekday(4)
thu = fri - dt.timedelta(days=1)
ctx = B.Ctx(r)
u_fri = B.units_at(ctx, fri, 19 * 60)
assert any(sorted(u['ids']) == sorted([tid['T7'], tid['T8']]) and u['seats'] == 8 for u in u_fri), 'T7+T8 joined Fri dinner'
assert not any(len(u['ids']) > 1 for u in B.units_at(ctx, thu, 19 * 60)), 'no join on Thursday dinner'
assert any(len(u['ids']) == 3 and u['seats'] == 10 for u in B.units_at(ctx, thu, 13 * 60)), 'lunch join every day'
# split one hour out of a join (the "split at this hour" button saves the join without that hour)
j = [x for x in P.get_tables(rid)['joins'] if len(x['tables']) == 3][0]
ok(P.save_join(rid, dict(j, hours=[12, 13])))
assert not any(len(u['ids']) == 3 for u in B.units_at(B.Ctx(r), thu, 14 * 60 + 30))
TB = ok(P.save_join(rid, dict(j, hours=[])))  # no hours left = split all day
assert len(TB['joins']) == 1
json.dumps(TB)
# new tables on an empty floor plan land on free spots, never on top of another table (even one that was moved there)
empty = [x for x in P.get_dashboard()['restaurants'] if x['name'] == 'Branch 0'][0]['id']
for k in range(3):
    ok(P.save_table(empty, {}))
pos = [(t['x'], t['y']) for t in P.get_tables(empty)['tables']]
assert len(set(pos)) == 3 and all(abs(a[0] - b[0]) >= 14 for a in pos for b in pos if a != b), pos
moved = P.get_tables(empty)['tables'][0]
ok(P.save_positions(empty, [{'id': moved['id'], 'x': 66, 'y': 14}]))
pos = [(t['x'], t['y']) for t in ok(P.save_table(empty, {}))['tables']]
assert all(abs(a[0] - b[0]) >= 14 or abs(a[1] - b[1]) >= 18 for a in pos for b in pos if a != b), pos
# after a delete, a new table still comes last and the reply names it (the UI opens it for editing)
ok(P.delete_table(empty, moved['id']))
TB = ok(P.save_table(empty, {}))
assert TB['new_id'] == TB['tables'][-1]['id'] and len(set(t['name'] for t in TB['tables'])) == 4, TB['tables']

# ---- booking form (public, no user)
anvil.users.CURRENT[0] = None
form = ok(G.get_booking_form('le-petit-jardin'))
assert form['restaurant']['max_party'] == 8 and form['restaurant']['privacy_text'] and form['days']
assert any(dd['date'] == fri.isoformat() and dd['open'] for dd in form['days'])
assert not G.get_booking_form('nope')['ok']
# late in the evening, today is no longer offered (the form then starts on the next open day)
_real_now = B.local_now
for hh, open_today in ((21, False), (10, TODAY.weekday() != 0)):  # regular hours: closed Mondays
    B.local_now = lambda r, hh=hh: dt.datetime.combine(TODAY, dt.time(hh, 30))
    first = G.get_booking_form('le-petit-jardin')['days'][0]
    assert first['date'] == TODAY.isoformat() and first['open'] == open_today, (hh, first)
B.local_now = _real_now
sl = ok(G.get_slots('le-petit-jardin', fri.isoformat(), 2))
times = [s['time'] for s in sl['slots']]
assert times[0] == '12:00' and '14:00' in times and '14:15' not in times and '22:00' in times and '22:15' not in times, times
assert all(s['state'] == 'open' and not s['review'] for s in sl['slots'])
guest = {'name': 'Marie Curie', 'email': 'marie@example.com', 'phone': '+33 1 23 45 67 89', 'notes': 'Window please'}
assert not G.book('le-petit-jardin', dict(guest, date=fri.isoformat(), time='19:00', party=2))['ok'], 'consent required'
assert 'email' in G.book('le-petit-jardin', dict(guest, email='nope', consent=True, date=fri.isoformat(), time='19:00', party=2))['error']
assert not G.book('le-petit-jardin', dict(guest, consent=True, date=fri.isoformat(), time='19:07', party=2))['ok'], 'not a slot'
assert not G.book('le-petit-jardin', dict(guest, consent=True, date=fri.isoformat(), time='19:00', party=9))['ok'], 'party > max'
assert not G.book('le-petit-jardin', dict(guest, consent=True, website='spam', date=fri.isoformat(), time='19:00', party=2))['ok']
b1 = ok(G.book('le-petit-jardin', dict(guest, consent=True, date=fri.isoformat(), time='19:00', party=2)))
assert b1['status'] == 'confirmed' and len(b1['token']) == 32
row = T.reservations.get(token=b1['token'])
assert row['consent'] and row['consent_text'] and row['consent_at'] and row['duration'] == 120
assert [ctx.by_id[i]['name'] for i in row['tables']][0] in ('T1', 'T2', 'T3'), 'smallest table that fits'

# fill the restaurant: 32 + 3 (Bar) = 35 seats. 2-tops 6, 4-tops 20 (T7+T8 joined = 8), T9 6, Bar 3.
seats = B.Ctx(r).total_seats
assert seats == 35, seats
tokens = [b1['token']]
for party in (2, 2, 4, 4, 4):  # T2, T3, T4, T5, T6 → 2+2+2+4+4+4 = 18 seats → 51%
    b = ok(G.book('le-petit-jardin', dict(guest, consent=True, date=fri.isoformat(), time='19:00', party=party)))
    assert b['status'] == 'confirmed', b
    tokens.append(b['token'])
b = ok(G.book('le-petit-jardin', dict(guest, consent=True, date=fri.isoformat(), time='19:30', party=8)))  # T7+T8: 26 seats = 74%
assert b['status'] == 'confirmed' and len(T.reservations.get(token=b['token'])['tables']) == 2, 'joined table for 8'
pct = B.occupancy(B.Ctx(r), fri, 19 * 60, 120)
assert pct == 74, pct
b = ok(G.book('le-petit-jardin', dict(guest, consent=True, date=fri.isoformat(), time='19:30', party=4)))  # T9 (min 4): 74% → still under 80
assert b['status'] == 'confirmed', b
sl = ok(G.get_slots('le-petit-jardin', fri.isoformat(), 2))
s1930 = [s for s in sl['slots'] if s['time'] == '19:30'][0]
assert s1930['state'] == 'open' and s1930['review'], ('Bar is free, but 91% booked → needs approval', s1930)
assert [s for s in sl['slots'] if s['time'] == '12:00'][0]['review'] is False
pend = ok(G.book('le-petit-jardin', dict(guest, name='Late Larry', consent=True, date=fri.isoformat(), time='19:30', party=2)))
assert pend['status'] == 'pending'
prow = T.reservations.get(token=pend['token'])
assert '91%' in prow['review_reason'] and prow['capacity_pct'] == 91, prow['review_reason']
sl = ok(G.get_slots('le-petit-jardin', fri.isoformat(), 2))
assert [s for s in sl['slots'] if s['time'] == '19:30'][0]['state'] == 'full', 'pending requests hold their table'
assert [s for s in sl['slots'] if s['time'] == '21:30'][0]['state'] == 'open'

# a big party is never auto-approved
anvil.users.CURRENT[0] = ana
ok(P.save_settings(rid, {'max_auto_party': 3}))
anvil.users.CURRENT[0] = None
big = ok(G.book('le-petit-jardin', dict(guest, name='Big Group', consent=True, date=thu.isoformat(), time='12:30', party=4)))
assert big['status'] == 'pending' and 'party of 4' in T.reservations.get(token=big['token'])['review_reason'].lower()

# ---- manager: alerts, analysis, approve / decline
anvil.users.CURRENT[0] = ana
al = P.get_alerts()
assert al['pending'] == 2 and al['items'][0]['date'] <= al['items'][1]['date'], al
day = P.get_day(rid, fri.isoformat())
assert day['summary']['bookings'] == 9 and day['summary']['covers'] == 32 and day['summary']['peak']['pct'] == 100, day['summary']
assert len(day['pending']) == 2 and day['pending'][0]['analysis']['threshold'] == 80
lp = [p for p in day['pending'] if p['name'] == 'Late Larry'][0]
assert lp['analysis']['pct_without'] == 91 and lp['analysis']['pct_with'] == 100 and lp['table_names'] == ['Bar'], lp
assert day['hours'] == [['12:00', '15:00'], ['18:00', '23:00']] and day['curve'] and day['nav']['restaurant']['pending'] == 2
json.dumps(day)
out = ok(P.set_status(rid, lp['id'], 'confirmed', fri.isoformat()))
assert out['alerts']['pending'] == 1 and T.reservations.get(token=pend['token'])['status'] == 'confirmed'
assert T.reservations.get(token=pend['token'])['history'][-1]['what'] == 'Approved by staff.'
big_id = T.reservations.get(token=big['token']).get_id()
ok(P.set_status(rid, big_id, 'declined'))
assert P.get_alerts()['pending'] == 0

# manager phone booking: auto table, conflicts, force
opts = ok(P.get_options(rid, fri.isoformat(), '19:00', 2, 120))
assert opts['units'] == [] and opts['pct'] == 100
c = P.save_reservation(rid, {'date': fri.isoformat(), 'time': '19:00', 'party': 2, 'name': 'Phone Pat', 'source': 'phone'})
assert not c['ok'] and c['conflict'], c
c = ok(P.save_reservation(rid, {'date': fri.isoformat(), 'time': '19:00', 'party': 2, 'name': 'Phone Pat', 'source': 'phone', 'tables': [tid['T1']], 'force': True}))
assert c['warnings'] and c['day']['summary']['bookings'] == 10
c = ok(P.save_reservation(rid, {'date': thu.isoformat(), 'time': '12:00', 'party': 3, 'name': 'Walk In', 'source': 'walk_in'}))
wi = T.reservations.get_by_id(c['id'])
assert wi['status'] == 'confirmed' and wi['source'] == 'walk_in' and wi['token']
c = ok(P.save_reservation(rid, {'id': c['id'], 'date': thu.isoformat(), 'time': '13:00', 'party': 3, 'name': 'Walk In', 'duration': 90, 'staff_note': 'VIP'}))
assert wi['start_min'] == 780 and wi['duration'] == 90 and wi['staff_note'] == 'VIP'
cl = P.save_reservation(rid, {'date': thu.isoformat(), 'time': '09:00', 'party': 2, 'name': 'Early'})
assert not cl['ok'] and 'closed' in cl['error'], cl

# ---- the guest's page: view, change, cancel
anvil.users.CURRENT[0] = None
g = ok(G.get_reservation(b1['token']))
assert g['reservation']['name'] == 'Marie Curie' and g['can_change'] and g['can_cancel'] and g['days'] and 'email' not in g['reservation']
assert not G.get_reservation('0' * 32)['ok'] and not G.get_reservation('../../x')['ok']
sat = fri + dt.timedelta(days=1)
g = ok(G.change_reservation(b1['token'], dict(guest, date=sat.isoformat(), time='20:00', party=3)))
row = T.reservations.get(token=b1['token'])
assert row['date'] == sat and row['start_min'] == 1200 and row['party'] == 3 and row['status'] == 'confirmed', row['history']
assert 'moved to' in row['history'][-1]['what']
g = ok(G.change_reservation(b1['token'], dict(guest, name='Marie S. Curie', date=sat.isoformat(), time='20:00', party=3)))
assert g['reservation']['name'] == 'Marie S. Curie' and row['tables']
g = ok(G.cancel_reservation(b1['token']))
assert g['reservation']['status'] == 'cancelled' and not g['can_change'] and not g['can_cancel']
assert not G.cancel_reservation(b1['token'])['ok']
assert not G.change_reservation(b1['token'], dict(guest, date=sat.isoformat(), time='20:00', party=3))['ok']

# ---- walk-in mode: past the threshold, online booking stops and the form suggests walking in
anvil.users.CURRENT[0] = ana
ok(P.set_status(rid, T.reservations.get(name='Phone Pat').get_id(), 'cancelled'))  # frees T1
ok(P.save_settings(rid, {'over_capacity': 'walk_in', 'max_auto_party': 8}))
anvil.users.CURRENT[0] = None
sl = ok(G.get_slots('le-petit-jardin', fri.isoformat(), 2))
assert [s for s in sl['slots'] if s['time'] == '19:30'][0]['state'] in ('walk_in', 'full')
assert [s for s in sl['slots'] if s['time'] == '18:00'][0]['state'] == 'walk_in', [s for s in sl['slots'] if s['time'] == '18:00']
assert [s for s in sl['slots'] if s['time'] == '12:00'][0]['state'] == 'open'
# closed day and closed online booking
closed_day = fri + dt.timedelta(days=14)
anvil.users.CURRENT[0] = ana
ok(P.save_special(rid, {'date': closed_day.isoformat(), 'label': 'Staff party', 'closed': True}))
anvil.users.CURRENT[0] = None
assert G.get_slots('le-petit-jardin', closed_day.isoformat(), 2)['slots'] == []
anvil.users.CURRENT[0] = ana
ok(P.save_settings(rid, {'accepting': False}))
anvil.users.CURRENT[0] = None
assert not G.book('le-petit-jardin', dict(guest, consent=True, date=thu.isoformat(), time='12:00', party=2))['ok']
assert G.get_booking_form('le-petit-jardin')['restaurant']['accepting'] is False

# ---- settings, permissions, duplicate, delete
anvil.users.CURRENT[0] = ana
S = P.get_settings(rid)
assert S['settings']['slug'] == 'le-petit-jardin' and S['origin'].startswith('https://')
assert not P.save_settings(rid, {'slug': 'Le Petit Jardin 2'})['ok'], 'slug taken'
assert P.save_settings(rid, {'auto_threshold': 500})['settings']['auto_threshold'] == 100
assert not P.save_settings(rid, {'timezone': 'Not/A Zone'})['ok']
anvil.users.CURRENT[0] = bob
for fn, args in ((P.get_day, (rid,)), (P.get_settings, (rid,)), (P.save_table, (rid, {'name': 'X'})), (P.set_status, (rid, big_id, 'confirmed'))):
    try:
        fn(*args); raise AssertionError('bob reached ana\'s restaurant via %s' % fn.__name__)
    except anvil.server.PermissionDenied:
        pass
assert P.get_dashboard()['restaurants'] == []
anvil.users.CURRENT[0] = None
try:
    P.get_dashboard(); raise AssertionError('signed out')
except anvil.users.AuthenticationFailed:
    pass
anvil.users.CURRENT[0] = ana
dup = ok(P.duplicate_restaurant(rid, 'Le Petit Jardin Riga'))
d2 = T.restaurants.get_by_id(dup['id'])
assert len(T.dining_tables.search(restaurant=d2)) == 10 and len(T.periods.search(restaurant=d2)) == 3 and len(T.table_joins.search(restaurant=d2)) == 1
assert len(T.special_days.search(restaurant=d2)) == 5 and not T.reservations.search(restaurant=d2)
j2 = T.table_joins.search(restaurant=d2)[0]
assert all(T.dining_tables.get_by_id(i)['restaurant'] == d2 for i in j2['tables']), 'joins point at the copied tables'
assert not P.delete_restaurant(dup['id'], 'wrong')['ok']
ok(P.delete_restaurant(dup['id'], 'Le Petit Jardin Riga'))
assert T.restaurants.get_by_id(dup['id']) is None and not T.dining_tables.search(restaurant=d2)
TB = ok(P.delete_table(rid, tid['T8']))
assert not any(tid['T8'] in j['tables'] for j in TB['joins'])

# embed script
resp = anvil.server.ENDPOINTS['/embed.js'](r='le-petit-jardin')
assert resp.status == 200 and '"le-petit-jardin"' in resp.body and 'planplate-test.anvil.app' in resp.body and 'javascript' in resp.headers['Content-Type']

# ---- emails: guest confirmations in the booking's language, staff alert when pending
import anvil.email
OUT = anvil.email.OUTBOX
anvil.users.CURRENT[0] = ana
ok(P.save_settings(rid, {'accepting': True, 'over_capacity': 'review', 'auto_threshold': 80, 'max_auto_party': 4,
                         'languages': ['fr', 'lv'], 'msg_confirmed': 'Parking is behind the building.', 'email': 'hello@jardin.test'}))
assert P.get_settings(rid)['settings']['languages'] == ['en', 'fr', 'lv']
anvil.users.CURRENT[0] = None
assert G.get_booking_form('le-petit-jardin', 'fr')['lang'] == 'fr' and G.get_booking_form('le-petit-jardin', 'de')['lang'] == 'en'
del OUT[:]
nxt = next_weekday(2)  # a Wednesday: open, empty
e1 = ok(G.book('le-petit-jardin', dict(guest, consent=True, date=nxt.isoformat(), time='12:00', party=2, language='fr')))
assert e1['status'] == 'confirmed' and len(OUT) == 1, OUT
m = OUT[0]
assert m['to'] == guest['email'] and m['subject'].startswith('Votre table chez Le Petit Jardin') and m['reply_to'] == 'hello@jardin.test'
assert '#r/' + e1['token'] in m['html'] and 'Parking is behind' in m['text'] and 'mercredi' in m['html'], m['text']
assert T.reservations.get(token=e1['token'])['language'] == 'fr'
assert T.reservations.get(token=e1['token'])['consent_text'].startswith('Nous utilisons') and G.get_reservation(e1['token'])['restaurant']['privacy_text'].startswith('Nous')
assert set(G.get_booking_form('le-petit-jardin')['privacy']) == {'en', 'fr', 'lv'}
del OUT[:]
e2 = ok(G.book('le-petit-jardin', dict(guest, name='Big Table', consent=True, date=nxt.isoformat(), time='13:00', party=6)))
assert e2['status'] == 'pending' and len(OUT) == 2, OUT
assert OUT[0]['subject'].startswith("We've received your request") and OUT[1]['to'] == 'ana@example.com' and OUT[1]['subject'].startswith('Approval needed: Big Table')
anvil.users.CURRENT[0] = ana
ok(P.save_settings(rid, {'notify_email': 'floor@jardin.test'}))
assert not P.save_settings(rid, {'notify_email': 'nope'})['ok']
del OUT[:]
e2row = T.reservations.get(token=e2['token'])
ok(P.set_status(rid, e2row.get_id(), 'confirmed'))
assert len(OUT) == 1 and 'is confirmed' in OUT[0]['subject'], OUT
del OUT[:]
ok(P.set_status(rid, e2row.get_id(), 'cancelled'))
assert len(OUT) == 1 and 'cancelled' in OUT[0]['subject'] and '#book/le-petit-jardin' in OUT[0]['html']
del OUT[:]
anvil.users.CURRENT[0] = None
e3 = ok(G.book('le-petit-jardin', dict(guest, name='Grand Party', consent=True, date=nxt.isoformat(), time='13:30', party=5, language='lv')))
assert [x['to'] for x in OUT] == [guest['email'], 'floor@jardin.test'] and 'pieprasījumu' in OUT[0]['subject']
anvil.users.CURRENT[0] = ana
del OUT[:]
ok(P.set_status(rid, T.reservations.get(token=e3['token']).get_id(), 'declined'))
assert len(OUT) == 1 and 'pieprasījumu' in OUT[0]['subject'] and 'Diemžēl' in OUT[0]['text']
ok(P.save_settings(rid, {'emails_on': False}))
del OUT[:]
c = ok(P.save_reservation(rid, {'date': nxt.isoformat(), 'time': '14:00', 'party': 2, 'name': 'Phone Guest', 'email': 'p@example.com', 'notify': True}))
assert OUT == [], 'guest emails switched off'
ok(P.save_settings(rid, {'emails_on': True}))
c = ok(P.save_reservation(rid, {'date': nxt.isoformat(), 'time': '14:15', 'party': 2, 'name': 'Phone Guest 2', 'email': 'p2@example.com', 'notify': True}))
assert len(OUT) == 1 and OUT[0]['to'] == 'p2@example.com' and c['emailed'] == ['guest']

# ---- team: managers and staff, invites by email
del OUT[:]
assert not P.invite_member(rid, 'nope', 'staff')['ok'] and not P.invite_member(rid, 'ana@example.com', 'staff')['ok']
tm = ok(P.invite_member(rid, 'Bob@Example.com', 'staff'))
assert [m['role'] for m in tm['team']] == ['owner', 'staff'] and tm['team'][1]['joined'] and len(OUT) == 1 and 'gave you access' in OUT[0]['subject']
assert not P.invite_member(rid, 'bob@example.com', 'manager')['ok'], 'no duplicates'
ok(P.invite_member(rid, 'carol@example.com', 'manager'))
bob_id = tm['team'][1]['id']
anvil.users.CURRENT[0] = bob
dash = P.get_dashboard()['restaurants']
assert [x['name'] for x in dash] == ['Le Petit Jardin'] and dash[0]['role'] == 'staff'
d = P.get_day(rid, nxt.isoformat())
assert d['nav']['restaurant']['role'] == 'staff' and d['summary']['bookings'] >= 2
ok(P.save_reservation(rid, {'date': nxt.isoformat(), 'time': '12:30', 'party': 2, 'name': 'Walk-in by Bob', 'source': 'walk_in'}))
for fn, args in ((P.get_hours, (rid,)), (P.get_tables, (rid,)), (P.get_settings, (rid,)), (P.invite_member, (rid, 'x@y.z')), (P.duplicate_restaurant, (rid,))):
    try:
        fn(*args); raise AssertionError('staff reached %s' % fn.__name__)
    except anvil.server.PermissionDenied:
        pass
assert P.get_alerts()['pending'] == 0
anvil.users.CURRENT[0] = ana
ok(P.set_member_role(rid, bob_id, 'manager'))
anvil.users.CURRENT[0] = bob
assert P.get_hours(rid)['nav']['restaurant']['role'] == 'manager' and P.get_settings(rid)['role'] == 'manager'
for fn, args in ((P.delete_restaurant, (rid, 'Le Petit Jardin')), (P.remove_member, (rid, bob_id))):
    try:
        fn(*args); raise AssertionError('manager reached %s' % fn.__name__)
    except anvil.server.PermissionDenied:
        pass
carol = T.users.add_row(email='carol@example.com', signed_up=now)
anvil.users.CURRENT[0] = carol
assert [x['role'] for x in P.get_dashboard()['restaurants']] == ['manager'], 'invite claimed on first sign-in'
anvil.users.CURRENT[0] = ana
team = P.get_team(rid)['team']
assert all(m['joined'] for m in team) and len(team) == 3
ok(P.remove_member(rid, bob_id))
anvil.users.CURRENT[0] = bob
assert P.get_dashboard()['restaurants'] == []
anvil.users.CURRENT[0] = ana

# ---- menu: sections, items, order, availability; public page and website feeds
A = M.get_menu_admin(rid)
assert A['sections'] == [] and 'VG' in A['tags']
assert not M.save_section(rid, {'title': ' '})['ok']
A = M.save_section(rid, {'title': 'Starters'}); A = M.save_section(rid, {'title': 'Mains', 'description': 'Served with bread'})
st_id, mn_id = A['sections'][0]['id'], A['sections'][1]['id']
A = M.save_item(rid, {'section_id': st_id, 'name': 'Onion soup', 'price': '€9', 'tags': ['V', 'XX']})
A = M.save_item(rid, {'section_id': st_id, 'name': 'Oysters', 'price': '€18', 'description': 'Six, with mignonette', 'tags': ['GF']})
A = M.save_item(rid, {'section_id': mn_id, 'name': 'Duck confit', 'price': '€26'})
assert [i['name'] for i in A['sections'][0]['items']] == ['Onion soup', 'Oysters'] and A['sections'][0]['items'][0]['tags'] == ['V']
oy = A['sections'][0]['items'][1]['id']
A = M.move_menu_row(rid, 'item', oy, -1)
assert [i['name'] for i in A['sections'][0]['items']] == ['Oysters', 'Onion soup']
A = M.move_menu_row(rid, 'section', mn_id, -1)
assert [x['title'] for x in A['sections']] == ['Mains', 'Starters']
A = M.save_item(rid, {'id': oy, 'name': 'Oysters', 'price': '€18', 'available': False, 'tags': ['GF']})
anvil.users.CURRENT[0] = None
pub = ok(M.get_menu('le-petit-jardin'))
assert [x['title'] for x in pub['sections']] == ['Mains', 'Starters'] and [i['name'] for i in pub['sections'][1]['items']] == ['Onion soup'], 'sold-out dishes are hidden'
resp = anvil.server.ENDPOINTS['/menu'](r='le-petit-jardin')
assert resp.status == 200 and json.loads(resp.body)['sections'][0]['items'][0]['name'] == 'Duck confit' and resp.headers['Access-Control-Allow-Origin'] == '*'
assert anvil.server.ENDPOINTS['/menu'](r='nope').status == 404
resp = anvil.server.ENDPOINTS['/menu.js'](r='le-petit-jardin')
assert 'data-planplate-' in resp.body and 'Duck confit' in resp.body and 'javascript' in resp.headers['Content-Type']
h = json.loads(anvil.server.ENDPOINTS['/hours'](r='le-petit-jardin').body)
assert len(h['week']) == 7 and len(h['next_days']) == 7 and h['week'][0]['day'] == 'Monday' and all('hours' in d for d in h['next_days'])
assert any(sd['label'] == 'Staff party' and sd['closed'] for sd in h['special_days']), h['special_days']
assert 'Monday' in anvil.server.ENDPOINTS['/hours.js'](r='le-petit-jardin').body
anvil.users.CURRENT[0] = bob
try:
    M.save_section(rid, {'title': 'Hack'}); raise AssertionError('bob is no longer a member')
except anvil.server.PermissionDenied:
    pass
anvil.users.CURRENT[0] = ana
dup = ok(P.duplicate_restaurant(rid, 'Jardin Two'))
d2 = T.restaurants.get_by_id(dup['id'])
assert len(T.menu_items.search(restaurant=d2)) == 3 and all(i['section']['restaurant'] == d2 for i in T.menu_items.search(restaurant=d2))
A = M.delete_section(rid, st_id)
assert [x['title'] for x in A['sections']] == ['Mains'] and len(T.menu_items.search(restaurant=r)) == 1
# ---- photos: upload to PlanPlate storage, gallery feed, captions, order, delete; Cloudinary when the secret is set
from app import Media as MD, Board as BD, Site as S
import base64, io, zipfile, hashlib
import anvil.secrets, anvil.http
PNG = 'data:image/png;base64,' + base64.b64encode(b'\x89PNG\r\n\x1a\n' + b'0' * 200).decode()
anvil.users.CURRENT[0] = ana
up = ok(MD.upload_photo(rid, {'image': PNG, 'thumb': PNG, 'width': 1600, 'height': 1066, 'caption': 'Terrace', 'in_gallery': True}))['photo']
assert up['provider'] == 'planplate' and up['url'].endswith('/_/api/photo/' + up['key']) and up['thumb_url'].endswith('?s=thumb'), up
assert not MD.upload_photo(rid, {'image': 'data:text/html;base64,PGI+'})['ok'], 'only pictures'
assert not MD.upload_photo(rid, {'image': 'data:image/png;base64,' + base64.b64encode(b'0' * (7 * 1024 * 1024)).decode()})['ok'], 'too big'
p2 = ok(MD.upload_photo(rid, {'image': PNG, 'in_gallery': True}))['photo']
p3 = ok(MD.upload_photo(rid, {'image': PNG}))['photo']
resp = anvil.server.ENDPOINTS['/photo/:key'](key=up['key'])
assert resp.status == 200 and resp.body.get_bytes().startswith(b'\x89PNG') and 'immutable' in resp.headers['Cache-Control']
assert anvil.server.ENDPOINTS['/photo/:key'](key=up['key'], s='thumb').status == 200
assert anvil.server.ENDPOINTS['/photo/:key'](key='nope').status == 404
feed = json.loads(anvil.server.ENDPOINTS['/gallery/:ref'](ref='le-petit-jardin').body)
assert [f['public_id'] for f in feed] == [up['key'], p2['key']] and feed[0]['alt'] == 'Terrace' and feed[0]['width'] == 1600, feed
assert anvil.server.ENDPOINTS['/gallery/:ref'](ref='nobody').status == 404
G = ok(MD.order_photos(rid, [p2['id'], up['id']]))
assert [p['key'] for p in G['photos']][:2] == [p2['key'], up['key']]
ok(MD.save_photo(rid, {'id': p2['id'], 'caption': 'Bar', 'in_gallery': False}))
assert [f['public_id'] for f in json.loads(anvil.server.ENDPOINTS['/gallery/:ref'](ref='le-petit-jardin').body)] == [up['key']]
g = ok(MD.get_gallery(rid))
assert g['storage'] == 'planplate' and g['feed_url'].endswith('/_/api/gallery/le-petit-jardin') and g['style']['theme'] == 'bento'
st = ok(MD.save_gallery_style(rid, {'theme': 'cinematic', 'size': 'huge', 'accent': '#AA3300', 'background': 'red', 'heading': 'Pictures'}))['style']
assert st['theme'] == 'cinematic' and st['size'] == 'md' and st['accent'] == '#aa3300' and st['background'] == '#1d1b18' and st['heading'] == 'Pictures'
# videos in PlanPlate storage, with byte ranges for Safari
vid = ok(MD.upload_video(rid, anvil.BlobMedia('video/mp4', b'v' * 1000, name='clip.mp4'), {'poster': PNG}))['photo']
assert vid['kind'] == 'video' and vid['poster_url'].endswith('?s=thumb')
assert not MD.upload_video(rid, anvil.BlobMedia('application/zip', b'z'))['ok']
assert MD._range(b'0123456789', 'bytes=2-5') == (206, b'2345', {'Content-Range': 'bytes 2-5/10'})
assert MD._range(b'0123456789', 'bytes=-3')[1] == b'789' and MD._range(b'0123456789', 'bytes=20-')[0] == 416 and MD._range(b'01', None)[0] == 200
# someone from another restaurant can't touch these photos
anvil.users.CURRENT[0] = bob
for fn, args in ((MD.get_gallery, (rid,)), (MD.upload_photo, (rid, {'image': PNG})), (MD.delete_photo, (rid, up['id']))):
    try:
        fn(*args); raise AssertionError('bob got in: %s' % fn.__name__)
    except anvil.server.PermissionDenied:
        pass
anvil.users.CURRENT[0] = ana
# Cloudinary: signed direct uploads, checked on the way back
anvil.secrets.SECRETS['cloudinary_url'] = 'cloudinary://123456:s3cret@demo-cloud'
t = ok(MD.media_ticket(rid, 'image'))
assert t['provider'] == 'cloudinary' and t['url'] == 'https://api.cloudinary.com/v1_1/demo-cloud/image/upload'
f = t['fields']
assert f['signature'] == hashlib.sha1(('folder=%s&timestamp=%s' % (f['folder'], f['timestamp']) + 's3cret').encode()).hexdigest()
pid = f['folder'] + '/abc123'
good = {'public_id': pid, 'version': 1784556836, 'signature': hashlib.sha1(('public_id=%s&version=1784556836s3cret' % pid).encode()).hexdigest(),
        'secure_url': 'https://res.cloudinary.com/demo-cloud/image/upload/v1784556836/%s.jpg' % pid, 'resource_type': 'image', 'format': 'jpg',
        'width': 1200, 'height': 800, 'bytes': 2048}
cl = ok(MD.register_upload(rid, good, {'in_gallery': True, 'caption': 'Cloud'}))['photo']
assert cl['provider'] == 'cloudinary' and '/upload/c_limit,w_1600,q_auto,f_auto/v1784556836/' in cl['url'] and 'c_fill,w_480' in cl['thumb_url']
assert not MD.register_upload(rid, dict(good, signature='0' * 40))['ok'], 'forged signature'
assert not MD.register_upload(rid, dict(good, public_id='planplate/r999/x'))['ok'], 'another restaurant folder'
assert not MD.register_upload(rid, dict(good, secure_url='https://evil.example/x.jpg'))['ok'], 'not a Cloudinary URL'
del anvil.http.CALLS[:]
ok(MD.delete_photo(rid, cl['id']))
assert anvil.http.CALLS and anvil.http.CALLS[0]['url'].endswith('/demo-cloud/image/destroy') and anvil.http.CALLS[0]['data']['public_id'] == pid
del anvil.secrets.SECRETS['cloudinary_url']
assert MD.media_ticket(rid)['provider'] == 'planplate'

# ---- Today: status, quick hour changes, specials, photo of the day
T_ = ok(BD.get_today(rid))
json.dumps(T_)
assert T_['status']['state'] in ('open', 'later', 'closed') and len(T_['week']) == 7 and len(T_['checklist']) == 5
assert {c['key']: c['done'] for c in T_['checklist']}['website'] is False
today = B.local_now(r).date()
T_ = ok(BD.quick_hours(rid, 'close'))
assert T_['status']['hours'] == [] and B.day_hours(B.Ctx(r), today)[1]['kind'] == 'special'
assert B.start_times(B.Ctx(r), today) == [], 'closed today: nothing to book'
T_ = ok(BD.quick_hours(rid, 'hours', [['10:00', '14:00']]))
assert T_['status']['hours'] == [['10:00', '14:00']]
assert not BD.quick_hours(rid, 'hours', [])['ok']
T_ = ok(BD.quick_hours(rid, 'regular'))
assert T.special_days.get(restaurant=r, date=today) is None
assert not BD.save_dish_special(rid, {'title': ' '})['ok']
T_ = ok(BD.save_dish_special(rid, {'title': 'Truffle risotto', 'price': '€24', 'when': 'today', 'photo': up['key']}))
sp = [x for x in T_['specials'] if x['title'] == 'Truffle risotto'][0]
assert sp['today'] and sp['photo']['key'] == up['key'] and sp['start'] == today.isoformat() == sp['end']
ok(BD.save_dish_special(rid, {'title': 'Friday fish', 'when': 'always', 'days': [4]}))
ok(BD.save_dish_special(rid, {'title': 'Old one', 'when': 'dates', 'start': '2020-01-01', 'end': '2020-01-02'}))
assert not BD.save_dish_special(rid, {'title': 'Bad', 'when': 'dates', 'start': '2037-01-05', 'end': '2037-01-01'})['ok']
fish = T.specials.get(restaurant=r, title='Friday fish')
assert BD.showing_on(fish, next_weekday(4)) and not BD.showing_on(fish, next_weekday(3))
assert 'Old one' not in [x['title'] for x in ok(BD.get_today(rid))['specials']], 'expired specials drop off Today'
ok(BD.toggle_dish_special(rid, sp['id'], False))
assert not BD.showing_on(T.specials.get_by_id(sp['id']), today)
ok(BD.toggle_dish_special(rid, sp['id'], True))
assert not BD.post_photo(rid, {})['ok']
T_ = ok(BD.post_photo(rid, {'photo': p3['key'], 'text': 'Fresh porcini today', 'add_to_gallery': True}))
assert T_['posts'][0]['text'] == 'Fresh porcini today' and T.photos.get(key=p3['key'])['in_gallery'] and T.photos.get(key=p3['key'])['caption'] == 'Fresh porcini today'
assert BD.latest_post(r, today)['text'] == 'Fresh porcini today'
# staff: can see Today and post a photo, can't change hours, specials or the website
cy = T.users.add_row(email='cy@example.com', signed_up=now)
ok(P.invite_member(rid, 'cy@example.com', 'staff'))
anvil.users.CURRENT[0] = cy
ok(BD.get_today(rid))
assert not BD.get_today(rid)['can_manage']
ok(BD.post_photo(rid, {'text': 'Staff lunch was great'}))
for fn, args in ((BD.quick_hours, (rid, 'close')), (BD.save_dish_special, (rid, {'title': 'X'})), (S.get_site, (rid,)), (BD.get_events, (rid,))):
    try:
        fn(*args); raise AssertionError('staff got in: %s' % fn.__name__)
    except anvil.server.PermissionDenied:
        pass
ana_post = [p for p in T.posts.search(restaurant=r) if p['by'] == ana][0]
try:
    BD.delete_post(rid, ana_post.get_id()); raise AssertionError("staff deleted the manager's post")
except anvil.server.PermissionDenied:
    pass
anvil.users.CURRENT[0] = ana

# ---- events: private events close online booking; an event's own room set-up changes the bookable tables
ev_day = next_weekday(4, 9)  # a Friday: regular hours 12-15, 18-23
assert not BD.save_event(rid, {'title': '', 'date': ev_day.isoformat(), 'start': '18:00', 'end': '22:00'})['ok']
assert not BD.save_event(rid, {'title': 'Backwards', 'date': ev_day.isoformat(), 'start': '22:00', 'end': '18:00'})['ok']
E = ok(BD.save_event(rid, {'title': 'Wedding dinner', 'date': ev_day.isoformat(), 'start': '18:00', 'end': '23:00', 'kind': 'private', 'guests': 40, 'host': 'Anna, +371 2000 0000'}))
wed = [e for e in E['upcoming'] if e['title'] == 'Wedding dinner'][0]
assert wed['blocks'] and not wed['on_site'] and not wed['has_setup']
ctx = B.Ctx(r)
times = B.start_times(ctx, ev_day)
assert times and max(times) < 18 * 60 - 120 + 1, 'no online booking that overlaps the private dinner: %s' % [B.hm(x) for x in times]
assert B.hm(min(times)) == '12:00'
E = ok(BD.save_event(rid, {'title': 'Jazz night', 'date': next_weekday(3, 9).isoformat(), 'start': '19:00', 'end': '22:00', 'kind': 'public', 'description': 'Live trio'}))
jazz = [e for e in E['upcoming'] if e['title'] == 'Jazz night'][0]
assert jazz['on_site'] and not jazz['blocks']
assert any(B.hm(x) == '19:00' for x in B.start_times(B.Ctx(r), next_weekday(3, 9))), 'public events keep online booking open'
tids = [t['id'] for t in E['tables']]
assert not BD.save_event_setup(rid, wed['id'], {'groups': [{'tables': tids[:3], 'seats': 12}, {'tables': tids[2:5], 'seats': 10}]})['ok'], 'overlapping groups'
E = ok(BD.save_event_setup(rid, wed['id'], {'layout': {tids[0]: [50, 50], 'bogus': [1, 1]}, 'groups': [{'tables': tids[:4], 'seats': 16, 'label': 'Head table'}],
                                           'removed': [tids[8]]}))
wed = [e for e in E['upcoming'] if e['id'] == wed['id']][0]
assert wed['has_setup'] and list(wed['layout']) == [tids[0]] and wed['removed'] == [tids[8]]
units = B.units_at(B.Ctx(r), ev_day, 19 * 60)
assert any(u['label'] == 'Head table' and u['seats'] == 16 for u in units) and not any(tids[8] in u['ids'] for u in units)
assert not any(u['label'] == 'Head table' for u in B.units_at(B.Ctx(r), ev_day, 13 * 60)), 'the set-up only applies during the event'
day = P.get_day(rid, ev_day.isoformat())
assert day['events'][0]['title'] == 'Wedding dinner' and day['events'][0]['setup']
ok(BD.save_event_setup(rid, wed['id'], {'reset': True}))
assert T.events.get_by_id(wed['id'])['layout'] is None

# ---- website: defaults, cleaning, address, publish, hosted page, live parts, preview, download, example
W = ok(S.get_site(rid))
assert W['site']['path'] == 'le-petit-jardin' and not W['site']['published'] and len(W['palettes']) == 8
c = W['site']['content']
c.update({'cuisine': 'French bistro', 'tagline': 'Small plates <b>& wine</b>', 'logo': 'f' * 32, 'hero': {'kind': 'youtube', 'youtube': 'https://youtu.be/dQw4w9WgXcQ', 'photo': up['key']},
          'social': {'facebook': 'https://facebook.com/jardin', 'instagram': 'javascript:alert(1)'},
          'reviews': [{'name': 'Lea', 'rating': 9, 'text': 'Lovely'}, {'name': '', 'text': ''}],
          'location': {'heading': 'Riverside', 'map': '<iframe src="https://www.google.com/maps/embed?pb=!1m18abc" width="600"></iframe>'}})
W = ok(S.save_site(rid, {'content': c, 'palette': 'bordeaux', 'accent': '#123456', 'restaurant': {'address': '1 Rue du Pont, Riga', 'phone': '+371 2000 1111'}}))
c = W['site']['content']
assert c['logo'] == '' and c['hero']['youtube'] == 'dQw4w9WgXcQ' and c['hero']['photo'] == up['key']
assert c['social']['facebook'] == 'https://facebook.com/jardin' and c['social']['instagram'] == ''
assert c['reviews'] == [{'name': 'Lea', 'source': '', 'rating': 5, 'text': 'Lovely'}] and c['location']['map'] == 'https://www.google.com/maps/embed?pb=!1m18abc'
assert r['address'] == '1 Rue du Pont, Riga' and W['site']['accent'] == '#123456' and W['site']['palette'] == 'bordeaux'
assert not S.save_site(rid, {'path': 'api'})['ok'] and not S.save_site(rid, {'restaurant': {'name': ''}})['ok']
assert not S.save_site(rid, {'restaurant': {'email': 'nope'}})['ok']
other = ok(P.create_restaurant('Other Place', 'UTC', False))['id']
ok(S.get_site(other))
assert not S.save_site(rid, {'path': 'other-place'})['ok'], 'web address taken'
assert anvil.server.ENDPOINTS['/site/:path'](path='le-petit-jardin').status == 404, 'not published yet'
W = ok(S.publish_site(rid, True))
assert W['site']['published'] and W['site']['published_at']
anvil.users.CURRENT[0] = None
page = anvil.server.ENDPOINTS['/site/:path'](path='le-petit-jardin')
html = page.body
assert page.status == 200 and 'text/html' in page.headers['Content-Type']
assert 'Le Petit Jardin' in html and 'French bistro' in html and 'Small plates &lt;b&gt;&amp; wine&lt;/b&gt;' in html, 'text is escaped'
assert '--accent:#123456' in html and '#3f1219' in html, 'bordeaux palette with a custom accent'
assert 'youtube-nocookie.com/embed/dQw4w9WgXcQ' in html and 'google.com/maps/embed?pb=!1m18abc' in html
assert 'Truffle risotto' in html and 'Staff lunch was great' in html, 'specials and the newest photo of the day'
assert '<planplate-gallery feed-url="https://planplate-test.anvil.app/_/api/gallery/le-petit-jardin" theme="cinematic"' in html
assert '"@type": "Restaurant"' in html and 'Jazz night' in html and 'Wedding dinner' not in html, 'private events stay off the website'
assert '#book/le-petit-jardin/' in html and 'javascript:' not in html
assert T.sites.get(restaurant=r)['views'] == 1 and sum(T.sites.get(restaurant=r)['visits'].values()) == 1
live = json.loads(anvil.server.ENDPOINTS['/site/:path'](path='le-petit-jardin', live='1').body)
assert set(live) == {'today', 'specials', 'menu', 'events', 'hours'} and 'Truffle risotto' in live['specials'] and 'data-live="hours"' in live['hours']
assert T.sites.get(restaurant=r)['views'] == 1, 'live refreshes are not visits'
anvil.users.CURRENT[0] = ana
pv = ok(S.preview_site(rid, {'palette': 'noir', 'accent': '', 'content': dict(c, tagline='Preview only'), 'restaurant': {'name': 'Jardin Preview'}}))['html']
assert 'Preview only' in pv and 'Jardin Preview' in pv and '#121110' in pv and 'canonical' not in pv
assert T.sites.get(restaurant=r)['content']['tagline'] != 'Preview only', 'preview never saves'
z = zipfile.ZipFile(io.BytesIO(S.download_site(rid).get_bytes()))
names = z.namelist()
assert 'index.html' in names and 'README.txt' in names and any(n.startswith('images/') for n in names), names
idx = z.read('index.html').decode('utf-8')
assert 'images/' in idx and '?live=1' in idx and 'canonical' not in idx
assert S.download_site(rid).name == 'le-petit-jardin-website.zip'
W = ok(S.load_site_example(other))
oc = W['site']['content']
assert oc['cuisine'] == 'Modern Italian restaurant' and oc['hero']['photo'] and len(oc['reviews']) == 3 and W['site']['palette'] == 'olive'
assert len([p for p in W['photos'] if p['in_gallery']]) == 8 and W['photos'][0]['url'].startswith('https://planplate-test.anvil.app/_/theme/ex-dlt-')
ok(S.load_site_example(other))
assert len(T.photos.search(restaurant=T.restaurants.get_by_id(other))) == 13, 'example photos are added once'
assert T.restaurants.get_by_id(other)['address'] == 'Teātra iela 6, Rīga, Latvia'
assert S.youtube_id('https://www.youtube.com/watch?v=abcdefghijk&t=3') == 'abcdefghijk' and S.youtube_id('hello') == ''
assert S.map_src('https://maps.app.goo.gl/xyz') == '' and S.prose('a **b**\n\nc') == '<p>a <strong>b</strong></p><p>c</p>'
# deleting a photo unlinks it from specials and events; deleting a restaurant removes everything
ok(MD.delete_photo(rid, up['id']))
assert T.specials.get_by_id(sp['id'])['photo'] is None
orow = T.restaurants.get_by_id(other)
ok(P.delete_restaurant(other, 'Other Place'))
assert not T.photos.search(restaurant=orow) and not T.sites.search(restaurant=orow)

ana_pp, bob_pp, rid_pp = ana, bob, rid

def ok(r, msg=""):  # (the booking-rule tests above reuse these names for values)
    assert isinstance(r, dict) and r.get("ok"), (msg, r)
    return r


def bad(r, msg=""):
    assert isinstance(r, dict) and r.get("ok") is False and r.get("error"), (msg, r)
    return r


# ---------------------------------------------------------------------------------- accounts
admin = person("arkulinskis@gmail.com", "The Admin")
ana = person("anna@example.com", "Ana")
bob = person("bobby@example.com")

as_user(None)
assert call("get_me") is None
assert denied("update_profile", "X")
as_user(admin)
assert call("get_me")["is_admin"] is True, "ADMIN_EMAILS become admins on first sign-in"
as_user(ana)
me = call("get_me")
assert me["name"] == "Ana" and me["is_admin"] is False
assert ana["last_seen"] is not None
as_user(bob)
assert call("get_me")["name"] == "Bobby", "a name comes from the email when none is set"
bad(call("update_profile", " x "))
assert ok(call("update_profile", "  Bob   Stone "))["me"]["name"] == "Bob Stone"

# ---------------------------------------------------------------------------------- feedback
as_user(None)
bad(call("submit_feedback", "bug", "hi"))
ok(call("submit_feedback", "bug", "The button is broken", "guest@example.com", {"page": "#dashboard", "evil": "x" * 9999}))
fb = T.feedback.search()[0]
assert fb["name"] == "Guest" and fb["email"] == "guest@example.com" and "evil" not in fb["context"] and fb["status"] == "new"
for i in range(4):
    ok(call("submit_feedback", "idea", "Idea number %d" % i))
bad(call("submit_feedback", "idea", "One too many this hour"), "rate limit")
as_user(ana)
ok(call("submit_feedback", "nonsense-kind", "Signed-in feedback"))
assert T.feedback.get(message="Signed-in feedback")["kind"] == "other"
assert denied("list_feedback")
as_user(admin)
lst = call("list_feedback")
assert lst["counts"]["new"] == 6 and len(lst["items"]) == 6
fid = lst["items"][0]["id"]
ok(call("set_feedback_status", fid, "done", "Fixed it"))
assert call("list_feedback", "done")["items"][0]["note"] == "Fixed it"
bad(call("set_feedback_status", fid, "weird"))
bad(call("set_feedback_status", "nope", "done"))
ok(call("delete_feedback", fid))
assert len(call("list_feedback")["items"]) == 5

# ---------------------------------------------------------------------------------- admin
as_user(ana)
for fn, args in [("admin_overview", ()), ("list_users", ()), ("set_admin", (bob.get_id(), True)), ("demo_load", ()), ("demo_remove", ())]:
    assert denied(fn, *args), fn
as_user(admin)
ov = call("admin_overview")
assert ov["users"] == len(T.users.search()) and ov["admins"] == 1 and ov["feedback_new"] == 5
assert len(call("list_users", "bobby")["users"]) == 1
ok(call("set_admin", bob.get_id(), True))
assert bob["is_admin"] is True
bad(call("set_admin", admin.get_id(), False), "can't remove your own admin")
ok(call("set_enabled", bob.get_id(), False))
assert bob["enabled"] is False
bad(call("set_enabled", admin.get_id(), False))
ok(call("set_enabled", bob.get_id(), True))
ok(call("set_admin", bob.get_id(), False))
assert bob["is_admin"] is False



# ---------------------------------------------------------------------------------- Privacy & Terms
if "legal_server" in MODS:
    as_user(ana)
    st = call("legal_state")
    assert st["signedIn"] and st["accepted_version"] is None
    ok(call("legal_accept", st["version"], "signup"))
    assert ana["legal_source"] == "signup" and call("legal_state")["accepted_version"] == st["version"]

# ---------------------------------------------------------------------------------- schema check (App Board): names only, never data
r = anvil.server.ENDPOINTS["/schema-check"](tables="users, restaurants,no_such_table")
json.dumps(r)
assert "email" in r["tables"]["users"] and "slug" in r["tables"]["restaurants"] and r["tables"]["no_such_table"] is None, r

rid, r = rid_pp, T.restaurants.get_by_id(rid_pp)

# ---------------------------------------------------------------------------------- the Forms rebuild: statuses, guest book, share
as_user(ana_pp)
day = P.get_day(rid, fri.isoformat())
res0 = [x for x in day["reservations"] if x["status"] == "confirmed"][0]
ok(P.set_status(rid, res0["id"], "seated", fri.isoformat()))
assert T.reservations.get_by_id(res0["id"])["status"] == "seated"
r_seated = T.reservations.get_by_id(res0["id"])
ctx = B.Ctx(r)
assert set(r_seated["tables"]) <= B.busy_ids(ctx, fri, int(r_seated["start_min"]), 1), "a seated guest still holds the table"
ok(P.set_status(rid, res0["id"], "done", fri.isoformat()))
assert not (set(r_seated["tables"]) & B.busy_ids(B.Ctx(r), fri, int(r_seated["start_min"]), 1)), "a finished table is free again"
outbox_before = len(anvil.email.OUTBOX)
ok(P.set_status(rid, res0["id"], "no_show", fri.isoformat()))
assert len(anvil.email.OUTBOX) == outbox_before, "no email to the guest for seated / finished / no-show"
assert not P.set_status(rid, res0["id"], "eaten", fri.isoformat())["ok"]
gb = P.get_day(rid, fri.isoformat())
assert all("guest" in x for x in gb["reservations"]), "every booking on the day carries its guest-book badge"
from app import Guests as GU  # noqa: E402
G1 = call("get_guests", rid)
assert G1["total"] >= 1 and G1["can_edit"] and all("visits" in g for g in G1["guests"])
noshow_key = GU.key_of(r_seated["email"], r_seated["phone"], r_seated["name"])
gone = [g for g in G1["guests"] if g["key"] == noshow_key][0]
assert gone["no_shows"] == 1, gone
card = ok(call("get_guest", rid, noshow_key))
assert any(h["status"] == "no_show" for h in card["history"])
ok(call("save_guest", rid, noshow_key, {"note": "Call to confirm", "tags": ["VIP", "Allergy", "Nonsense"]}))
gone = [g for g in call("get_guests", rid, "call to confirm")["guests"]][0]
assert gone["tags"] == ["VIP", "Allergy"] and gone["vip"] and gone["note"] == "Call to confirm"
bad(call("save_guest", rid, "e:nobody@example.com", {"note": "x"}))
assert GU.key_of("A@B.com", "", "") == "e:a@b.com" and GU.key_of("", "+1 (514) 555-0101", "x") == "p:145550101"
sh = call("get_share", rid)
assert sh["settings"]["slug"] and "site_url" in sh and sh["origin"]
as_user(bob_pp)
try:
    call("get_guests", rid)
    leaked = True
except Exception:
    leaked = False
assert not leaked, "someone else's guest book must be private"

# ---------------------------------------------------------------------------------- the demo restaurant (Maison Lumière)
as_user(None)
MODS["common"].set_setting("demo", "never")
form = ok(call("get_booking_form", "maison-lumiere"))
assert form["restaurant"]["name"] == "Maison Lumière", "the demo appears the first time its booking form opens"
demo = T.restaurants.get(slug="maison-lumiere")
assert demo["owner"]["is_demo"] and T.members.search(restaurant=demo, email="arkulinskis@gmail.com"), "admins can manage the demo"
assert len(T.reservations.search(restaurant=demo)) >= 10 and T.guests.search(restaurant=demo)
assert any(x["status"] == "pending" for x in T.reservations.search(restaurant=demo)), "two requests wait for approval"
assert ok(call("get_menu", "maison-lumiere"))["sections"], "its menu"
site = anvil.server.ENDPOINTS["/site/:path"](path="maison-lumiere")
assert site.status == 200 and "Maison Lumi" in site.body, "its PlanPlate website is published"
assert MODS["DemoData"].state() == "loaded"
c = MODS["DemoData"].counts()
assert c["restaurants"] == 1 and c["users"] == 1
real_before = len([x for x in T.restaurants.search() if not (x["owner"] and x["owner"]["is_demo"])])
MODS["DemoData"].remove()
assert T.restaurants.get(slug="maison-lumiere") is None and MODS["DemoData"].state() == "removed"
assert len(T.restaurants.search()) == real_before, "removing the demo keeps real restaurants"
call("get_booking_form", "maison-lumiere")
assert T.restaurants.get(slug="maison-lumiere") is None, "a removed demo doesn't come back by itself"
as_user(admin)
ok(call("demo_load"))
ok(call("demo_load"))
assert len(T.restaurants.search(slug="maison-lumiere")) == 1, "reloading replaces the demo instead of doubling it"

# ---------------------------------------------------------------------------------- the old PlanPlate's public addresses + menu files
import anvil  # noqa: E402
as_user(ana_pp)
OLD_ID = "a022c1f9-7cc3-44ce-9523-0952a8b6f8be"
bad(P.save_settings(rid_pp, {"legacy_id": "not-an-id"}))
ok(P.save_settings(rid_pp, {"legacy_id": OLD_ID.upper()}))
rr = T.restaurants.get_by_id(rid_pp)
assert rr["legacy_id"] == OLD_ID and MODS["Media"].folder(rr) == "restaurants/" + OLD_ID, "uploads share the old Cloudinary folder"
hv = anvil.server.ENDPOINTS["/v1/:ref/:lang"](ref=OLD_ID, lang="lv")
assert hv.status == 200 and "<ul style='list-style-type: none; padding-left: 0;'>" in hv.body and "Pirmdiena" in hv.body, hv.body[:200]
assert anvil.server.ENDPOINTS["/v1/:ref/:lang"](ref="00000000-0000-0000-0000-000000000000", lang="en").status == 404
ml = anvil.server.ENDPOINTS["/menus/:ref/:lang"](ref=OLD_ID, lang="en")
assert ml.status == 200 and "#menu/" in ml.body, "no files yet: the live menu link"
bad(call("add_menu_file", rid_pp, anvil.BlobMedia("text/plain", b"hi", name="x.txt"), "Food", "en"))
bad(call("add_menu_file", rid_pp, anvil.BlobMedia("application/pdf", b"%PDF-1.4", name="food.pdf"), "  ", "en"))
mf = ok(call("add_menu_file", rid_pp, anvil.BlobMedia("application/pdf", b"%PDF-1.4 menu", name="food.pdf"), "Food", "en"))["files"]
ok(call("add_menu_file", rid_pp, anvil.BlobMedia("image/jpeg", bytes([255, 216]) + b"jpeg", name="dzerieni.jpg"), "Dzērieni", "lv"))
ml = anvil.server.ENDPOINTS["/menus/:ref/:lang"](ref=OLD_ID, lang="en").body
assert ">Food</a>" in ml and "Dzērieni" not in ml, "only that language's files"
key = mf[0]["url"].rsplit("/", 1)[1]
f = anvil.server.ENDPOINTS["/menu/:ref/:key"](ref=OLD_ID, key=key)
assert f.status == 200 and f.headers["Content-Type"] == "application/pdf" and "inline" in f.headers["Content-Disposition"]
assert anvil.server.ENDPOINTS["/menu/:ref/:key"](ref="le-petit-jardin-2", key=key).status == 404, "a file only through its own restaurant"
gm = call("get_menu", rr["slug"])
assert [x["title"] for x in gm["files"]] == ["Food", "Dzērieni"] and gm["files"][1]["language"] == "lv"
red = anvil.server.ENDPOINTS["/restaurant/:ref"](ref=OLD_ID)
assert red.status == 302 and red.headers["Location"] == "/#book/" + rr["slug"], "the old booking page opens the new booking form"
assert MODS["Media"].find_restaurant(OLD_ID) == rr, "the gallery feed finds a restaurant by its old id"
E = anvil.server.ENDPOINTS
assert E["/restaurant/:ref/:lang"](ref=OLD_ID, lang="lv").headers["Location"] == "/#book/%s/lv" % rr["slug"], "old pop-up with a language"
assert E["/restaurant/:ref/:lang/:token"](ref=OLD_ID, lang="fr", token="x").headers["Location"] == "/#book/%s/fr" % rr["slug"]
assert E["/reserve/:ref/:lang"](ref=OLD_ID, lang="en").headers["Location"] == "/#book/%s/en" % rr["slug"], "printed booking QR codes"
assert E["/restaurant/:ref/:lang"](ref=OLD_ID, lang="xx").headers["Location"] == "/#book/" + rr["slug"], "unknown language: the default"
qm = E["/menus/:ref/:lang"](ref=OLD_ID, lang=key)
assert qm.status == 200 and qm.headers["Content-Type"] == "application/pdf", "old MENU QR codes (a file id in the language slot) open the file"
qp = E["/menus/:ref/:key/:lang"](ref=OLD_ID, key=key, lang="fr")
assert qp.status == 200 and "Voici le code QR du menu" in qp.body and key in qp.body, "printable menu QR page"
assert E["/menus/:ref/:key/:lang"](ref=OLD_ID, key="0" * 32, lang="en").status == 404
assert E["/reservations/:ref"](ref=OLD_ID).headers["Location"] == "/#reservations/" + rid_pp, "old approval-email link"
assert E["/demo"]().headers["Location"] == "/#book/maison-lumiere"
# a guest note per language
ok(P.save_settings(rid_pp, {"language": "en", "languages": ["en", "fr"], "form_note": "Hello", "form_notes": {"fr": " Bonjour ", "lv": "", "xx": "no"}}))
assert T.restaurants.get_by_id(rid_pp)["form_notes"] == {"fr": "Bonjour"}
assert call("get_booking_form", rr["slug"], "fr")["restaurant"]["form_note"] == "Bonjour"
assert call("get_booking_form", rr["slug"], "en")["restaurant"]["form_note"] == "Hello"
# a special day that is open but takes no online bookings (the old "allow reservations" switch)
sp_day = None
for i in range(3, 40):
    dd = TODAY + dt.timedelta(days=i)
    if any(s["state"] == "open" for s in call("get_slots", rr["slug"], dd.isoformat(), 2)["slots"]):
        sp_day = dd
        break
assert sp_day is not None, "a day with online slots"
ok(call("save_special", rid_pp, {"date": sp_day.isoformat(), "label": "Wedding", "closed": False, "hours": [["12:00", "22:00"]], "no_online": True}))
sl = call("get_slots", rr["slug"], sp_day.isoformat(), 2)["slots"]
assert sl and all(s["state"] == "walk_in" for s in sl), "no online bookings that day: every time is walk-in only"
assert T.special_days.get(restaurant=rr, date=sp_day)["no_online"] is True
ok(call("save_special", rid_pp, {"date": sp_day.isoformat(), "label": "Wedding", "closed": True, "hours": [], "no_online": True}))
assert T.special_days.get(restaurant=rr, date=sp_day)["no_online"] is False, "a closed day has no online switch"
ok(call("delete_menu_file", rid_pp, mf[0]["id"]))
as_user(bob_pp)
try:
    call("add_menu_file", rid_pp, anvil.BlobMedia("application/pdf", b"%PDF", name="x.pdf"), "Hack", "")
    leaked = True
except Exception:
    leaked = False
assert not leaked, "only the restaurant's managers add menu files"

# ---------------------------------------------------------------------------------- every callable is covered by a permission check
# A callable that changes data without require_user / a C.require_* check is a security hole. List the public ones here.
PUBLIC = {"get_me", "submit_feedback", "legal_state", "legal_accept",
          "get_booking_form", "get_slots", "book", "get_reservation", "change_reservation", "cancel_reservation", "get_menu"}
for name, (f, need) in sorted(anvil.server.CALLABLES.items()):
    if name in PUBLIC:
        continue
    assert need, "%s is callable by anyone: add require_user=True (or list it in PUBLIC in test_server.py)" % name

print("ALL OK (%d server functions)" % len(anvil.server.CALLABLES))
