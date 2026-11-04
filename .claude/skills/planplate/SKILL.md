---
name: planplate
description: Context, workflow and recipes for PlanPlate (the restres project, folder restres-forms), the user's Anvil app for restaurant reservations, built as native Anvil Forms since Nov 2026. Managers run bookings, hours, tables, guests, menu, events, gallery and a generated website for all their restaurants; guests book through a form embedded in the restaurant's site. Load this before any feature request, bug fix, restyle or deploy for PlanPlate.
---

# PlanPlate: working on the app (native Anvil Forms)

**What it is:** a reservation portal and one-stop restaurant platform (brand PlanPlate, planplate.com).
- Managers sign in, create restaurants (about 10 each), and for each one set opening hours, tables, booking rules,
  menu, events, specials, gallery and a website. Staff see reservations, Today and the guest book.
- Guests book through `#book/<slug>[/<lang>]` (also inside an iframe or the Reserve button's pop-up from
  `/_/api/embed.js`), manage their booking at `#r/<token>` (no account), and read the menu at `#menu/<slug>` (the QR code).
- Bookings confirm themselves until the restaurant is 80% full (setting); past that, or for a large party, they wait
  as **pending** (header bell, dashboard banner, Reservations).

**Where it lives:**
- Folder `C:\Users\arkvi\Documents\CLAUDE\restres-forms\` = git clone of **github.com/arkulinskis/restres**.
  The user merged the Forms rebuild (branch `forms`) into **`master`** on 2026-11-04; master runs at
  planplate-test.anvil.app. "git" layout: the folder *is* the Anvil app. Pushing master is the deploy.
  The old JS source folder `C:\Users\arkvi\Documents\CLAUDE\restres` is retired: **never run its tools/deploy.py**
  (it would overwrite master with the old version).
- planplate.com still runs the older PlanPlate apps (client.planplate.com, restaurant.planplate.com) until the user migrates.
- Made from `APP_MAKER\template-forms`; Anvil's own skills: `APP_MAKER\vendor\anvil-agent-references\skills\client-forms`.

**What the user wants:** a modern, calm, high-end restaurant look: ivory paper, warm ink, brass accent; Cormorant
Garamond headings, Inter text. Mobile-first (every page fits 390 px), light and dark, and it must also look right on big
monitors (the landing hero fills the screen; `--maxw` and the root font size grow at 1680 px and 2200 px). Claude assumes
details and deploys. Guest texts in English, French and Latvian.

## Workflow for any change

1. `git pull --ff-only` (Anvil commits "Edited ..." from the IDE; read them).
2. Edit a page's template and Python side by side (`client_code/Pages/X/form_template.html` + `__init__.py`).
3. `python tools/check.py` -> **ALL CHECKS PASSED** (anvil validate, JS syntax, asset hashes, server tests).
4. `python -I tools/ui_test.py` (Docker Desktop running) -> **ALL UI TESTS PASSED**. Server edits: `--restart`.
   It includes tools/ui/a11y.js: axe-core (WCAG 2.2 AA) on every page in light + dark, and keyboard checks on the
   booking form and the Privacy page. `--only a11y.js` runs just that.
   `--shots DIR` = every page, desktop + phone, light + dark, guest + member. The local App Server runs with
   `--auto-migrate`, so new tables/columns appear locally by themselves.
   Member pages sign in as arkulinskis@gmail.com **on the local server only** (password in the git-ignored
   `tools/live/.test-account-password.txt`); that address is a manager of the demo restaurant.
5. `python tools/assets.py` after changing theme assets or head_html.
6. Commit as arkulinskis with the Co-Authored-By line; push. New tables/columns: the user accepts the **Schema Mismatch**.

## Architecture

```
client_code/
  startup.py        get_me (skipped on guest pages), legal kit, pp.setup (toasts), router.start()
  router.py         PAGES / NAV / PUBLIC (#book #r #menu: no app chrome) / RESTAURANT (#<page>/<restaurant id>[/more])
  state.py, auth.py the template's helpers (call, toast, store, set_attr, sign in/up/Google)
  pp.py             TABS + roles (can), dates, links (book_url, menu_url, manage_url), QR (qr_svg, qr_png), copy,
                    time_input (browser time picker on a TextBox), html_class, upload() (Cloudinary or PlanPlate)
  i18n.py           every guest text in en/fr/lv: T(key, **vars), set_lang
  site_model.py     the website builder's form data (Model.get/set by dotted path) and its sections
  Layouts/Shell     header (Restaurants, approvals bell polled by a Timer, account menu), footer, guest footer
  Components/       RestaurantNav (the restaurant sub-menu on every restaurant page), AuthBox (sign in/up/reset),
                    SlotPicker (guests/calendar/times for #book and #r), Timeline (pp-timeline.js),
                    FloorPlan (pp-floor.js: Tables and event room set-ups), PhotoField
  Pages/            Landing Auth Dashboard Today Reservations Guests Hours Tables Events Dishes Gallery Website Share
                    Settings Profile Admin + guest pages Book Manage PublicMenu
  Items/            RepeatingPanel rows (Chip is the generic pill: {label, value, on, disabled, group} -> x-chip)
  Dialogs/          BookingEditor DaySheet NewRestaurant PeriodEditor SpecialEditor QuickHours SpecialDish PostPhoto
                    PhotoPicker EventEditor DishEditor SectionEditor GuestCard
theme/assets/       app.css (template tokens set to PlanPlate's look + --pp-* aliases + each page's styles),
                    pp-kit.js (window.PP: dates, time-zone search field, QR, Cloudinary upload, .ics), pp-timeline.js,
                    pp-floor.js, planplate-gallery.js (the <planplate-gallery> web component), photos, icons
server_code/        Booking (rules engine), Portal (manager callables), Public (guest callables, /embed.js),
                    Menu, Board (Today, specials, posts, events), Media (Cloudinary or Anvil media, /photo, /gallery feed),
                    Site (website builder, /_/api/site/<path>), Notify (emails), Guests (guest book), GuestNews
                    (PlanPlate's own booking tick + optional news list, /_/api/news/stop/<token>), DemoData (Maison
                    Lumière), Legacy (old PlanPlate endpoints + menu files), Accounts/Admin/Feedback/common (template),
                    SchemaCheck, seo_routes, legal_server
```

Every restaurant page: `RestaurantNav` at the top (`self.rnav.show(D["nav"])`, `prop:tab="<page>"`), data from one server
call in `__init__`, `_draw()` sets Labels/panels, dialogs return the page's new data. Guest pages call `i18n.set_lang`.

## The rules (Booking.py) and statuses

- Hours: periods with weekly maps; the shorter period wins on overlap; special days override. 00:00 closing = midnight.
- Tables join into one bookable unit for chosen hours/days; events can have their own room set-up.
- Statuses: pending, confirmed, **seated**, **done**, **no_show**, declined, cancelled. `ACTIVE` (hold a table) = pending,
  confirmed, seated. `VISITED` = seated, done (+ confirmed in the past) — the guest book counts these. Seated/done/no-show
  send no guest email.
- Guest book (Guests.py): guests matched by email, else phone digits, else name (`key_of`); stats are computed from
  reservations; the team's notes/tags/VIP live in the `guests` table. `get_day` adds a `guest` badge to every booking.

## Demo restaurant

`DemoData.py` builds **Maison Lumière** (fictional bistro, Old Montréal, demo owner camille.demo@example.com, slug
`maison-lumiere`): hours, a summer period, holidays, 9 tables + a join, a 4-section menu, specials, a note of the day, two
public events, past visits (regulars, a no-show), bookings for the next open days, two pending requests, guest notes,
and a published website (`/_/api/site/maison-lumiere`). It loads by itself the first time the dashboard or its booking
form/menu opens; ADMIN_EMAILS become its managers. Admin -> Demo data reloads or removes it (removing is remembered).

## Replacing the old PlanPlate (client.planplate.com, restaurant.planplate.com)

The old apps live only in Anvil and must not be changed. Read-only copies (Anvil CLI checkout, push disabled) are in
`Documents/CLAUDE/planplate-old/client` (app AYKERJ732EPKSD2F: guest booking + public APIs) and `.../restaurant`
(IBNHSVPERTSB5OFE: back office, Stripe plans, Cloudinary gallery, approval emails). `git pull` there to refresh.
Both used the same tables: restaurants (uid, regular/special hours as lists, table_seats, eating_time in hours,
resto_message_en/fr/lv), reservations (approved/seated/done + status "deleted"), menu_files, new_staff_access (owner/
manager/staff by email), gallery_flags, cloudinary_related, special_actions.

Everything public that old websites and printed QR codes use is answered by `server_code/Legacy.py` once a
restaurant's Settings has its **Old PlanPlate ID** (the old uuid, column `legacy_id`):
- `/restaurant/<id>[/<lang>[/<token>]]` and `/reserve/<id>/<lang>` (PRINTED booking QR codes) -> `#book/<slug>[/<lang>]`.
  On a `restaurant.*` host, `/reserve/...` and `/menus/<id>/<file>/<lang>` are the owners' printable QR pages instead.
- `/reservations/<id>` (old approval emails) -> `#reservations/<rid>`; `/demo` -> the demo booking form.
- `/_/api/v1/<id>/<lang>` hours HTML; `/_/api/menus/<id>/<lang>` menu-file links (with a file id in the `<lang>` slot,
  as the old, broken menu QR codes do, it serves that file); `/_/api/menu/<id>/<file>` the file.
- `/_/theme/planplate_client2.js` + `planplate_client.js`: the old embed scripts rewritten (same names: iframe_launcher,
  restaurant, menus/menu attributes, get_work_hours, get_menu_links, open_reservation_iframe), calling the origin they
  were loaded from. Test page: `maison-lumiere-site/old-code.html`.
- Gallery feed `/_/api/gallery/<id>`; Cloudinary uploads go to `restaurants/<id>/`. Media.cloudinary() reads
  `cloudinary_url` or the old three secrets `cloudinary_cloud` + `cloudinary_api` + `cloudinary_secret`.
Old behaviours ported: special day "open, no online bookings" (`special_days.no_online`), guest note per language
(`restaurants.form_notes`). The demo has the made-up old id 4d2c1f0a-9b7e-4c3d-8a6f-2e5b7c9d1a30.
**Moving the old data (the user chose CSV, Nov 2026):** Admin -> Old PlanPlate (`server_code/OldImport.py`). The
user downloads each old table as CSV from the old app's Data Tables (users, new_staff_access, restaurants, reservations,
menu_files, gallery_flags, cloudinary_related, special_actions); files are recognised by their columns. Passwords are
kept (old password_hash copied into an EMPTY password only). Re-importing updates restaurants by old id and replaces
their hours/special days/tables; bookings (token = old reservation_uid), photos and people are only added. CSVs carry
no media: imported menu files wait for their upload (Menu page -> "Upload the file", keeps the old id so old links work).
Tested on the REAL exports (Nov 3 2026, files `export (3..9).csv` in the user's Downloads; never commit them, they hold
guests' data and password hashes): Anvil writes datetimes as `2026-10-08A21:28:27.161000+0000`, booleans 1/0, `null`,
and puts `'` before text starting with + - = @ (all handled). The admin ticks which restaurants come over (recent
bookings = pre-ticked; only Dilettante - Riga a022c1f9 in the real data); people come only from those teams. ~4,300
bookings is too much for one server call, so `old_import` launches the background task `old_import_task` and the page
polls `old_import_status` (progress in app_settings "old_import"). A re-import also refreshes status/date/time/party of
bookings nobody touched here (history = just the import line), so a final import right before the DNS switch syncs.
The real restaurants export lacked Dilettante Jūrmala `54a6400c…` (308 bookings, 4 menus, 3 staff point to it): the
report names it; the user has to re-download the restaurants table.

**Billing (`server_code/Billing.py`, user's pricing Nov 2026: one flat plan, 100 a month, everything included):** on
only when the app secrets `stripe_secret_key` (or the old `stripe_live_key_secret`) and `stripe_price_id` are set;
otherwise everything is free. Stripe's REST API via anvil.http (no stripe package). Access = admin, demo owner, Admin ->
Users -> "Free plan" (the user's dad's restaurant), or a live subscription (active/trialing/past_due) for the price's
product or an old plan (OLD_PRODUCTS). Without a plan you can't ADD restaurants; existing ones keep running. Dashboard
plan card -> Stripe Checkout (back to `#dashboard/paid`); Profile -> Manage billing (Stripe portal); landing shows the
price from Stripe. Stripe unreachable = nobody locked out. Legal kit: provider `stripe_billing` + "Paid plan" terms.

Demo website using all of it: `Documents/CLAUDE/maison-lumiere-site` (static; `?planplate=http://localhost:3876` for
local testing).

## Accessibility (WCAG 2.2 AA; audit + fixes 2026-11-04)

tools/ui/a11y.js runs axe-core on every page (light +
dark, guest + member) and fails on serious problems; add new pages to its page lists. The rules:
- Text colours reach 4.5:1 on every surface: check new tokens (`--c-faint`, `--c-accent` used as text, status
  colours on their `-soft` fills). Text on good/bad/warn fills is `var(--c-on-status)` (white light, ink dark).
- Every field has a name: wrap it in `<label class="ui-field"><span>Caption</span>...</label>`, or
  `state.set_control_attr(box, "aria-label", "...")` when the caption isn't a label (set it AFTER `.items` on a
  DropDown: Anvil rebuilds the select). Name/email/phone/password get `autocomplete` (set_control_attr).
- The page's title Label is a heading: `state.heading(label, 1)` (one per page; Labels render as divs).
- Toggle buttons say they're on: `.ui-seg` buttons get aria-pressed from the "on" class automatically (app-kit.js);
  elsewhere `state.set_control_attr(btn, "aria-pressed", ...)`. Never `role="tablist"` without real tabs.
- Messages that appear are read out: roles msg-error/msg-note get role alert/status automatically; other changing
  Labels: `state.live(label)`. Hidden text just for screen readers: Label role `sr`.
- When a click redraws a RepeatingPanel, keep the keyboard's place: give the item's button a `data-key` and call
  `state.refocus(panel, key)` after the event (PlanPlate's Items/Chip). Buttons have no `.focus()`: `state.focus(btn)`.
- Images: content images get real alt text (photos: their caption); decorative ones `alt=""`; a Button icon image
  is set to alt="" automatically. Hidden anti-spam fields: `tabindex=-1`, `autocomplete=off`.
- PlanPlate specifics: Items/Chip and Items/PickDay carry `data-key` + aria-pressed and restore focus after the row
  redraws; SlotPicker's hidden `sr_status` says "N free times on <day>" (i18n `timesFree`); the booking form moves
  focus to the first empty field (`fillIn`, aria-invalid), shows "time taken" errors on the pick step (`pick_error`),
  focuses the done title; the guest pages' restaurant name is the h1. Website builder (Site.py): `--accent-text`
  (`_readable`) is the accent darkened/lightened to 4.5:1 for eyebrows, prices and icons; `_ink_for` picks button
  text by real contrast (black when neither ink passes); the menu tabs are toggle buttons (aria-pressed).
- The brass is `#826638` now (was #9c7a43, 3.4:1); `--c-faint` #70695e light / #8f8980 dark; `--c-warn` #8a5e0e.

## Recipes

- **New restaurant page:** Pages/X with RestaurantNav, add to router (PAGES, RESTAURANT, _form), pp.TABS, flow.js + phone.js.
- **New guest text:** i18n.TEXTS en + fr + lv; emails in Notify.TEXT.
- **Times in forms:** a TextBox + `pp.time_input(box)` (Anvil's TextBox has no time type).
- **Photos:** `Components/PhotoField` (set `.rid`) or `pp.upload(rid, accept, multiple, meta, progress)`.
- **Website template:** server_code/Site.py (Render, CSS, LABELS, PALETTES); the builder's fields: site_model.sections.

## Gotchas

- anvil validate narrows dict literals: annotate `x: dict = ...`; DOM properties the stubs miss: `setattr/getattr(node, ...)`.
- CSS image URLs in app.css are relative (`url(photo-plate.webp)`), not `_/theme/...`.
- The template's landing CSS was removed: `.lp-hero` is PlanPlate's full-screen split hero.
- Heredocs with apostrophes fail in the Bash tool: write files with the Write tool.
- Test password and seeded admin exist only in the local Docker volume `restres-data`.
- An Anvil Label is `<div><span>`: page CSS must use child selectors (`.pp-stat > span`), or it restyles Labels too.
- Button icons are `::before` masks (icons.css): rotate the `::before` to flip one (`.anvil-role-pp-up`).

## Privacy & Terms (legal kit)

`APP_MAKER/legal-kit/apps/restres.json`; build + install there, then `python tools/assets.py`. The facts file has its own
`"version"` (2026-11-04, later than the kit's): bump it when PlanPlate's documents change in a way people must re-accept.

**The booking form's three ticks (EU rules, user's decision 2026-11-04):**
1. The restaurant's privacy notice (required; its text is stored with the booking: `consent`, `consent_text`, `consent_at`).
2. **PlanPlate's own agreement** (required, no tick = no booking, checked in the browser AND in `Public.book`): PlanPlate,
   the booking service, keeps a record of the booking and emails the guest about it. Stored as `pp_consent`,
   `pp_consent_text` (the exact words), `pp_consent_at`. Link opens PlanPlate's Privacy Policy (`legal.open("privacy")`).
3. **PlanPlate news** (optional, never pre-ticked): "PlanPlate may also email me now and then with news and offers".
   Marketing consent must be optional under GDPR Art. 7(4) and ePrivacy, so never make it required or pre-tick it.
   Yes = a row in `pp_contacts` (one per lower-cased email: subscribed, consent_text, consent_at, stopped_at, token) +
   `reservations.pp_news`. Guests switch it on/off on `#r/<token>` (`set_guest_news`) or with the stop link
   `/_/api/news/stop/<token>` (GET shows a button, POST stops: mail scanners open links). Guest emails carry the stop link
   while the address is subscribed (`GuestNews.email_line`). Admin -> **News list**: counts + CSV with each person's stop
   link (put it in every news email). Stopped addresses keep their row so they are never emailed again.
All texts live in `server_code/GuestNews.py` (`TEXT`, en/fr/lv) and reach the browser through `get_booking_form` /
`get_reservation` (`pp`), so what's stored is exactly what the guest saw. Staff-made and imported bookings have no PlanPlate
tick (`pp_consent` empty): the guest never saw the form.
