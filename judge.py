# judge.py
# replaces grok.py: NO paid API, no key. a confidence score from free signals only.
# check 14 (the X read: no posts, copycat CA, bought hype, rug history) is NOT done here:
# every token that reaches the judge is appended to pending_x_review.jsonl for a human/free X review.
import json, time
from config import MIN_CONFIDENCE, PENDING_X
import market

def judge(token: dict, m: dict, sell_info: dict, record: bool = True) -> dict:
    sig = {}
    b, s = m["buys_1h"], m["sells_1h"]
    sig["buy_pressure"] = 0.20 if s and b / s >= 1.2 else 0.0
    sig["trend_up"] = 0.20 if (m["chg_1h"] or 0) > 0 and (m["chg_5m"] or 0) >= 0 else 0.0
    sig["active_volume"] = 0.15 if m["liq_usd"] and (m["vol_1h"] or 0) / m["liq_usd"] >= 0.3 else 0.0
    sig["x_linked"] = 0.10 if "twitter" in m["socials"] else 0.0
    sig["website"] = 0.05 if m["websites"] else 0.0
    sig["low_risk_score"] = 0.10 if (token["risk_score"] or 99) <= 10 else 0.0
    sig["no_warnings"] = 0.05 if not token["warn"] else 0.0
    sig["clean_roundtrip"] = 0.05 if sell_info.get("roundtrip", 0) >= 0.95 else 0.0
    whales = []
    try:
        whales = market.whale_buys(m["pair"], token["mint"]) if m.get("pair") else []
    except Exception as e:
        sig["whale_scan_error"] = str(e)[:60]
    sig["whale_200sol"] = 0.10 if whales else 0.0
    conf = round(sum(v for v in sig.values() if isinstance(v, float)), 2)
    verdict = "BUY" if conf >= MIN_CONFIDENCE else "SKIP"
    why = "free signals: " + ", ".join(k for k, v in sig.items() if isinstance(v, float) and v > 0) or "none"
    if verdict == "SKIP": why = f"low confidence {conf}; " + why
    return {"verdict": verdict, "confidence": conf, "why": why, "signals": sig,
            "whales": whales, "x_read": "pending (check 14: X posts -> judge_x.py)"}
