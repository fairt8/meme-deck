# book.py
# positions, trades, limits. the desk's memory lives in two files you can open yourself.
import csv, json, os, sys, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from config import (POSITIONS, TRADES, TICKET_USD, MAX_OPEN, MAX_ENTRIES_PER_DAY,
                    DAILY_LOSS_HALT_USD, COOLDOWN_HOURS, START_BALANCE)

FIELDS = ["time", "mint", "symbol", "action", "usd", "pnl", "reason"]

def load() -> dict:
    return json.load(open(POSITIONS)) if os.path.exists(POSITIONS) else {}

def save(book: dict):
    tmp = POSITIONS + ".tmp"; json.dump(book, open(tmp, "w"), indent=2); os.replace(tmp, POSITIONS)

def trades() -> list[dict]:
    return list(csv.DictReader(open(TRADES))) if os.path.exists(TRADES) else []

def record(mint, symbol, action, usd, pnl, reason):
    new = not os.path.exists(TRADES)
    with open(TRADES, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new: w.writeheader()
        w.writerow({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "mint": mint, "symbol": symbol,
                    "action": action, "usd": round(usd, 4), "pnl": round(pnl, 4), "reason": reason})

def today_pnl() -> float:
    day = time.strftime("%Y-%m-%d")
    return sum(float(t["pnl"]) for t in trades() if t["time"].startswith(day))

def cash() -> float:
    """Paper cash: start balance - tickets bought + sale proceeds."""
    c = START_BALANCE
    for t in trades():
        c += -float(t["usd"]) if t["action"] == "open" else float(t["usd"])
    return c

def guard(mint: str) -> str | None:
    """Limits run before any network call. A block here means the desk doesn't even look."""
    day = time.strftime("%Y-%m-%d")
    book = load()
    if today_pnl() <= -DAILY_LOSS_HALT_USD: return "daily_loss_halt"
    if mint in book: return "already_held"
    if len(book) >= MAX_OPEN: return "max_open"
    opens = [t for t in trades() if t["action"] == "open" and t["time"].startswith(day)]
    if len(opens) >= MAX_ENTRIES_PER_DAY: return "max_entries_today"
    cutoff = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - COOLDOWN_HOURS * 3600))
    if any(t["mint"] == mint and t["action"] == "close" and t["time"] >= cutoff for t in trades()):
        return "cooldown"
    if cash() < TICKET_USD: return "no_paper_cash"   # extra: paper bankroll can't cover a flat ticket
    return None

def open_position(mint, symbol, price, liq_usd, usd):
    book = load()
    book[mint] = {"symbol": symbol, "entry": price, "opened": time.time(), "peak": price,
                  "liq0": liq_usd, "usd": usd, "qty": usd / price, "qty0": usd / price, "steps": 0}
    save(book)
    record(mint, symbol, "open", usd, 0, "entry")

def sell(mint, frac_of_original, price, reason) -> float:
    """Sells a fraction of the ORIGINAL size (1.0 = everything that's left)."""
    book = load()
    p = book[mint]
    q = min(p["qty"], p["qty0"] * frac_of_original)
    pnl = q * (price - p["entry"])
    p["qty"] -= q
    action = "close" if p["qty"] <= p["qty0"] * 1e-9 else "partial"
    record(mint, p["symbol"], action, q * price, pnl, reason)
    if action == "close":
        del book[mint]
    save(book)
    return pnl

if __name__ == "__main__":
    # live mode: after you buy in your own wallet, tell the book. after you sell by hand, close it.
    cmd = sys.argv[1]
    if cmd == "add":     # python3 book.py add <mint> <usd> <price> <liq_usd>
        mint, usd, price, liq = sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
        open_position(mint, mint[:6], price, liq, usd)
    elif cmd == "close": # python3 book.py close <mint> <price>
        print(round(sell(sys.argv[2], 1.0, float(sys.argv[3]), "manual"), 2))
