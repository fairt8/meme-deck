# dashboard.py - builds a static, self-contained web/index.html (+ web/balance.png) from the desk files.
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
kill_rows = [[E(r["time"]), E(r["symbol"] or r["mint"][:6]), f"<code>{E(r['mint'])}</code>", E(r["stage"]), E(r["reason"])] for r in kills[-25:][::-1]]
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
<h2>Recent kills</h2>{table(["time", "symbol", "CA", "stage", "reason"], kill_rows)}
</body></html>"""
open("web/index.html", "w").write(page)
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
    "kills": [{k: r.get(k) for k in ("time", "mint", "symbol", "stage", "reason", "liq_usd", "risk_score", "top10_pct", "dev_pct", "insiders", "x_read", "main_risk")} for r in kills[-60:][::-1]],
    "equity_series": [[r["time"], float(r["equity"]), float(r["cash"])] for r in eqrows[-300:]],
    "report": rep,
    "config": {"TICKET_USD": C.TICKET_USD, "FACTS": C.FACTS, "MIN_CONFIDENCE": C.MIN_CONFIDENCE, "EXIT": C.EXIT,
               "MAX_OPEN": C.MAX_OPEN, "MAX_ENTRIES_PER_DAY": C.MAX_ENTRIES_PER_DAY, "DAILY_LOSS_HALT_USD": C.DAILY_LOSS_HALT_USD,
               "COOLDOWN_HOURS": C.COOLDOWN_HOURS},
}
os.makedirs("web/app", exist_ok=True)
tmp = "web/data.json.tmp"; json.dump(data, open(tmp, "w"), default=str); os.replace(tmp, "web/data.json")
