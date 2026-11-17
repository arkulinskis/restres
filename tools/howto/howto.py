"""PlanPlate's how-to guide: screenshots taken in the real app, text kept per section, one HTML file built from both.

    python -I tools/howto/howto.py list                  sections, their shots and the app files they describe
    python -I tools/howto/howto.py stale                 sections whose app files changed after their screenshots
    python -I tools/howto/howto.py shoot                 every screenshot (reloads the demo restaurant first)
    python -I tools/howto/howto.py shoot team today      only these sections' screenshots (or shot names)
    python -I tools/howto/howto.py build                 docs/howto/PlanPlate-how-to.html (self-contained)
    python -I tools/howto/howto.py check                 every picture in the text exists, every shot is used

Everything lives in docs/howto/: guide.json (sections, order, shots, sources), sections/<id>.md (the words),
shots/<name>.webp (the pictures) and shots/manifest.json (when and at which commit each shot was taken).
Updating one part of the app = `stale`, then `shoot <section>`, edit sections/<section>.md, `build`. See docs/howto/README.md.
Shots run against the local Anvil App Server (tools/ui_test.py starts it; Docker Desktop must be running).
"""
import base64
import datetime as dt
import html
import io
import json
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "howto"
SHOTS = DOCS / "shots"
MANIFEST = SHOTS / "manifest.json"
GUIDE = DOCS / "guide.json"
OUT = DOCS / "PlanPlate-how-to.html"
HERE = pathlib.Path(__file__).resolve().parent

ROLES = {  # who each shot is taken as: the JS that signs in (local test database only) and sets window.SEED.rid
    "guest": "",
    "manager": """await H.signIn('admin@example.com', 'Alex Morgan');
        if (__RELOAD__ || !H.demoId()) await H.reloadDemo();  // also when the local database has no demo yet
        window.SEED = {rid: H.demoId()};""",
    "staff": """await H.signIn('admin@example.com', 'Alex Morgan');
        if (!H.demoId()) await H.reloadDemo();
        const rid = encodeURIComponent(H.demoId());
        await H.go('#settings/' + rid, () => H.$('#st-team'));
        if (!/waiter@example\\.com/.test(H.$('#st-team').textContent)) {
          H.type(H.$$('#st-team input').find(H.vis), 'waiter@example.com');
          const sel = H.$$('#st-team select').find(H.vis); sel.selectedIndex = 0; sel.dispatchEvent(new Event('change', {bubbles: true}));
          await H.click('Invite', '#st-team');
          await H.until(() => /waiter@example\\.com/.test(H.$('#st-team').textContent), 'the waiter invited');
        }
        await H.signOut();
        await H.signIn('waiter@example.com', 'Sam Rivera');
        window.SEED = {rid: H.demoId()};""",
}


def guide():
    return json.loads(GUIDE.read_text(encoding="utf-8"))


def manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}


def git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    return r.stdout.strip()


# ---------------------------------------------------------------- list / stale / check
def cmd_list(_):
    for s in guide()["sections"]:
        print("%-16s %-44s %s" % (s["id"], s["title"], s["who"]))
        print("    shots:   " + ", ".join(x["name"] for x in s["shots"]))
        print("    sources: " + ", ".join(s["sources"]))


def cmd_stale(_):
    """A section is stale when a commit touched one of its sources after its oldest screenshot was taken."""
    m, stale = manifest(), 0
    for s in guide()["sections"]:
        taken = [m.get(x["name"], {}).get("taken") for x in s["shots"]]
        if not all(taken):
            print("%-16s never shot (or a shot is missing): shoot %s" % (s["id"], s["id"]))
            stale += 1
            continue
        since = min(taken)
        changed = git("log", "--since=" + since, "--format=%h %s", "--", *s["sources"])
        if changed:
            stale += 1
            print("%-16s app changed since %s:" % (s["id"], since[:16]))
            for line in changed.splitlines()[:6]:
                print("      " + line)
    print("%d stale section(s)" % stale if stale else "every section is up to date")


def cmd_check(_):
    g, bad = guide(), 0
    for s in g["sections"]:
        md = DOCS / "sections" / (s["id"] + ".md")
        if not md.exists():
            print("missing text: %s" % md.relative_to(ROOT)); bad += 1; continue
        used = set(re.findall(r"\(shot:([\w-]+)\)", md.read_text(encoding="utf-8")))
        names = {x["name"] for x in s["shots"]}
        for n in sorted(used - names):
            print("%s: uses shot:%s, which isn't one of this section's shots" % (s["id"], n)); bad += 1
        for n in sorted(names - used):
            print("%s: shot %s is never shown" % (s["id"], n)); bad += 1
        for n in sorted(names):
            if not (SHOTS / (n + ".webp")).exists():
                print("%s: shots/%s.webp is missing (shoot %s)" % (s["id"], n, s["id"])); bad += 1
    print("GUIDE OK" if not bad else "%d problem(s)" % bad)
    return bad


