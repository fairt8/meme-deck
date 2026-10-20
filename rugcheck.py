# rugcheck.py
# one report per token, trimmed to the fields the desk reads. checks 1-9.
import requests
from config import FACTS

RC = "https://api.rugcheck.xyz/v1/tokens"

def report(mint: str) -> dict:
    r = requests.get(f"{RC}/{mint}/report", timeout=20)
    r.raise_for_status()                      # 404/empty = too fresh to index -> SKIP upstream
    d = r.json()
    token = d.get("token") or {}
    known = d.get("knownAccounts") or {}

    def is_pool(h):  # AMM vaults and lockers sit in topHolders; drop them before adding up the top 10
        tag = known.get(h.get("owner")) or known.get(h.get("address")) or {}
        return str(tag.get("type", "")).upper() in ("AMM", "LOCKER")

    holders = [h for h in (d.get("topHolders") or []) if not is_pool(h)]
    markets = sorted(d.get("markets") or [],
                     key=lambda m: ((m.get("lp") or {}).get("baseUSD") or 0) + ((m.get("lp") or {}).get("quoteUSD") or 0),
                     reverse=True)
    lp = (markets[0].get("lp") or {}) if markets else {}
    supply = token.get("supply") or 0
    risks = d.get("risks") or []
    return {
        "mint": mint,
        "symbol": (d.get("tokenMeta") or {}).get("symbol"),
        "rugged": bool(d.get("rugged")),
        "risk_score": d.get("score_normalised"),
        "danger": [x.get("name") for x in risks if x.get("level") == "danger"],
        "warn": [x.get("name") for x in risks if x.get("level") == "warn"],
        "mint_authority": token.get("mintAuthority") or d.get("mintAuthority"),
        "freeze_authority": token.get("freezeAuthority") or d.get("freezeAuthority"),
        "lp_locked_pct": lp.get("lpLockedPct", d.get("lpLockedPct")) if markets else None,
        "top10_pct": round(sum(h.get("pct") or 0 for h in holders[:10]), 2) if d.get("topHolders") is not None else None,
        "dev_pct": round((d.get("creatorBalance") or 0) / supply * 100, 2) if supply else None,
        "insiders": sum(1 for h in holders if h.get("insider")) + (1 if d.get("graphInsidersDetected") else 0),
        "holders": d.get("totalHolders"),
    }

def fact_kill(t: dict) -> str | None:
    """Plain comparisons. First failure wins, the reason is logged. NULL IS NOT CLEAN."""
    if t["risk_score"] is None: return "no_report"
    if t["rugged"]: return "rugged"
    if t["mint_authority"]: return "mint_open"
    if t["freeze_authority"]: return "freeze_open"
    if t["danger"]: return "danger:" + "|".join(map(str, t["danger"]))
    if t["risk_score"] > FACTS["max_risk_score"]: return "risk_score"
    if t["lp_locked_pct"] is None or t["lp_locked_pct"] < FACTS["min_lp_locked_pct"]:
        return "lp_unlocked"
    if t["top10_pct"] is None or t["top10_pct"] > FACTS["max_top10_pct"]:
        return "top10_heavy"
    if t["dev_pct"] is None or t["dev_pct"] > FACTS["max_dev_pct"]:
        return "dev_holds"
    if t["insiders"] > FACTS["max_insiders"]: return "insiders"
    return None
