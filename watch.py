# watch.py
# every open position, every 10 minutes. prints nothing when nothing happens. SILENCE IS A STATUS.
import os, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from config import EXIT, PAPER, FEE_PCT, SLIPPAGE_PCT
from market import pool
import book
from notify import send

def watch() -> list[str]:
    events = []
    for mint, p in list(book.load().items()):
        try:
            m = pool(mint)
        except Exception as e:
            events.append(f"{p['symbol']}: price fetch failed (DexScreener: {str(e)[:60]}), skipped this round")
            continue
        if not m or m["price"] <= 0:
            pnl = book.sell(mint, 1.0, 0.0, "pool_gone")
            events.append(f"{p['symbol']}: pool gone, wrote off, pnl ${pnl:+.2f}")
            continue
        price = m["price"]
        b = book.load(); s = b[mint]
        s["peak"] = max(s["peak"], price); s["last"] = price; s["last_liq"] = m["liq_usd"]; book.save(b)
        pct = (price / s["entry"] - 1) * 100
        hours = (time.time() - s["opened"]) / 3600
        exit_px = price * (1 - (FEE_PCT + SLIPPAGE_PCT) / 100)   # paper exit: live price minus fee + slippage

        def out(frac, why):
            pnl = book.sell(mint, frac, exit_px, why)
            verb = "sold" if PAPER else "SELL NOW"
            size = "the rest" if frac >= 1 else f"{frac*100:.0f}%"
            events.append(f"{s['symbol']}: {verb} {size} at {pct:+.0f}% ({why}), pnl ${pnl:+.2f}")

        if m["liq_usd"] < s["liq0"] * (1 - EXIT["liq_drop_pct"] / 100):
            out(1.0, "liquidity_pulled"); continue
        if pct <= EXIT["stop_pct"]:
            out(1.0, "stop"); continue
        ladder = EXIT["ladder"]
        if s["steps"] < len(ladder) and pct >= ladder[s["steps"]][0]:
            out(ladder[s["steps"]][1], f"take_profit_{ladder[s['steps']][0]}")
            b = book.load()
            if mint in b:
                b[mint]["steps"] += 1; book.save(b)
            continue
        if s["steps"] > 0 and price <= s["peak"] * (1 - EXIT["trail_pct"] / 100):
            out(1.0, "trailing_stop"); continue
        if hours >= EXIT["time_stop_hours"] and pct < EXIT["time_stop_min_pct"]:
            out(1.0, "time_stop")
    snapshot()
    return events

def snapshot():
    """append paper equity (cash + open positions at last live price, net exit costs) to equity.csv; silent."""
    eq = book.cash() + sum(p["qty"] * p.get("last", p["entry"]) * (1 - (FEE_PCT + SLIPPAGE_PCT) / 100) for p in book.load().values())
    new = not os.path.exists("equity.csv")
    with open("equity.csv", "a") as f:
        if new: f.write("time,cash,equity,open\n")
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')},{book.cash():.4f},{eq:.4f},{len(book.load())}\n")

if __name__ == "__main__":
    for e in watch():
        print(e)
        send("RUG DESK watch: " + e)
