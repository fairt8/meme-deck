# market.py
# the pool itself: depth, age, price, and whether anyone is actually selling. checks 10-13.
import time
import requests
from config import FACTS, TICKET_USD, SELL_TEST_SOL, MIN_ROUNDTRIP, WHALE_MIN_SOL

DS = "https://api.dexscreener.com/tokens/v1/solana"
JUP = "https://lite-api.jup.ag/swap/v1/quote"
RPC = "https://api.mainnet-beta.solana.com"
SOL = "So11111111111111111111111111111111111111112"

def pool(mint: str) -> dict | None:
    r = requests.get(f"{DS}/{mint}", timeout=15)
    r.raise_for_status()
    data = r.json()
    pairs = data if isinstance(data, list) else (data.get("pairs") or [])
    pairs = [p for p in pairs if (p.get("baseToken") or {}).get("address") == mint]
    if not pairs:
        return None
    p = max(pairs, key=lambda x: (x.get("liquidity") or {}).get("usd") or 0)
    h1 = (p.get("txns") or {}).get("h1") or {}
    m5 = (p.get("txns") or {}).get("m5") or {}
    born = p.get("pairCreatedAt")
    return {
        "symbol": (p.get("baseToken") or {}).get("symbol"),
        "price": float(p.get("priceUsd") or 0),
        "liq_usd": (p.get("liquidity") or {}).get("usd") or 0,
        "age_min": round((time.time() * 1000 - born) / 60000) if born else None,
        "buys_1h": h1.get("buys", 0),
        "sells_1h": h1.get("sells", 0),
        "buys_5m": m5.get("buys", 0), "sells_5m": m5.get("sells", 0),
        "vol_1h": (p.get("volume") or {}).get("h1", 0),
        "chg_5m": (p.get("priceChange") or {}).get("m5"), "chg_1h": (p.get("priceChange") or {}).get("h1"),
        "pair": p.get("pairAddress"), "quote": (p.get("quoteToken") or {}).get("address"),
        "socials": [s.get("type") for s in ((p.get("info") or {}).get("socials") or [])],
        "websites": len((p.get("info") or {}).get("websites") or []),
        "links": [s.get("url") for s in ((p.get("info") or {}).get("socials") or [])] + [w.get("url") for w in ((p.get("info") or {}).get("websites") or [])],
        "boosts": (p.get("boosts") or {}).get("active", 0),
        "url": p.get("url"),
    }

def market_kill(m: dict | None) -> str | None:
    if not m: return "no_pool"
    if m["price"] <= 0: return "no_price"
    if m["liq_usd"] < FACTS["min_liquidity_usd"]: return "thin_pool"
    if TICKET_USD / m["liq_usd"] > FACTS["max_ticket_share"]: return "ticket_too_big"
    if m["age_min"] is None or m["age_min"] < FACTS["min_age_min"]:
        return "too_fresh"
    if m["age_min"] > FACTS["max_age_hours"] * 60: return "too_old"
    if m["buys_1h"] >= 20 and m["sells_1h"] == 0: return "no_sells"
    return None

def _quote(inp, out, amt):
    r = requests.get(JUP, params={"inputMint": inp, "outputMint": out, "amount": int(amt), "slippageBps": 1000}, timeout=15)
    return r.json() if r.status_code == 200 else None

def sell_test(mint: str) -> tuple[str | None, dict]:
    """Extra honeypot sim (free Jupiter quotes, nothing signed): buy SELL_TEST_SOL, quote selling it all back."""
    buy = _quote(SOL, mint, SELL_TEST_SOL * 1e9)
    if not buy or "outAmount" not in buy: return "no_buy_route", {}
    sell = _quote(mint, SOL, int(buy["outAmount"]))
    if not sell or "outAmount" not in sell: return "cant_sell", {}
    rt = int(sell["outAmount"]) / (SELL_TEST_SOL * 1e9)
    info = {"roundtrip": round(rt, 4), "impact_pct": round(float(buy.get("priceImpactPct") or 0) * 100, 3)}
    return ("cant_sell" if rt < MIN_ROUNDTRIP else None), info

def _rpc(method, params):
    for i in range(3):
        r = requests.post(RPC, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=20)
        if r.status_code == 429: time.sleep(2 + 2 * i); continue
        j = r.json()
        if "result" in j: return j["result"]
    raise RuntimeError("Solana public RPC unavailable")

def whale_buys(pair: str, mint: str, lookback: int = 20) -> list[dict]:
    """Recent pool txs where one signer spent >= WHALE_MIN_SOL (native + wSOL) and received the token."""
    from concurrent.futures import ThreadPoolExecutor
    sigs = [s for s in _rpc("getSignaturesForAddress", [pair, {"limit": lookback}]) if not s.get("err")]
    def tx(s):
        try: return _rpc("getTransaction", [s["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
        except Exception: return None
    with ThreadPoolExecutor(6) as ex: txs = list(ex.map(tx, sigs))
    out = []
    for s, t in zip(sigs, txs):
        if not t: continue
        m = t["meta"]; signer = t["transaction"]["message"]["accountKeys"][0]["pubkey"]
        tok = lambda bals, mt: sum(float(b["uiTokenAmount"]["uiAmount"] or 0) for b in bals or [] if b.get("owner") == signer and b["mint"] == mt)
        d_sol = (m["postBalances"][0] - m["preBalances"][0]) / 1e9 + tok(m.get("postTokenBalances"), SOL) - tok(m.get("preTokenBalances"), SOL)
        if d_sol <= -WHALE_MIN_SOL and tok(m.get("postTokenBalances"), mint) > tok(m.get("preTokenBalances"), mint):
            out.append({"sol": round(-d_sol, 1), "time": time.strftime("%Y-%m-%d %H:%M", time.localtime(s.get("blockTime") or 0)), "sig": s["signature"]})
    return out
