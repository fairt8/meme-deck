# xqueue.py - the check-14 queue. pending_x_review.jsonl (one JSON per line, one per mint) + pending_symbols.txt (mint<TAB>symbol).
import json, os, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from config import PENDING_X

def load() -> list[dict]:
    out, seen = [], set()
    if os.path.exists(PENDING_X):
        for l in open(PENDING_X):
            if not l.strip(): continue
            d = json.loads(l)
            if d.get("mint") and d["mint"] not in seen: seen.add(d["mint"]); out.append(d)
    return out

def _write(rows):
    tmp = PENDING_X + ".tmp"
    with open(tmp, "w") as f:
        for r in rows: f.write(json.dumps(r) + "\n")
    os.replace(tmp, PENDING_X)
    with open("pending_symbols.txt.tmp", "w") as f:
        for r in rows: f.write(f"{r['mint']}\t{r.get('symbol') or ''}\n")
    os.replace("pending_symbols.txt.tmp", "pending_symbols.txt")

def enqueue(mint, symbol, free_conf, url):
    rows = load()
    if any(r["mint"] == mint for r in rows): return
    rows.append({"mint": mint, "symbol": symbol, "queued": time.strftime("%Y-%m-%d %H:%M:%S"), "queued_ts": int(time.time()),
                 "free_confidence": free_conf, "url": url, "x_read": "PENDING"})
    _write(rows)

def unqueue(mint):
    _write([r for r in load() if r["mint"] != mint])

def rewrite(rows): _write(rows)
