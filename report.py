# report.py
# the evening report (21:30). everything in it comes from checks.csv, trades.csv, positions.json.
# python3 report.py          -> today's evening report + all-time paper summary + balance.png
import csv, os, sys, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from collections import Counter
from config import LOG, PAPER, START_BALANCE, FEE_PCT, SLIPPAGE_PCT
import book
from notify import send
SEND = "--send" in sys.argv
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
_buf = []; _print = print
def print(*a, **k):
    _buf.append(" ".join(map(str, a))); _print(*a, **k)

day = _args[0] if _args else time.strftime("%Y-%m-%d")
allchecks = [r for r in csv.DictReader(open(LOG))] if os.path.exists(LOG) else []
checks = [r for r in allchecks if r["time"].startswith(day)]
done = [t for t in book.trades() if t["time"].startswith(day) and t["action"] in ("close", "partial")]

by_stage = Counter(r["stage"] for r in checks if r["verdict"] in ("KILL", "SKIP"))
kills = Counter(r["stage"] for r in checks if r["verdict"] == "KILL")
buys = [r for r in checks if r["verdict"] == "BUY"]
wins = [t for t in done if float(t["pnl"]) > 0]
reasons = Counter(r["reason"] for r in checks if r["verdict"] == "KILL")

print(f"EVENING REPORT {day} {'(PAPER)' if PAPER else '(LIVE)'}  [times WAT, UTC+1]")
print(f"checked: {len(checks)}")
print(f"killed by rug filter: {kills['facts']} | by pool: {kills['pool']} | by judge: {by_stage['judge']} | by limits: {by_stage['limits']}"
      f" | skipped (source down/unindexed): {sum(1 for r in checks if r['verdict']=='SKIP' and r['stage'] in ('facts','pool'))}")
print(f"bought: {len(buys)} | open now: {len(book.load())}")
print(f"realized pnl today: ${book.today_pnl():+.2f}")
if done:
    print(f"green exits: {len(wins)}/{len(done)}")
    best = max(done, key=lambda t: float(t["pnl"])); worst = min(done, key=lambda t: float(t["pnl"]))
    print(f"best: {best['symbol']} ${float(best['pnl']):+.2f} ({best['reason']}, {best['time']}) | worst: {worst['symbol']} ${float(worst['pnl']):+.2f} ({worst['reason']}, {worst['time']})")
if reasons:
    top, n = reasons.most_common(1)[0]
    print(f"most common kill: {top} ({n}x)")

# ---- all-time paper summary ----
opn = book.load()
eq = book.cash() + sum(p["qty"] * p.get("last", p["entry"]) * (1 - (FEE_PCT + SLIPPAGE_PCT) / 100) for p in opn.values())
closes = [t for t in book.trades() if t["action"] in ("close", "partial")]
pos_pnl = Counter()
for t in closes: pos_pnl[t["mint"]] += float(t["pnl"])
closed_mints = {t["mint"] for t in book.trades() if t["action"] == "close"}
w = sum(1 for m in closed_mints if pos_pnl[m] > 0); l = len(closed_mints) - w
print(f"\nALL-TIME (PAPER): start ${START_BALANCE:.2f} | cash ${book.cash():.2f} | equity ${eq:.2f} ({(eq/START_BALANCE-1)*100:+.2f}%)")
print(f"closed positions: {len(closed_mints)} | wins {w} | losses {l} | realized ${sum(pos_pnl.values()):+.2f}")
print(f"rugs blocked (rug filter kills, all time): {sum(1 for r in allchecks if r['verdict']=='KILL' and r['stage']=='facts')} "
      f"| pool kills: {sum(1 for r in allchecks if r['verdict']=='KILL' and r['stage']=='pool')}")
kc = Counter(r["reason"] for r in allchecks if r["verdict"] == "KILL")
print("kill reasons: " + ", ".join(f"{k} {n}x" for k, n in kc.most_common()))
for r in [r for r in allchecks if r["verdict"] == "KILL"][-5:]:
    print(f"  e.g. {r['time']} {r['symbol'] or r['mint'][:6]} {r['mint']} -> {r['reason']}")
print("open positions:")
for m, p in opn.items():
    last = p.get("last", p["entry"])
    print(f"  {p['symbol']} {m} ${p['usd']} in @ {p['entry']:.6g}, last {last:.6g} ({(last/p['entry']-1)*100:+.1f}%), opened {time.strftime('%Y-%m-%d %H:%M', time.localtime(p['opened']))}, steps {p['steps']}")
if not opn: print("  (none)")
print("biggest closes:")
for t in sorted(closes, key=lambda t: -abs(float(t["pnl"])))[:5]:
    print(f"  {t['time']} {t['symbol']} {t['action']} ${float(t['pnl']):+.2f} ({t['reason']})")
if not closes: print("  (none yet)")

# ---- chart ----
if os.path.exists("equity.csv"):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt, datetime
    rows = list(csv.DictReader(open("equity.csv")))
    xs = [datetime.datetime.strptime(r["time"], "%Y-%m-%d %H:%M:%S") for r in rows]
    plt.figure(figsize=(9, 4.5))
    plt.plot(xs, [float(r["equity"]) for r in rows], marker="o", label="equity (cash + open, net exit costs)")
    plt.plot(xs, [float(r["cash"]) for r in rows], ls="--", marker=".", label="cash")
    plt.axhline(START_BALANCE, color="gray", ls=":", lw=0.8, label=f"start ${START_BALANCE:.0f}")
    plt.title("RUG DESK paper balance (WAT, UTC+1)"); plt.ylabel("USD"); plt.grid(alpha=.3); plt.legend()
    plt.gcf().autofmt_xdate(); plt.tight_layout(); plt.savefig("balance.png", dpi=110)
    print(f"\nchart: {os.path.abspath('balance.png')}")

if SEND:
    send("\n".join(l for l in _buf if not l.startswith("\nchart:")))
