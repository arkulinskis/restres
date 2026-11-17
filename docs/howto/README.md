# PlanPlate how-to guide

A guide for restaurant managers and staff, with screenshots taken in the real app. Built so that one part can be
updated without going through the whole app: every section has its own text file, its own screenshots and a list of
the app files it describes.

| What | Where |
|---|---|
| Sections, their order, who each is for, their screenshots and the app files they describe | `guide.json` |
| The words, one file per section (small Markdown subset, see `tools/howto/build.py`) | `sections/<id>.md` |
| The screenshots, and when / at which commit each was taken | `shots/<name>.webp`, `shots/manifest.json` |
| The built guide (self-contained, ~1.3 MB, also published as a claude.ai artifact) | `PlanPlate-how-to.html` |
| The app's own How to page (`#howto`, header tab + a How to link on every restaurant page) | `client_code/Pages/HowTo` reads the GENERATED `client_code/howto_content.py`; pictures `theme/assets/howto-*.webp` |
| The tool | `tools/howto/howto.py` (+ `helpers.js` for the screenshot steps, `build.py` for both pages) |

Published copy (private claude.ai artifact; republish to the same URL with `url`): https://claude.ai/artifact/UpMCg7fHJnDq8WufZSgNHX

## Update after an app change (the cheap way)

1. `python -I tools/howto/howto.py stale` lists the sections whose app files changed since their screenshots.
   (Or you already know: "the Settings page changed" means section `settings`, and maybe `team`.)
2. `python -I tools/howto/howto.py shoot <section>` retakes only that section's screenshots (Docker Desktop must be
   running; the local App Server starts by itself; add `--restart` after server-code changes).
3. Look at the new shots, then edit only `sections/<section>.md`. Read only the app files listed in that section's
   `sources` if you need to check a fact.
4. `python -I tools/howto/howto.py check` then `python -I tools/howto/howto.py build`. This rebuilds BOTH the standalone
   page and the app's How to page (never edit `client_code/howto_content.py` by hand).
5. Commit and push (that deploys the app's page), and republish the artifact from `docs/howto/PlanPlate-how-to.html`
   to the same URL.

A new restaurant tab needs its section in `HELP` in `client_code/Components/RestaurantNav/__init__.py` (tab -> section id).

## Add a section or a screenshot

- New section: add an entry to `guide.json` (`id`, `title`, `who`, `sources`, `shots`) where it belongs in the order,
  and write `sections/<id>.md`.
- New screenshot: add it to the section's `shots` and put `![caption](shot:<name>)` in the text. Shot fields:
  `as` = `guest` | `manager` | `staff` (staff = waiter@example.com, invited by the manager on the local database);
  `go` = address (`{rid}` = the demo restaurant); `do` = JS run once the page is ready (async; `H.click('Label')`,
  `H.view('List')`, `H.opened(/Title/)`, `H.scrollTo('.css')`, `H.type(input, text)` ... see `tools/howto/helpers.js`);
  `selector` crops to one element; `full` = whole page; `window: "phone"` = 390x844; `wait` = extra ms.
- Several pictures on one line in the text sit side by side (used for the phone shots).

## Notes

- Shots are taken against the local Anvil App Server with the demo restaurant Maison Lumière. A full `shoot` (no
  section names) reloads the demo first, so dates and requests are fresh; single-section shoots don't (`--reload` forces it).
- The local test address is replaced by `live_origin` from `guide.json` in every screenshot.
- The light theme is used for screenshots (printed guides). The guide page itself follows the reader's theme.
