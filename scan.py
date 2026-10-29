# scan.py
# the optional lead source: fresh Solana tokens that just paid for a DexScreener profile.
# a paid profile is not a quality signal, it only means the dev spent money. the filter decides the rest.
import csv, json, os, subprocess, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import requests
from config import LOG, SCAN_MAX_NEW
from notify import send

# one verdict per token - but a token stopped only at the LIMITS stage (cash, slots, cooldown) never got a verdict,
# so it may be rechecked later.
seen = {r["mint"] for r in csv.DictReader(open(LOG)) if r["stage"] != "limits"} if os.path.exists(LOG) else set()
try:
    r = requests.get("https://api.dexscreener.com/token-profiles/latest/v1", timeout=15)
    r.raise_for_status()
    rows = r.json()
except Exception as e:
    msg = f"SOURCE DOWN: DexScreener token-profiles ({str(e)[:80]}), scan skipped"
    print(msg); send("RUG DESK scan: " + msg); sys.exit(0)

fresh = []
for t in rows if isinstance(rows, list) else []:
    m = t.get("tokenAddress")
    if t.get("chainId") == "solana" and m and m not in seen and m not in fresh:
        fresh.append(m)
for mint in fresh[:SCAN_MAX_NEW]:
    out = subprocess.run([sys.executable, "check.py", mint], capture_output=True, text=True, timeout=300).stdout
    try:
        v = json.loads(out)
    except Exception:
        print(f"{mint}: check.py gave no verdict"); continue
    if v.get("insightx_note"):   # check 13b ran (or was skipped: SOURCE DOWN: InsightX ...) - one journal line per token
        print(f"{v.get('symbol') or mint[:6]}: {v['insightx_note']}" + (" -> KILL" if v.get("stage") == "insightx" else ""))
    if v.get("verdict") == "BUY":
        print(f"BUY {v.get('symbol')} conf {v.get('confidence')} | x_read: {v.get('x_read')} | {v.get('why')} | {v.get('action')} | {v.get('url')}")
    elif "down" in str(v.get("reason", "")):
        msg = f"{v.get('symbol') or mint[:6]}: SKIP at {v['stage']} - {v['reason']}"
        print(msg); send("RUG DESK scan, source down: " + msg)
