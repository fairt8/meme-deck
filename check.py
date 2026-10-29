# check.py
# one contract address in, one verdict out. LIMITS -> FACTS -> POOL -> JUDGE -> FILL.
# usage: python3 check.py <mint> [--readonly] [--x]
# scan path: checks 1-13 + free judge + check 13b (InsightX bundlers/clusters, insightx.py). a pass is queued for check 14 (pending_x_review.jsonl); judge_x.py finishes it
# once x_posts/<mint>.json exists. --readonly: never opens a position, never writes checks.csv or the queue.
# --readonly --x: also runs check 14 if a fresh x_posts/<mint>.json exists (no search).
import csv, json, os, sys, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from config import LOG, PAPER, TICKET_USD, EXTRA_SELL_TEST, FEE_PCT, SLIPPAGE_PCT
from rugcheck import report, fact_kill
from market import pool, market_kill, sell_test
from judge import judge
import gemini, glm, xqueue, insightx
from config import MIN_CONFIDENCE, PENDING_X
import book
from notify import send

FIELDS = ["time", "mint", "symbol", "stage", "verdict", "reason", "confidence", "price", "liq_usd",
          "age_min", "risk_score", "lp_locked_pct", "top10_pct", "dev_pct", "insiders", "action", "x_read", "main_risk", "judge_model",
          "bundler_pct", "max_cluster_pct"]

def _migrate_header():
    """older checks.csv files lack the x_read/main_risk columns: rewrite once with the new header."""
    if not os.path.exists(LOG): return
    with open(LOG, newline="") as f:
        rows = list(csv.DictReader(f))
    with open(LOG, newline="") as f:
        head = f.readline().strip().split(",")
    if head == FIELDS: return
    tmp = LOG + ".tmp"
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader()
        for r in rows: w.writerow({k: r.get(k) for k in FIELDS})
    os.replace(tmp, LOG)

def unqueue(mint: str):
    """drop a judged token from pending_x_review.jsonl."""
    if not os.path.exists(PENDING_X): return
    keep = [l for l in open(PENDING_X) if l.strip() and json.loads(l).get("mint") != mint]
    tmp = PENDING_X + ".tmp"; open(tmp, "w").writelines(keep); os.replace(tmp, PENDING_X)

def x_judge(mint, token, m, base, free, posts_doc):
    """check 14: one grounded Gemini call. BUY only if Gemini says BUY with confidence >= MIN_CONFIDENCE."""
    needed = [k for k in ("risk_score", "lp_locked_pct", "top10_pct", "dev_pct") if token.get(k) is None] + \
             [k for k in ("price", "liq_usd", "age_min") if m.get(k) is None]
    if needed: return {"stage": "judge_x", "verdict": "SKIP", "reason": "null field(s): " + ",".join(needed), **base}
    payload = {"token": {k: token[k] for k in ("mint", "symbol", "rugged", "risk_score", "danger", "warn", "lp_locked_pct",
                                               "top10_pct", "dev_pct", "insiders", "holders")},
               "pool": {k: m.get(k) for k in ("symbol", "price", "liq_usd", "age_min", "buys_1h", "sells_1h", "vol_1h", "url", "links")},
               "free_judge": {"confidence": free["confidence"], "signals": [k for k, v in free["signals"].items() if isinstance(v, float) and v > 0]}}
    if not posts_doc.get("posts"):
        return {"stage": "judge_x", "verdict": "KILL", "reason": "x: zero posts on X", "x_read": "zero posts found by the operator's X fetch",
                "main_risk": "nobody knows it exists", **base}
    from config import GEMINI_MODEL, GLM_MODEL
    judge_model = f"gemini:{GEMINI_MODEL}"
    try:
        if posts_doc.get("test") and posts_doc.get("_simulate_gemini_failure"):
            raise gemini.JudgeError("gemini: simulated failure (test)")
        a = gemini.ask_posts(payload, posts_doc)
    except Exception as e1:               # 429, 5xx, timeout, bad JSON -> backup judge
        judge_model = f"glm:{GLM_MODEL} (gemini failed: {str(e1)[:60]})"
        try:
            a = glm.ask_posts(payload, posts_doc)
        except Exception as e2:
            rl = isinstance(e1, gemini.RateLimited) and isinstance(e2, glm.RateLimited)
            return {"stage": "judge_x", "verdict": "SKIP", "judge_model": "none",
                    "reason": ("judge rate limited" if rl else "judge error") + f": gemini {str(e1)[:60]}; glm {str(e2)[:60]}", **base}
    v = str(a.get("verdict", "")).upper(); conf = a.get("confidence")
    xr, risk = (a.get("x_read") or "").strip(), (a.get("main_risk") or "").strip()
    g = a.get("_grounding", {})
    out = {**base, "stage": "judge_x", "judge_model": judge_model, "x_read": xr, "main_risk": risk, "x_confidence": conf, "grounding": g,
           "free_confidence": free["confidence"], "confidence": conf}
    if v == "BUY" and isinstance(conf, (int, float)) and conf >= MIN_CONFIDENCE and xr:
        return {**out, "verdict": "BUY", "reason": "x: " + str(a.get("why", ""))[:200]}
    why = str(a.get("why", ""))[:200]
    if v == "BUY" and not xr: why = "BUY with empty x_read -> not trusted; " + why
    elif v == "BUY": why = f"low x confidence {conf}; " + why
    return {**out, "verdict": "KILL", "reason": "x: " + why}

