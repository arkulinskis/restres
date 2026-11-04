# Billing — Server Module. One flat plan: a monthly Stripe subscription, everything included (any number of
# restaurants, managers and staff). Ported from the old PlanPlate's plan check (restaurant.planplate.com: it looked up
# the owner's email in Stripe), with the user's new pricing (Nov 2026).
#
# Turned on by two app secrets (Anvil: App Secrets):
#   stripe_secret_key   Stripe's secret API key (the old app's secret "stripe_live_key_secret" works too)
#   stripe_price_id     the monthly price of the PlanPlate product in Stripe (price_...)
# Without them billing is off and everything stays free, as before.
#
# Who has access while billing is on:
#   - an admin, the demo owner, or anyone an admin gave a free plan (Admin -> Users -> Free plan)
#   - anyone whose email has an active or trialing Stripe subscription to that price's product, or to one of the old
#     PlanPlate plans (OLD_PRODUCTS), so existing licences keep working
# Without a plan, people can't ADD restaurants; restaurants they already have keep running (as in the old app).
import time
import urllib.parse
from typing import cast

import anvil.server
import anvil.users
from anvil.tables import app_tables

from . import common as C

OLD_PRODUCTS = ("prod_SXebVc9d5USMxV", "prod_SXCHC26PFU2NvS", "prod_SXCEaspbKWh0SP")  # old Basic, Premium, Recommended (live)
LIVE = ("active", "trialing", "past_due")  # past_due: Stripe is still retrying the card
SYMBOLS = {"usd": "$", "cad": "$", "aud": "$", "eur": "€", "gbp": "£", "chf": "CHF ", "sek": "SEK ", "nok": "NOK "}
CACHE_S = 600


def _secret(name):
    try:
        import anvil.secrets
        return str(anvil.secrets.get_secret(name) or "").strip()
    except Exception:
        return ""


def _key():
    return _secret("stripe_secret_key") or _secret("stripe_live_key_secret")


def _price_id():
    return _secret("stripe_price_id")


def is_on():
    return bool(_key() and _price_id())


def _flat(data, prefix=""):
    """Stripe's form encoding: {"a": [{"b": 1}]} -> a[0][b]=1."""
    out = []
    for k, v in (data or {}).items():
        name = "%s[%s]" % (prefix, k) if prefix else k
        if isinstance(v, dict):
            out += _flat(v, name)
        elif isinstance(v, (list, tuple)):
            for i, x in enumerate(v):
                out += _flat(x, "%s[%d]" % (name, i)) if isinstance(x, dict) else [("%s[%d]" % (name, i), x)]
        elif v is not None:
            out.append((name, "true" if v is True else "false" if v is False else v))
    return out


def api(method, path, data=None):
    """Call Stripe's API (https://api.stripe.com/v1/<path>) with the secret key. Replaced in tests."""
    import anvil.http
    url = "https://api.stripe.com/v1/" + path
    body = urllib.parse.urlencode(_flat(data)) if data else None
    if method == "GET" and body:
        url, body = url + "?" + body, None
    try:
        return anvil.http.request(url, method=method, data=body, json=True,
                                  headers={"Authorization": "Bearer " + _key(), "Content-Type": "application/x-www-form-urlencoded"})
    except anvil.http.HttpError as e:
        print("stripe error", e.status, str(getattr(e, "content", ""))[:300])
        raise RuntimeError("Stripe said no (%s)." % e.status)


# ---------------------------------------------------------------- the price (shown on the landing page and the plan card)
def price():
    """{"amount", "currency", "interval", "product", "text"} of the plan, cached for 6 hours in app_settings."""
    row = app_tables.app_settings.get(key="stripe_price")
    v = dict(row["value"] or {}) if row is not None else {}
    if v.get("id") == _price_id() and time.time() - float(v.get("at") or 0) < 6 * 3600:
        return v
    p = api("GET", "prices/" + urllib.parse.quote(_price_id()))
    amount = (p.get("unit_amount") or 0) / 100.0
    cur = str(p.get("currency") or "usd").lower()
    interval = str((p.get("recurring") or {}).get("interval") or "month")
    num = ("%d" % amount) if amount == int(amount) else ("%.2f" % amount)
    v = {"id": _price_id(), "at": time.time(), "amount": amount, "currency": cur, "interval": interval,
         "product": p.get("product") if isinstance(p.get("product"), str) else (p.get("product") or {}).get("id"),
         "text": "%s%s a %s" % (SYMBOLS.get(cur, cur.upper() + " "), num, interval)}
    if row is None:
        app_tables.app_settings.add_row(key="stripe_price", value=v)
    else:
        row["value"] = v
    return v


