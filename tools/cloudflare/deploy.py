"""Put PlanPlate's photo storage on Cloudflare: R2 bucket "planplate-media" + the planplate-media Worker.

    python -I tools/cloudflare/deploy.py            create the bucket if needed, set the signing key, deploy, test
    python -I tools/cloudflare/deploy.py --test     only test the live Worker (signed upload, read, range, delete)

Before the first run: `npx wrangler login` done once on this PC (same Cloudflare account as the music Worker).

The signing key is made once and kept OUTSIDE the repo in ~/.planplate/cloudflare_media.txt, as the exact value of the
Anvil app secret "cloudflare_media" (https://<key>@planplate-media.<subdomain>.workers.dev). Paste that value into the
Anvil editor: App Secrets -> cloudflare_media. Never commit it.
"""
import hashlib
import hmac
import json
import pathlib
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
SECRET_FILE = pathlib.Path.home() / ".planplate" / "cloudflare_media.txt"
BUCKET = "planplate-media"
WRANGLER = "wrangler@4"


def npx():
    exe = shutil.which("npx.cmd") or shutil.which("npx")
    if not exe:
        sys.exit("npx not found: install Node.js first.")
    return exe


def wrangler(*args, stdin=None, check=True):
    r = subprocess.run([npx(), "--yes", WRANGLER, *args], cwd=HERE, input=stdin, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    if check and r.returncode:
        sys.exit("wrangler %s failed:\n%s" % (" ".join(args), out))
    return out


def parse(value):
    m = re.match(r"^(https://)([0-9a-f]{32,128})@([\w.-]+)/?$", value.strip())
    return (m.group(1) + m.group(3), m.group(2)) if m else (None, None)


def sign(key, method, obj, exp, extra):
    return hmac.new(key.encode(), "\n".join([method, obj, str(exp), extra]).encode(), hashlib.sha256).hexdigest()


def http(method, url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, method=method, headers=dict({"User-Agent": "planplate-deploy"}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def test(base, key):
    obj = "test/deploy-" + secrets.token_hex(6)
    exp = int(time.time()) + 600
    body = bytes(range(256)) * 4
    q = urllib.parse.urlencode({"exp": exp, "max": 5000, "kind": "image", "sig": sign(key, "PUT", obj, exp, "5000\nimage")})
    st, out, _ = http("PUT", "%s/%s?%s" % (base, obj, q), body, {"Content-Type": "image/png"})
    assert st == 200, ("signed upload", st, out[:200])
    st, out, _ = http("PUT", "%s/%s?%s" % (base, obj + "-x", q), body, {"Content-Type": "image/png"})
    assert st == 403, ("an upload link only works for its own file", st)
    q2 = urllib.parse.urlencode({"exp": exp, "max": 100, "kind": "image", "sig": sign(key, "PUT", obj + "-big", exp, "100\nimage")})
    st, _, _ = http("PUT", "%s/%s?%s" % (base, obj + "-big", q2), body, {"Content-Type": "image/png"})
    assert st == 413, ("size limit", st)
    st, out, h = http("GET", "%s/%s" % (base, obj))
    assert st == 200 and out == body and h.get("Content-Type") == "image/png", ("read back", st, h)
    st, out, h = http("GET", "%s/%s" % (base, obj), headers={"Range": "bytes=10-19"})
    assert st == 206 and out == body[10:20], ("byte range", st)
    st, out, _ = http("GET", "%s/%s?meta=1" % (base, obj))
    assert st == 200 and json.loads(out) == {"ok": True, "size": len(body), "type": "image/png"}, ("file info", st, out)
    q3 = urllib.parse.urlencode({"exp": exp, "sig": sign(key, "DELETE", obj, exp, "")})
    st, _, _ = http("DELETE", "%s/%s?%s" % (base, obj, q3))
    assert st == 200, ("delete", st)
    st, _, _ = http("GET", "%s/%s" % (base, obj))
    assert st == 404, ("deleted file is gone", st)
    print("Live test OK: signed upload, wrong-file and size refusals, read, byte range, delete (%s)" % base)


def main():
    args = sys.argv[1:]
    value = SECRET_FILE.read_text(encoding="utf-8").strip() if SECRET_FILE.exists() else ""
    if "--test" in args:
        base, key = parse(value)
        if not base:
            sys.exit("No signing key yet: run without --test first.")
        return test(base, key)

    out = wrangler("whoami", check=False)
    if "not authenticated" in out.lower():
        sys.exit("Not logged in to Cloudflare. Run once: npx wrangler login")
    if BUCKET not in wrangler("r2", "bucket", "list"):
        wrangler("r2", "bucket", "create", BUCKET)
        print("Created R2 bucket", BUCKET)
    base, key = parse(value)
    key = key or secrets.token_hex(32)
    out = wrangler("deploy")
    m = re.search(r"https://planplate-media\.[\w-]+\.workers\.dev", out)
    if not m:
        sys.exit("Deployed, but couldn't find the Worker's address in wrangler's output:\n" + out)
    base = m.group(0)
    wrangler("secret", "put", "SIGNING_KEY", stdin=key + "\n")
    value = "https://%s@%s" % (key, base[len("https://"):])
    SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    SECRET_FILE.write_text(value + "\n", encoding="utf-8")
    print("Worker live at", base)
    print("Anvil app secret 'cloudflare_media' value saved in", SECRET_FILE)
    time.sleep(5)  # the new secret takes a moment to reach every Cloudflare location
    test(base, key)


if __name__ == "__main__":
    main()
