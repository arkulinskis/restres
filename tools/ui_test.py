"""Run the app for real in the open-source Anvil App Server (Docker) and drive it with headless Chrome.

    python -I tools/ui_test.py                 the user journey (tools/ui/flow.js), the phone-width check (phone.js), admin (admin.js)
    python -I tools/ui_test.py --shots DIR     also screenshots of every page (desktop + phone, light + dark) into DIR
    python -I tools/ui_test.py --stop          stop the local server afterwards

The server runs this folder as it is (no build step): container "<key>-dev" on http://localhost:<PORT>, data in the
Docker volume "<key>-data" (accounts made by tests stay there; `docker volume rm <key>-data` to start clean).
Edits to client code show up on the next page load; server-code edits need the container restarted (--restart).
Needs Docker Desktop running and Chrome installed.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
KEY = "restres"
NAME, IMAGE = KEY + "-dev", "anvilworks/anvil-app-server:1.18.0"
PORT = 3100 + sum(map(ord, KEY)) % 800  # one port per app, so several apps can run side by side
URL = "http://localhost:%d" % PORT


def sh(*args, check=True):
    return subprocess.run(list(args), capture_output=True, text=True, encoding="utf-8", errors="replace", check=check)


def running():
    r = sh("docker", "ps", "--filter", "name=^/%s$" % NAME, "--format", "{{.Status}}", check=False)
    return r.stdout.strip().startswith("Up")


def start(restart=False):
    if restart:
        sh("docker", "rm", "-f", NAME, check=False)
    if not running():
        sh("docker", "rm", "-f", NAME, check=False)
        sh("docker", "run", "-d", "--name", NAME, "-p", "%d:%d" % (PORT, PORT), "-v", "%s:/apps/MainApp" % ROOT.as_posix(),
           "-v", KEY + "-data:/anvil-data", IMAGE, "--app", "MainApp", "--origin", URL,
           "--auto-migrate")  # new tables/columns apply locally; columns a service adds by itself (e.g. Users) must not stop local tests
        print("starting the App Server ...")
    for _ in range(300):
        logs = sh("docker", "logs", NAME, check=False)
        if "Downlink client connected" in logs.stdout + logs.stderr:
            try:
                urllib.request.urlopen(URL, timeout=5).read(100)
                return
            except Exception:
                pass
        time.sleep(2)
    sys.exit("The App Server didn't start. `docker logs %s` says why." % NAME)


def drive(script, window, out, shots=(), seed=False):
    """Run a page script and/or take screenshots. shots = [(name, hash or JS expression, js to run first)]."""
    steps = [{"waitFor": "window.UI_READY === true", "timeout": 90000}]
    if script:
        code = (ROOT / "tools" / "ui" / script).read_text(encoding="utf-8")
        seed_js = (ROOT / "tools" / "ui" / "seed.js").read_text(encoding="utf-8").strip().rstrip(";")
        code = code.replace("(async () => { /*SEED*/ })()", seed_js)  # flow/phone sign in the same way seed.js does
        steps.append({"eval": code})
    if seed:
        steps.append({"eval": (ROOT / "tools" / "ui" / "seed.js").read_text(encoding="utf-8")})
    for name, where, js in shots:
        target = where if not where.startswith("#") else json.dumps(where)
        steps += [{"eval": "%s; window.__to = %s; if (location.hash !== window.__to) window.UI_READY = false; location.hash = window.__to; 1"
                           % (js or "0", target)},
                  {"waitFor": "window.UI_READY === true && location.hash === window.__to", "timeout": 30000},
                  {"wait": 1200}, {"shot": name, "full": True}]
    f = pathlib.Path(out) / ("steps-%s.json" % (script or "shots").replace(".js", ""))
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(steps), encoding="utf-8")
    env = dict(__import__("os").environ, WINDOW="1280,1000")
    if window != "1280,1000":
        env["MOBILE"] = window
    r = subprocess.run(["node", str(ROOT / "tools" / "live" / "drive.mjs"), URL + "/#landing", str(f), str(out)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=900)
    return r.stdout + r.stderr


def result(text):
    """The {ok, log} the page script returned (drive.mjs prints it after [eval])."""
    for line in text.splitlines():
        if line.startswith("[eval] {"):
            return json.loads(line[len("[eval] "):])
    return None


def main():
    args = sys.argv[1:]
    if "--stop" in args and len(args) == 1:
        sh("docker", "rm", "-f", NAME, check=False)
        return
    start(restart="--restart" in args)
    out = pathlib.Path(tempfile.mkdtemp(prefix=KEY + "-ui-"))
    failed = False
    for script, window in (("flow.js", "1280,1000"), ("phone.js", "390,844"), ("admin.js", "1280,1000")):
        text = drive(script, window, out / script.replace(".js", ""))
        res = result(text)
        errors = [l for l in text.splitlines() if "[EXCEPTION]" in l or "Python exception" in l or "Error report" in l]
        print("==== %s (%s)" % (script, window))
        for line in (res or {}).get("log", []) or text.splitlines()[-25:]:
            print("  " + line)
        for e in errors:
            print("  " + e)
        if not res or not res.get("ok") or errors:
            failed = True
    if "--shots" in args:
        dest = pathlib.Path(args[args.index("--shots") + 1])
        guest = [("landing", "#landing"), ("auth", "#auth/signup"), ("book", "#book/maison-lumiere"), ("menu", "#menu/maison-lumiere")]
        member = [("dashboard", "#dashboard")] + [(p, "'#%s/' + encodeURIComponent(window.SEED.rid)" % p) for p in
                                                  ("today", "reservations", "guests", "hours", "tables", "events", "dishes", "gallery",
                                                   "website", "share", "settings")]
        for window, tag in (("1280,1000", ""), ("390,844", "_phone")):
            for theme in ("light", "dark"):
                js = "UI.setTheme(%s)" % json.dumps(theme)
                drive(None, window, dest / (theme + tag), [(n + tag + "_" + theme, h, js) for n, h in guest])
                log = drive(None, window, dest / (theme + tag + "_in"), [(n + tag + "_" + theme, h, js) for n, h in member], seed=True)
                problems = [l for l in log.splitlines() if "TIMEOUT" in l or "EXCEPTION" in l or "error" in l.lower()]
                for p_ in problems[:5]:
                    print("  shots: " + p_[:300])
        print("screenshots in", dest)
    if "--stop" in args:
        sh("docker", "rm", "-f", NAME, check=False)
    print("ALL UI TESTS PASSED" if not failed else "UI TESTS FAILED")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
