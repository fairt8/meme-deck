# dashboard.py - writes web/data.json (all numbers the pages show), web/index.html (= the card UI in web/app/index.html,
# reading data.json), web/static.html (the old no-JavaScript tables) and web/balance.png from the desk files.
# read-only on the desk; publishes nothing.
import base64, csv, html, io, os, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from collections import Counter
from config import LOG, START_BALANCE, FEE_PCT, SLIPPAGE_PCT, TICKET_USD, PAPER
import book
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt, datetime

E = lambda x: html.escape(str(x if x is not None else ""))
checks = list(csv.DictReader(open(LOG))) if os.path.exists(LOG) else []
trades = book.trades(); opn = book.load()
eq = book.cash() + sum(p["qty"] * p.get("last", p["entry"]) * (1 - (FEE_PCT + SLIPPAGE_PCT) / 100) for p in opn.values())
pnl_by = Counter()
for t in trades:
    if t["action"] in ("close", "partial"): pnl_by[t["mint"]] += float(t["pnl"])
closed = {t["mint"] for t in trades if t["action"] == "close"}
wins = sum(1 for m in closed if pnl_by[m] > 0); losses = len(closed) - wins
kills = [r for r in checks if r["verdict"] == "KILL"]
rugs = sum(1 for r in kills if r["stage"] == "facts")
reasons = Counter(r["reason"] for r in kills).most_common(8)

png = b""
if os.path.exists("equity.csv"):
    rows = list(csv.DictReader(open("equity.csv")))
    xs = [datetime.datetime.strptime(r["time"], "%Y-%m-%d %H:%M:%S") for r in rows]
    fig = plt.figure(figsize=(9, 4))
    plt.plot(xs, [float(r["equity"]) for r in rows], marker="o", label="equity")
    plt.plot(xs, [float(r["cash"]) for r in rows], ls="--", marker=".", label="cash")
    plt.axhline(START_BALANCE, color="gray", ls=":", lw=.8, label=f"start ${START_BALANCE:.0f}")
    plt.title("Paper balance (WAT, UTC+1)"); plt.grid(alpha=.3); plt.legend(); fig.autofmt_xdate(); plt.tight_layout()
    buf = io.BytesIO(); plt.savefig(buf, format="png", dpi=100); png = buf.getvalue()
    open("web/balance.png", "wb").write(png); plt.close(fig)

def table(head, rows):
    return ("<table><tr>" + "".join(f"<th>{E(h)}</th>" for h in head) + "</tr>" +
            "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</table>") if rows else "<p class=m>none</p>"

open_rows = [[E(p["symbol"]), f"<code>{E(m)}</code>", f"${p['usd']}", f"{p['entry']:.6g}", f"{p.get('last', p['entry']):.6g}",
              f"{(p.get('last', p['entry'])/p['entry']-1)*100:+.1f}%", time.strftime("%m-%d %H:%M", time.localtime(p["opened"]))] for m, p in opn.items()]
trade_rows = [[E(t["time"]), E(t["symbol"]), E(t["action"]), f"${float(t['usd']):.2f}", f"${float(t['pnl']):+.2f}", E(t["reason"])] for t in trades[-20:][::-1]]
kill_rows = [[E(r["time"]), E(r["symbol"] or r["mint"][:6]), f"<code>{E(r['mint'])}</code>", E(r["stage"]), E(r["reason"]),
              E(r.get("bundler_pct") or ""), E(r.get("max_cluster_pct") or "")] for r in kills[-25:][::-1]]
img = f'<img src="data:image/png;base64,{base64.b64encode(png).decode()}" alt="balance">' if png else "<p class=m>no balance history yet</p>"

page = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RUG DESK {'(PAPER)' if PAPER else ''}</title><style>
body{{font-family:system-ui,sans-serif;background:#0b0f0c;color:#e6efe8;margin:0;padding:16px;max-width:1000px;margin:auto}}
h1{{color:#5cff8a;margin:0 0 4px}} .m{{color:#8a9a8f}} .cards{{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}}
.c{{background:#141b16;border:1px solid #23302a;border-radius:10px;padding:10px 14px;min-width:120px}} .c b{{display:block;font-size:22px}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin-bottom:18px}} th,td{{padding:5px 6px;border-bottom:1px solid #23302a;text-align:left}}
th{{color:#8a9a8f}} code{{font-size:11px;word-break:break-all}} img{{max-width:100%;background:#fff;border-radius:8px}}
</style></head><body>
<h1>RUG DESK {'— PAPER TRADING' if PAPER else ''}</h1>
<div class=m>simulated fills at live DexScreener prices, no real funds. updated {time.strftime('%Y-%m-%d %H:%M:%S')} WAT (UTC+1). ticket ${TICKET_USD} flat.</div>
<div class=cards>
<div class=c>equity<b>${eq:.2f}</b><span class=m>{(eq/START_BALANCE-1)*100:+.2f}% vs ${START_BALANCE:.0f}</span></div>
<div class=c>cash<b>${book.cash():.2f}</b></div><div class=c>open<b>{len(opn)}</b></div>
<div class=c>wins / losses<b>{wins} / {losses}</b></div><div class=c>realized<b>${sum(pnl_by.values()):+.2f}</b></div>
<div class=c>rugs blocked<b>{rugs}</b><span class=m>+{sum(1 for r in kills if r['stage']=='pool')} pool kills</span></div>
<div class=c>tokens checked<b>{len(checks)}</b></div></div>
{img}
<h2>Top kill reasons</h2>{table(["reason", "count"], [[E(r), n] for r, n in reasons])}
<h2>Open positions</h2>{table(["symbol", "CA", "in", "entry", "last", "pnl", "opened"], open_rows)}
<h2>Recent trades</h2>{table(["time", "symbol", "action", "usd", "pnl", "reason"], trade_rows)}
<h2>Recent kills</h2>{table(["time", "symbol", "CA", "stage", "reason", "bundler %", "max cluster %"], kill_rows)}
</body></html>"""
open("web/static.html", "w").write(page)   # 2026-11-03: the old tables page moved here; web/index.html is the card UI
import shutil; shutil.copyfile("web/app/index.html", "web/index.html.tmp"); os.replace("web/index.html.tmp", "web/index.html")
print_path = os.path.abspath("web/index.html")
if __name__ == "__main__" and os.environ.get("DASH_VERBOSE"): print(print_path)

# ---- web/data.json for the Telegram Mini App (no secrets: only desk files + public config numbers) ----
import json, subprocess, sys
import config as C
try:
    rep = subprocess.run([sys.executable, "report.py"], capture_output=True, text=True, timeout=120).stdout
    rep = "\n".join(l for l in rep.splitlines() if not l.startswith("chart:")).strip()
except Exception as e:
    rep = f"report unavailable: {type(e).__name__}"
eqrows = list(csv.DictReader(open("equity.csv"))) if os.path.exists("equity.csv") else []
data = {
    "updated": time.strftime("%Y-%m-%d %H:%M:%S") + " WAT", "updated_ts": int(time.time()), "paper": PAPER,
    "start_balance": START_BALANCE, "ticket_usd": TICKET_USD, "cash": round(book.cash(), 4), "equity": round(eq, 4),
    "realized_pnl": round(sum(pnl_by.values()), 4), "wins": wins, "losses": losses,
    "rugs_blocked": rugs, "pool_kills": sum(1 for r in kills if r["stage"] == "pool"), "checked": len(checks),
    "top_kills": [[r, n] for r, n in Counter(r["reason"] for r in kills).most_common(10)],
    "positions": [{"mint": m, "symbol": p["symbol"], "usd": p["usd"], "entry": p["entry"], "last": p.get("last", p["entry"]),
                   "peak": p["peak"], "steps": p["steps"], "opened": time.strftime("%Y-%m-%d %H:%M", time.localtime(p["opened"])),
                   "pct": round((p.get("last", p["entry"]) / p["entry"] - 1) * 100, 2),
                   "url": f"https://dexscreener.com/solana/{m}"} for m, p in opn.items()],
    "trades": trades[-100:][::-1],
    "kills": [{k: r.get(k) for k in ("time", "mint", "symbol", "stage", "reason", "liq_usd", "risk_score", "top10_pct", "dev_pct", "insiders", "x_read", "main_risk", "bundler_pct", "max_cluster_pct")} for r in kills[-60:][::-1]],
    "equity_series": [[r["time"], float(r["equity"]), float(r["cash"])] for r in eqrows[-300:]],
    "report": rep,
    "config": {"TICKET_USD": C.TICKET_USD, "FACTS": C.FACTS, "MIN_CONFIDENCE": C.MIN_CONFIDENCE, "EXIT": C.EXIT,
               "MAX_OPEN": C.MAX_OPEN, "MAX_ENTRIES_PER_DAY": C.MAX_ENTRIES_PER_DAY, "DAILY_LOSS_HALT_USD": C.DAILY_LOSS_HALT_USD,
               "COOLDOWN_HOURS": C.COOLDOWN_HOURS},
}

# ---- 2026-11-03: extra fields for the card UI (computed only from the desk files; nothing estimated) ----
import xqueue, deskstate
COST = (FEE_PCT + SLIPPAGE_PCT) / 100
# closed trades = one row per position, open -> close, partial legs summed
eps, cur = [], {}
for t in trades:
    m = t["mint"]
    if t["action"] == "open":
        cur[m] = {"mint": m, "symbol": t["symbol"], "opened": t["time"], "usd": float(t["usd"]), "pnl": 0.0, "legs": []}
    elif t["action"] in ("partial", "close") and m in cur:
        e = cur[m]; e["pnl"] += float(t["pnl"]); e["legs"].append(t["reason"])
        if t["action"] == "close":
            e.update(closed=t["time"], reason=t["reason"], pnl=round(e["pnl"], 4), ret_pct=round(e["pnl"] / e["usd"] * 100, 2) if e["usd"] else 0)
            eps.append(cur.pop(m))
gains = sum(e["pnl"] for e in eps if e["pnl"] > 0); loss = -sum(e["pnl"] for e in eps if e["pnl"] <= 0)
daily = Counter()
for t in trades:
    if t["action"] in ("partial", "close"): daily[t["time"][:10]] += float(t["pnl"])
mdd_pct = mdd_usd = 0.0; pk = None
for r in eqrows:
    v = float(r["equity"]); pk = v if pk is None else max(pk, v)
    if pk and (pk - v) > mdd_usd: mdd_usd, mdd_pct = pk - v, (pk - v) / pk * 100
ladder = C.EXIT["ladder"]
def pos_extra(m, p):
    last = p.get("last", p["entry"]); taken = p.get("taken") or [(100, 200)[i] for i in range(min(p.get("steps", 0), 2))]
    basis = p["usd"] * p["qty"] / p["qty0"] if p.get("qty0") else p["usd"]
    nxt = next((lv for lv, _ in ladder if lv not in taken), None)
    armed = bool(taken) or p["peak"] >= p["entry"] * (1 + C.EXIT["trail_arm_pct"] / 100)
    return {"taken": taken, "qty_left_pct": round(p["qty"] / p["qty0"] * 100, 1) if p.get("qty0") else 100,
            "stop_px": p["entry"] * (1 + C.EXIT["stop_pct"] / 100), "next_tp": nxt,
            "next_tp_px": p["entry"] * (1 + nxt / 100) if nxt is not None else None,
            "trail_armed": armed, "trail_px": p["peak"] * (1 - C.EXIT["trail_pct"] / 100) if armed else None,
            "unreal_usd": round(p["qty"] * last * (1 - COST) - basis, 4), "unreal_pct": round(((last * (1 - COST)) / p["entry"] - 1) * 100, 2),
            "realized_usd": round(sum(float(t["pnl"]) for t in trades if t["mint"] == m and t["action"] == "partial"
                                      and t["time"] >= time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p["opened"]))), 4),
            "hours": round((time.time() - p["opened"]) / 3600, 1)}
for d_ in data["positions"]: d_.update(pos_extra(d_["mint"], opn[d_["mint"]]))
day_ago = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 86400))
recent = [r for r in checks if r["time"] >= day_ago]
def src(name, key, stages=None):
    seen = [r for r in recent if not stages or r["stage"] in stages]
    hits = [r for r in seen if key in (r.get("reason") or "")]
    return {"name": name, "down_24h": len(hits), "last_down": hits[-1]["time"] if hits else None, "rows_24h": len(seen)}
ds = deskstate.load()
ixs = json.load(open("insightx_state.json")) if os.path.exists("insightx_state.json") else {}
data.update({
    "unrealized_pnl": round(sum(p["unreal_usd"] for p in data["positions"]), 4),
    "closed": eps[::-1], "closed_count": len(eps),
    "win_rate": round(sum(1 for e in eps if e["pnl"] > 0) / len(eps) * 100, 1) if eps else None,
    "avg_ret_pct": round(sum(e["ret_pct"] for e in eps) / len(eps), 2) if eps else None,
    "expectancy_usd": round(sum(e["pnl"] for e in eps) / len(eps), 4) if eps else None,
    "profit_factor": (round(gains / loss, 2) if loss else None) if eps else None,
    "max_dd_pct": round(mdd_pct, 2), "max_dd_usd": round(mdd_usd, 4),
    "daily_pnl": sorted([[k, round(v, 4)] for k, v in daily.items()], reverse=True),
    "pending_x": [{k: r.get(k) for k in ("mint", "symbol", "queued", "queued_ts", "free_confidence", "url", "x_read")} for r in xqueue.load()],
    "insightx_kills": sum(1 for r in kills if r["stage"] == "insightx"), "x_kills": sum(1 for r in kills if r["stage"] == "judge_x"),
    "checked_24h": len(recent), "kills_24h": sum(1 for r in recent if r["verdict"] == "KILL"),
    "since": (eqrows[0]["time"] if eqrows else None),
    "sources": [src("Rugcheck (down or not indexed yet)", "rugcheck down"), src("DexScreener", "dexscreener down"), src("Jupiter sell test", "jupiter down"),
                src("InsightX 13b", "SOURCE DOWN: InsightX"), src("X read (Gemini / GLM)", "down", ("judge_x",))],
    "quotas": {"insightx_calls_month": ixs.get("calls"), "insightx_month": ixs.get("month"), "insightx_quota_remaining": ixs.get("quota_remaining"),
               "insightx_budget": C.INSIGHTX["monthly_budget"], "apify_fetches_today": ds.get("apify_fetches") if ds.get("apify_day") == time.strftime("%Y-%m-%d") else 0,
               "apify_max_per_day": C.APIFY_MAX_FETCHES_PER_DAY},
    "last_run": ds.get("last_run"), "last_scan": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ds["last_scan_ts"])) if ds.get("last_scan_ts") else None,
    "runs": ds.get("runs"),
})
step = max(1, len(eqrows) // 300)   # sparkline: whole history, at most ~300 points, last point always kept
data["equity_series"] = [[r["time"], float(r["equity"]), float(r["cash"])] for r in (eqrows[::step] + ([eqrows[-1]] if eqrows and (len(eqrows) - 1) % step else []))]
data["config"].update({"INSIGHTX": {k: v for k, v in C.INSIGHTX.items()}, "START_BALANCE": START_BALANCE, "FEE_PCT": FEE_PCT, "SLIPPAGE_PCT": SLIPPAGE_PCT})
os.makedirs("web/app", exist_ok=True)
tmp = "web/data.json.tmp"; json.dump(data, open(tmp, "w"), default=str); os.replace(tmp, "web/data.json")