def price_text():
    try:
        return price()["text"] if is_on() else ""
    except Exception as e:
        print("price lookup failed:", e)
        return ""


# ---------------------------------------------------------------- who has a plan
def _customers(email):
    return (api("GET", "customers", {"email": email, "limit": 10}) or {}).get("data") or []


def subscription(email):
    """The first live subscription of this email to the plan (or an old plan): {"status", "customer"} or None."""
    products = set(OLD_PRODUCTS)
    try:
        products.add(price()["product"])
    except Exception:
        pass
    for c in _customers(email):
        subs = (api("GET", "subscriptions", {"customer": c["id"], "status": "all", "limit": 20}) or {}).get("data") or []
        for s in subs:
            if s.get("status") not in LIVE:
                continue
            for item in ((s.get("items") or {}).get("data") or []):
                prod = (item.get("price") or {}).get("product")
                if (prod if isinstance(prod, str) else (prod or {}).get("id")) in products:
                    return {"status": s["status"], "customer": c["id"]}
    return None


def plan(u, fresh=False):
    """{"active": bool, "why": "off" | "included" | "free" | "subscription" | "none" | "error", "status"}."""
    if not is_on():
        return {"active": True, "why": "off"}
    if u is None:
        return {"active": False, "why": "none"}
    if u["is_admin"] or u["is_demo"]:
        return {"active": True, "why": "included"}
    if u["plan_free"]:
        return {"active": True, "why": "free"}
    session = cast(dict, anvil.server.session)
    cache = session.get("pp_plan")
    if not fresh and cache and cache.get("email") == u["email"] and time.time() - cache["at"] < CACHE_S:
        return cache["plan"]
    try:
        s = subscription(u["email"])
        out = {"active": True, "why": "subscription", "status": s["status"]} if s else {"active": False, "why": "none"}
    except Exception as e:
        print("plan check failed:", e)
        return {"active": True, "why": "error"}  # Stripe unreachable: don't lock anyone out
    session["pp_plan"] = {"email": u["email"], "at": time.time(), "plan": out}
    return out


def blocked(u):
    """The message for someone who can't add a restaurant without a plan, or None."""
    if plan(u)["active"]:
        return None
    return ("PlanPlate is %s, with everything included: any number of restaurants, your whole team and every feature. "
            "Start your subscription to add a restaurant." % (price_text() or "a flat monthly price"))


# ---------------------------------------------------------------- callables
@anvil.server.callable(require_user=True)
def get_plan(fresh=False):
    u = anvil.users.get_user()
    p = plan(u, fresh=bool(fresh))
    return {"on": is_on(), "active": p["active"], "why": p["why"], "status": p.get("status", ""), "price": price_text()}


@anvil.server.callable
def get_pricing():
    """For the landing page: the plan's price, or on=False while billing is off."""
    return {"on": is_on(), "price": price_text()}


@anvil.server.callable(require_user=True)
def start_checkout():
    """A Stripe Checkout page for the monthly plan. Returns its address; the browser goes there."""
    u = anvil.users.get_user()
    if u is None:
        return C.fail("Sign in first.")
    if not is_on():
        return C.fail("Billing isn't set up yet.")
    if plan(u, fresh=True)["active"]:
        return C.fail("You already have a plan.")
    origin = anvil.server.get_app_origin()
    data: dict = {"mode": "subscription", "line_items": [{"price": _price_id(), "quantity": 1}],
                  "success_url": origin + "/#dashboard/paid", "cancel_url": origin + "/#dashboard",
                  "client_reference_id": u.get_id(), "allow_promotion_codes": True}
    try:
        found = _customers(u["email"])
        if found:
            data["customer"] = found[0]["id"]
        else:
            data["customer_email"] = u["email"]
        s = api("POST", "checkout/sessions", data)
    except Exception as e:
        return C.fail("Stripe couldn't start the payment page. Try again in a minute. (%s)" % e)
    cast(dict, anvil.server.session).pop("pp_plan", None)
    return C.ok(url=s.get("url"))


@anvil.server.callable(require_user=True)
def billing_portal():
    """Stripe's billing page for this person (card, invoices, cancel)."""
    u = anvil.users.get_user()
    if u is None:
        return C.fail("Sign in first.")
    if not is_on():
        return C.fail("Billing isn't set up yet.")
    try:
        found = _customers(u["email"])
        if not found:
            return C.fail("There's no subscription under %s yet." % u["email"])
        s = api("POST", "billing_portal/sessions", {"customer": found[0]["id"], "return_url": anvil.server.get_app_origin() + "/#profile"})
    except Exception as e:
        return C.fail("Stripe couldn't open your billing page. Try again in a minute. (%s)" % e)
    return C.ok(url=s.get("url"))
