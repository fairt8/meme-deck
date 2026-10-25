# cf_pages_deploy.py - deploy web/ to Cloudflare Pages via the direct-upload API (same flow as `wrangler pages deploy`).
# env: CLOUDFLARE_API_TOKEN (Account > Cloudflare Pages: Edit only), CLOUDFLARE_ACCOUNT_ID, optional CF_PAGES_PROJECT (default meme-deck).
# creates the project on first run if missing. writes the live URL to ../.pages_url (bot_listener reads it). never prints the token.
import base64, json, mimetypes, os, sys
import requests
from blake3 import blake3
DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); WEB = os.path.join(DESK, "web")
TOK = os.environ.get("CLOUDFLARE_API_TOKEN", ""); ACC = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
PROJ = os.environ.get("CF_PAGES_PROJECT", "meme-deck")
API = "https://api.cloudflare.com/client/v4"
SKIP = {".git", ".github", ".nojekyll"}

def cf(method, path, auth=None, **kw):
    r = requests.request(method, API + path, headers={"Authorization": f"Bearer {auth or TOK}"}, timeout=60, **kw)
    try: j = r.json()
    except Exception: j = {"success": False, "errors": [{"message": f"HTTP {r.status_code}"}]}
    if not j.get("success"):
        raise RuntimeError(f"{method} {path.split('?')[0]} -> HTTP {r.status_code} {[e.get('message') for e in j.get('errors', [])][:2]}")
    return j.get("result")

def files():
    out = {}
    for root, dirs, fs in os.walk(WEB):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for f in fs:
            if f in SKIP or f.endswith(".tmp"): continue
            p = os.path.join(root, f); rel = "/" + os.path.relpath(p, WEB).replace(os.sep, "/")
            data = open(p, "rb").read(); b64 = base64.b64encode(data).decode()
            ext = os.path.splitext(f)[1].lstrip(".")
            h = blake3((b64 + ext).encode()).hexdigest()[:32]   # wrangler's asset key: blake3(base64(content) + extension)[:32]
            out[rel] = dict(hash=h, b64=b64, ctype=mimetypes.guess_type(f)[0] or "application/octet-stream")
    return out

def project():
    try: return cf("GET", f"/accounts/{ACC}/pages/projects/{PROJ}")
    except RuntimeError as e:
        if "404" not in str(e) and "not found" not in str(e).lower(): raise
    print(f"cf-pages: creating project {PROJ}")
    return cf("POST", f"/accounts/{ACC}/pages/projects", json={"name": PROJ, "production_branch": "main"})

def main():
    if not TOK or not ACC: print("cf-pages: CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID missing, skipped"); return 0
    p = project(); url = f"https://{p.get('subdomain') or PROJ + '.pages.dev'}"
    fs = files()
    jwt = cf("GET", f"/accounts/{ACC}/pages/projects/{PROJ}/upload-token")["jwt"]
    hashes = sorted({v["hash"] for v in fs.values()})
    missing = set(cf("POST", "/pages/assets/check-missing", auth=jwt, json={"hashes": hashes}) or [])
    up = [v for v in {v["hash"]: v for v in fs.values()}.values() if v["hash"] in missing]
    for i in range(0, len(up), 20):
        cf("POST", "/pages/assets/upload", auth=jwt, json=[{"key": v["hash"], "value": v["b64"], "metadata": {"contentType": v["ctype"]}, "base64": True} for v in up[i:i+20]])
    cf("POST", "/pages/assets/upsert-hashes", auth=jwt, json={"hashes": hashes})
    manifest = {k: v["hash"] for k, v in fs.items()}
    d = cf("POST", f"/accounts/{ACC}/pages/projects/{PROJ}/deployments",
           files={"manifest": (None, json.dumps(manifest)), "branch": (None, "main")})
    open(os.path.join(DESK, ".pages_url"), "w").write(url + "\n")
    print(f"cf-pages: deployed {len(fs)} files ({len(up)} uploaded) -> {url} [{d.get('id', '')[:8]}]")
    return 0

if __name__ == "__main__":
    try: sys.exit(main())
    except Exception as e: print(f"cf-pages: deploy failed: {str(e)[:300]}"); sys.exit(1)