# ---------------------------------------------------------------- shoot
def shot_steps(shot, prefix, origin=""):
    go = json.dumps(shot["go"])
    do = shot.get("do", "") + "\n        H.live(%s);" % json.dumps(origin)
    js = """(async () => { try {
        await H.closeDialogs();
        const to = %s.replace('{rid}', encodeURIComponent((window.SEED || {}).rid || ''));
        await H.go(to); %s
        await H.sleep(%d);
        return 'ok %s';
      } catch (e) { return 'ERROR %s: ' + (e && e.message || e); } })()""" % (go, do, 900 + int(shot.get("wait", 0)), shot["name"], shot["name"])
    step = {"shot": prefix + shot["name"]}
    if shot.get("selector"):
        step.update(selector=shot["selector"], pad=shot.get("pad", 12))
    elif shot.get("full"):
        step["full"] = True
    return [{"eval": js}, step]


def run_group(role, window, shots, reload_demo, out):
    import ui_test  # tools/ui_test.py: the URL of the local App Server
    helpers = (HERE / "helpers.js").read_text(encoding="utf-8")
    setup = ROLES[role].replace("__RELOAD__", "true" if reload_demo else "false")
    steps = [{"waitFor": "window.UI_READY === true", "timeout": 90000}, {"eval": helpers}]
    if setup:
        steps.append({"eval": "(async () => { try { %s; return 'signed in as %s, restaurant ' + window.SEED.rid; } "
                              "catch (e) { return 'ERROR setup %s: ' + (e && e.message || e); } })()" % (setup, role, role)})
    for s in shots:
        steps += shot_steps(s, "", guide().get("live_origin", ""))
    out.mkdir(parents=True, exist_ok=True)
    f = out / "steps.json"
    f.write_text(json.dumps(steps), encoding="utf-8")
    env = dict(__import__("os").environ, WINDOW="1280,900")
    if window == "phone":
        env["MOBILE"] = "390,844"
    r = subprocess.run(["node", str(ROOT / "tools" / "live" / "drive.mjs"), ui_test.URL + "/#landing", str(f), str(out)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=1200)
    return r.stdout + r.stderr


def to_webp(png, dest):
    import site
    sys.path.append(site.getusersitepackages())  # Pillow is a user install; `python -I` leaves that folder out
    from PIL import Image
    im = Image.open(png).convert("RGB")
    if im.width > 1600:
        im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
    im.save(dest, "WEBP", quality=82, method=6)


def cmd_shoot(args):
    sys.path.insert(0, str(ROOT / "tools"))
    import ui_test
    wanted = [a for a in args if not a.startswith("--")]
    g = guide()
    picked = []
    for s in g["sections"]:
        for x in s["shots"]:
            if not wanted or s["id"] in wanted or x["name"] in wanted:
                picked.append(dict(x, section=s["id"]))
    unknown = set(wanted) - {s["id"] for s in g["sections"]} - {x["name"] for s in g["sections"] for x in s["shots"]}
    if unknown:
        sys.exit("unknown section or shot: " + ", ".join(sorted(unknown)))
    ui_test.start(restart="--restart" in args)
    # a full run reloads the demo restaurant first (fresh bookings for today, two requests waiting); --no-reload skips it
    reload_demo = not wanted and "--no-reload" not in args or "--reload" in args
    groups = {}
    for x in picked:
        groups.setdefault((x.get("as", "manager"), x.get("window", "desktop")), []).append(x)
    order = sorted(groups, key=lambda k: ({"manager": 0, "staff": 1, "guest": 2}[k[0]], k[1]))
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="planplate-howto-"))
    m, sha, failed = manifest(), git("rev-parse", "--short", "HEAD"), []
    SHOTS.mkdir(parents=True, exist_ok=True)
    for role, window in order:
        out = tmp / ("%s-%s" % (role, window))
        log = run_group(role, window, groups[(role, window)], reload_demo and role == "manager", out)
        reload_demo = reload_demo and role != "manager"
        errors = [l for l in log.splitlines() if "ERROR" in l or "TIMEOUT" in l or "driver error" in l or "EXCEPTION" in l]
        print("==== %s (%s): %d shot(s)" % (role, window, len(groups[(role, window)])))
        for e in errors:
            print("  " + e[:400])
        for x in groups[(role, window)]:
            png = out / (x["name"] + ".png")
            if png.exists() and not any(("ERROR %s:" % x["name"]) in e for e in errors):
                to_webp(png, SHOTS / (x["name"] + ".webp"))
                m[x["name"]] = {"section": x["section"], "taken": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "commit": sha}
                print("  ok   " + x["name"])
            else:
                failed.append(x["name"])
                print("  FAIL " + x["name"] + " (log: %s)" % (out / "log.txt"))
    MANIFEST.write_text(json.dumps(dict(sorted(m.items())), indent=1), encoding="utf-8")
    print("screenshots in", SHOTS.relative_to(ROOT), "· raw run in", tmp)
    if failed:
        sys.exit("FAILED: " + ", ".join(failed))


# ---------------------------------------------------------------- build
def cmd_build(_):
    from build import build_html  # tools/howto/build.py
    page = build_html(guide(), DOCS, SHOTS)
    OUT.write_text(page, encoding="utf-8")
    print("built %s (%d KB)" % (OUT.relative_to(ROOT), len(page.encode("utf-8")) // 1024))


def main():
    sys.path.insert(0, str(HERE))
    cmds = {"list": cmd_list, "stale": cmd_stale, "check": cmd_check, "shoot": cmd_shoot, "build": cmd_build}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        sys.exit(__doc__)
    sys.exit(cmds[sys.argv[1]](sys.argv[2:]) and 1 or 0)


if __name__ == "__main__":
    main()
