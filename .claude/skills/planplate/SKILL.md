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
  The Forms rebuild is on branch **`forms`** until the user approves it; `master` (still the old JS version, built from
  `C:\Users\arkvi\Documents\CLAUDE\restres` with tools/deploy.py) runs at planplate-test.anvil.app.
  "git" layout: the folder *is* the Anvil app. Pushing is the deploy (once merged to master).
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
                    Site (website builder, /_/api/site/<path>), Notify (emails), Guests (guest book), DemoData (Maison
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

The old apps live only in Anvil (not on GitHub) and must not be changed. Their public interface, which restaurant
websites (e.g. dilettante.lv) still call, is answered by `server_code/Legacy.py` once a restaurant's Settings ->
"Coming from the old PlanPlate" has its **Old PlanPlate ID** (the UUID in the old embed code, column `legacy_id`):
- `/restaurant/<id>` (the old booking iframe) -> 302 to `/#book/<slug>`; the Book page's "Close" posts `close_div`
  to the parent, as the old pop-up expected.
- `/_/api/v1/<id>/<lang>`: opening hours as the old `<ul>` HTML (week + special days).
- `/_/api/menus/<id>/<lang>` (links to menu files) and `/_/api/menu/<id>/<file key>` (serves the image/PDF inline).
  Menu files: table `menu_files`, managed on the Menu page (Dishes) -> "Menu files"; shown on #menu too.
- Gallery: `/_/api/gallery/<id or slug>` (Media.py) lists the photos; with `legacy_id` set, Cloudinary uploads go to the
  old folder `restaurants/<id>/` of the old cloud (`dzqa1mwom`) once the app secret `cloudinary_url` points at it.
To switch a domain over, point client.planplate.com / restaurant.planplate.com at this app (Anvil custom domain) only
after every restaurant has its Old PlanPlate ID filled in.

Demo website using all of it: `Documents/CLAUDE/maison-lumiere-site` (static; `?planplate=http://localhost:3876` for
local testing).

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

`APP_MAKER/legal-kit/apps/restres.json`; build + install there, then `python tools/assets.py`. The guest booking form keeps
its own consent tick (the restaurant's privacy text, stored with each booking).
