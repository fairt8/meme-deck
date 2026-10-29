# insightx.py - check 13b: bundlers and holder clusters from InsightX (free plan: 5 req/min, 1,000 req/month).
# runs only on tokens that passed checks 1-13 and the free judge, right before the check-14 queue.
# KILL if bundlers hold > INSIGHTX["max_bundler_pct"] of supply, or any single cluster holds > INSIGHTX["max_cluster_pct"]
# (clusters tagged liquidity_pool / exchange / vesting / locker are ignored).
# calls: GET /dex-metrics/v1/sol/<mint> (overview: bundlers_pct + total cluster_pct). only when the total cluster_pct is
# over the cluster limit does it also call /clusters to find the largest single non-excluded cluster. so 1 call per
# token usually, 2 at most. results are cached per mint for CACHE_MIN, so the judge_x recheck does not pay twice.
# budget: a monthly counter in insightx_state.json, synced down from InsightX's own X-Quota-Month-Remaining header.
# at the budget, on 429, or with the source down: returns status "down" + a 'SOURCE DOWN: InsightX ...' note. the
# caller skips check 13b (no kill, no numbers). never prints the key.
import fcntl, json, os, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import requests
from config import INSIGHTX

BASE = "https://api.insightx.network/dex-metrics/v1/sol/"
F = "insightx_state.json"
PLAN_MONTH = 1000          # free plan monthly quota (used to turn X-Quota-Month-Remaining into calls used)
PLAN_MINUTE = 5
CACHE_MIN = 60
EXCLUDED = ("liquidity_pool", "exchange", "vesting", "locker")   # a cluster tag equal to or containing one of these is ignored

class Down(Exception): pass

def _locked(fn):
    """run fn(state) under an exclusive lock on insightx_state.json; scan, judge_x and the bot's /check share it."""
    fd = os.open(F + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try: st = json.load(open(F))
        except Exception: st = {}
        out = fn(st)
        tmp = F + ".tmp"; json.dump(st, open(tmp, "w"), indent=1); os.replace(tmp, F)
        return out
    finally:
        os.close(fd)

def usage() -> dict:
    month = time.strftime("%Y-%m")
    def f(st):
        if st.get("month") != month: return {"month": month, "calls": 0, "budget": INSIGHTX["monthly_budget"]}
        return {"month": month, "calls": st.get("calls", 0), "budget": INSIGHTX["monthly_budget"],
                "quota_remaining": st.get("quota_remaining")}
    return _locked(f)

def _reserve():
    """count one call before it is made. raises Down at the budget; waits out the 5/min window (max ~60 s)."""
    month = time.strftime("%Y-%m")
    while True:
        def f(st):
            if st.get("month") != month:
                st.clear(); st.update({"month": month, "calls": 0, "cache": {}})
            if st.get("calls", 0) >= INSIGHTX["monthly_budget"]:
                return ("budget", 0)
            minute = int(time.time() // 60)
            stamps = [t for t in st.get("stamps", []) if int(t // 60) == minute]
            if len(stamps) >= PLAN_MINUTE:
                return ("wait", 61 - time.time() % 60)
            stamps.append(time.time()); st["stamps"] = stamps
            st["calls"] = st.get("calls", 0) + 1
            return ("ok", 0)
        what, wait = _locked(f)
        if what == "budget": raise Down(f"monthly budget {INSIGHTX['monthly_budget']} calls reached")
        if what == "ok": return
        time.sleep(wait)

def _sync(headers):
    rem = headers.get("X-Quota-Month-Remaining")
    try: rem = int(rem)
    except (TypeError, ValueError): return
    def f(st):
        st["quota_remaining"] = rem
        st["calls"] = max(st.get("calls", 0), PLAN_MONTH - rem)   # count calls made from anywhere on this account
    _locked(f)

def _get(path: str, key: str):
    _reserve()
    try:
        r = requests.get(BASE + path, headers={"X-API-Key": key}, timeout=20)
    except requests.RequestException as e:
        raise Down(type(e).__name__)
    _sync(r.headers)
    if r.status_code == 429: raise Down("HTTP 429 rate limited")
    if r.status_code != 200: raise Down(f"HTTP {r.status_code}")
    try: return r.json()
    except ValueError: raise Down("bad JSON")

def _num(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)): raise Down("missing field in response")
    return float(x)

def _cached(mint):
    def f(st):
        c = st.get("cache", {}).get(mint)
        return c if c and time.time() - c["ts"] < CACHE_MIN * 60 else None
    return _locked(f)

def _store(mint, res):
    def f(st):
        cache = {m: c for m, c in st.get("cache", {}).items() if time.time() - c["ts"] < 86400}
        cache[mint] = {"ts": time.time(), "res": res}; st["cache"] = cache
    _locked(f)

def check13b(mint: str) -> dict:
    """{'status': 'pass'|'kill'|'down', 'bundler_pct', 'max_cluster_pct', 'reason', 'calls'}"""
    c = _cached(mint)
    if c: return {**c["res"], "calls": 0, "cached": True}
    key = os.environ.get("INSIGHTX_API_KEY")
    if not key:
        return {"status": "down", "calls": 0, "reason": "SOURCE DOWN: InsightX (INSIGHTX_API_KEY not set), check 13b skipped"}
    calls = 0
    try:
        calls += 1; ov = _get(mint, key)
        bund, total = round(_num(ov.get("bundlers_pct")), 2), _num(ov.get("cluster_pct"))
        if bund == 0 and total == 0 and not ov.get("top10_pct"):
            raise Down("no holder data for this token yet")     # an empty snapshot is not a clean token: skip, don't guess
        res = {"bundler_pct": bund}
        if bund > INSIGHTX["max_bundler_pct"]:
            res.update(status="kill", max_cluster_pct=None,
                       reason=f"13b: bundlers hold {bund:.1f}% of supply (> {INSIGHTX['max_bundler_pct']}%)")
        elif total <= INSIGHTX["max_cluster_pct"]:
            # all clusters together are within the limit, so no single one can be over it: no second call
            res.update(status="pass", max_cluster_pct=f"<={total:.2f}",
                       reason=f"13b ok: bundlers {bund:.1f}%, all clusters {total:.1f}% total")
        else:
            calls += 1; cl = _get(mint + "/clusters", key)
            if not isinstance(cl.get("clusters"), list): raise Down("missing clusters list")
            keep = [x for x in cl["clusters"] if not any(any(e in str(t).lower() for e in EXCLUDED) for t in (x.get("tags") or []))]
            mx = max((_num(x.get("pct")) for x in keep), default=0.0)
            top = max(keep, key=lambda x: x.get("pct") or 0) if keep else {}
            res["max_cluster_pct"] = round(mx, 2)
            if mx > INSIGHTX["max_cluster_pct"]:
                res.update(status="kill", reason=f"13b: one holder cluster holds {mx:.1f}% of supply (> {INSIGHTX['max_cluster_pct']}%; "
                                                 f"tags {','.join(t for t in (top.get('tags') or []) if not t.startswith('funding-window:'))[:60]})")
            else:
                res.update(status="pass", reason=f"13b ok: bundlers {bund:.1f}%, largest cluster {mx:.1f}% "
                                                 f"({len(cl['clusters']) - len(keep)} pool/exchange/vesting cluster(s) ignored)")
    except Down as e:
        return {"status": "down", "calls": calls, "reason": f"SOURCE DOWN: InsightX ({e}), check 13b skipped"}
    _store(mint, res)
    return {**res, "calls": calls}

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] != "--usage":
        print(json.dumps(check13b(sys.argv[1].strip()), indent=1))
    print(json.dumps(usage()))