def log(row: dict):
    new = not os.path.exists(LOG)
    with open(LOG, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new: w.writeheader()
        w.writerow({k: row.get(k) for k in w.fieldnames})

def load_posts(mint: str, max_age_min: int = 60):
    """x_posts/<mint>.json if it exists and was fetched < max_age_min ago, else None."""
    import datetime
    p = os.path.join("x_posts", f"{mint}.json")
    if not os.path.exists(p): return None
    d = json.load(open(p))
    try:
        ts = datetime.datetime.fromisoformat(str(d["fetched_at"]).replace("Z", "+00:00")).timestamp()
    except Exception:
        ts = os.path.getmtime(p)
    return d if time.time() - ts < max_age_min * 60 else None

def fill(mint: str, v: dict) -> dict:
    """the existing paper-buy path: live price + fee + slippage + impact, book entry, Telegram alert."""
    if PAPER:
        px = v["price"] * (1 + (FEE_PCT + SLIPPAGE_PCT + v.get("impact_pct", 0)) / 100)
        book.open_position(mint, v["symbol"], px, v["liq_usd"], TICKET_USD)
        v["action"] = f"PAPER BUY ${TICKET_USD} at {px:.10g} (live {v['price']})"
        send(f"RUG DESK PAPER BUY {v['symbol']}\nCA: {mint}\nfill ${px:.10g} (live ${v['price']}), ticket ${TICKET_USD}\n"
             f"X confidence {v.get('x_confidence')} (free {v.get('free_confidence')}) | judge: {v.get('judge_model')}\nX read: {v.get('x_read')}\n"
             f"main risk: {v.get('main_risk')}\n{v.get('url')}")
    else:
        v["action"] = (f"APPROVAL NEEDED: buy ${TICKET_USD} of {v['symbol']} {mint} in your own wallet, "
                       f"then run: python3 book.py add {mint} {TICKET_USD} <price> {v['liq_usd']}")
    return v

def check(mint: str, readonly: bool = False, posts_doc: dict | None = None) -> dict:
    g = book.guard(mint)
    if g and not readonly:
        return {"stage": "limits", "verdict": "SKIP", "reason": g}
    try:
        token = report(mint)
    except Exception as e:
        return {"stage": "facts", "verdict": "SKIP", "reason": f"rugcheck down/unindexed: {str(e)[:80]}"}
    facts = {k: token[k] for k in ("risk_score", "lp_locked_pct", "top10_pct", "dev_pct", "insiders")}
    if (k := fact_kill(token)):
        return {"stage": "facts", "verdict": "KILL", "reason": k, "symbol": token["symbol"], **facts}
    try:
        m = pool(mint)
    except Exception as e:
        return {"stage": "pool", "verdict": "SKIP", "reason": f"dexscreener down: {str(e)[:80]}", "symbol": token["symbol"], **facts}
    if (k := market_kill(m)):
        return {"stage": "pool", "verdict": "KILL", "reason": k, "symbol": (m or {}).get("symbol") or token["symbol"], **facts,
                **({"price": m["price"], "liq_usd": m["liq_usd"], "age_min": m["age_min"]} if m else {})}
    base = {"symbol": m["symbol"], "price": m["price"], "liq_usd": m["liq_usd"], "age_min": m["age_min"], "url": m["url"], **facts}
    sell_info = {}
    if EXTRA_SELL_TEST:
        try:
            k, sell_info = sell_test(mint)
        except Exception as e:
            return {"stage": "pool", "verdict": "SKIP", "reason": f"jupiter down: {str(e)[:80]}", **base}
        if k: return {"stage": "pool", "verdict": "KILL", "reason": k, **base}
    try:
        ans = judge(token, m, sell_info, record=not readonly)
    except Exception as e:
        return {"stage": "judge", "verdict": "SKIP", "reason": f"judge error: {str(e)[:80]}", **base}
    extra = {"impact_pct": sell_info.get("impact_pct", 0), **({"limits_note": g} if g else {})}
    if ans["verdict"] != "BUY":
        return {**ans, **base, "stage": "judge", "reason": ans["why"], **extra}
    # check 13b: InsightX bundlers + clusters. only here, after 1-13 and the free judge passed. down/budget -> skipped, no kill.
    ix = insightx.check13b(mint)
    if ix["status"] == "down":
        print(ix["reason"], file=sys.stderr)
        extra["insightx_note"] = ix["reason"]
    else:
        base = {**base, "bundler_pct": ix["bundler_pct"], "max_cluster_pct": ix["max_cluster_pct"]}
        extra["insightx_note"] = ix["reason"]
        if ix["status"] == "kill":
            return {**base, **extra, "stage": "insightx", "verdict": "KILL", "reason": ix["reason"], "free_confidence": ans["confidence"]}
    ctx = {"_ctx": {"token": token, "pool": m, "free": ans}}
    if posts_doc is None:
        if not readonly: xqueue.enqueue(mint, m["symbol"], ans["confidence"], m["url"])
        return {**ans, **base, **extra, **ctx, "stage": "judge", "verdict": "PENDING_X",
                "reason": ans["why"] + " | " + extra["insightx_note"] + " -> queued for check 14 (X read)", "free_confidence": ans["confidence"]}
    x = x_judge(mint, token, m, base, ans, posts_doc)
    if ix["status"] == "down": x["reason"] = str(x.get("reason")) + " | " + ix["reason"]
    return {**x, "signals": ans["signals"], **extra, **ctx}

if __name__ == "__main__":
    mint = sys.argv[1].strip()
    readonly = "--readonly" in sys.argv
    posts = load_posts(mint) if (readonly and "--x" in sys.argv) else None
    v = check(mint, readonly, posts)
    v.pop("_ctx", None)
    v["mint"] = mint
    if readonly:
        v["action"] = "READ-ONLY check: no position opened, nothing logged"
        if "--x" in sys.argv and posts is None: v["x_note"] = "check 14 not run: no x_posts/<mint>.json fresher than 60 min"
        print(json.dumps(v, indent=2, default=str)); sys.exit(0)
    if v["verdict"] == "BUY": fill(mint, v)
    _migrate_header()
    log({"time": time.strftime("%Y-%m-%d %H:%M:%S"), **v})
    print(json.dumps({k: v[k] for k in v if k not in ("signals",)} | ({"signals": v["signals"]} if "signals" in v else {}), indent=2, default=str))
