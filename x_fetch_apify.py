# x_fetch_apify.py - check-14 input without Grok Bot: real X posts via an Apify pay-per-result actor.
# reads pending_symbols.txt (mint<TAB>symbol), writes x_posts/<mint>.json in the format judge_x.py reads.
# token from env APIFY_TOKEN (or APIFY_API_TOKEN), never printed. budget guard in desk_state.json (WAT day).
# a token is fetched only if it has no x_posts file fresher than POSTS_MAX_AGE_MIN. Apify down -> say so, skip, stay queued.
import datetime, json, os, sys, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import requests
from config import APIFY_ACTOR, APIFY_RESULTS_PER_QUERY, APIFY_MAX_FETCHES_PER_DAY, APIFY_TIMEOUT_S
import deskstate

POSTS_MAX_AGE_MIN = 60   # same freshness judge_x.py demands

def _fresh(mint):
    p = f"x_posts/{mint}.json"
    if not os.path.exists(p): return False
    try:
        ts = datetime.datetime.fromisoformat(json.load(open(p))["fetched_at"].replace("Z", "+00:00")).timestamp()
    except Exception: ts = os.path.getmtime(p)
    return time.time() - ts < POSTS_MAX_AGE_MIN * 60

def queries(mint, sym):
    q = [mint]
    if sym: q.append(f"${sym} (solana OR pump OR pumpfun OR sol)")
    return q

def fetch(mint, sym, tok):
    qs = queries(mint, sym)
    r = requests.post(f"https://api.apify.com/v2/acts/{APIFY_ACTOR}/run-sync-get-dataset-items",
                      params={"timeout": APIFY_TIMEOUT_S, "maxItems": APIFY_RESULTS_PER_QUERY * len(qs)},
                      headers={"Authorization": f"Bearer {tok}"}, timeout=APIFY_TIMEOUT_S + 30,
                      json={"searchQueries": qs, "sort": "latest", "maxResults": APIFY_RESULTS_PER_QUERY})
    if r.status_code not in (200, 201): raise RuntimeError(f"HTTP {r.status_code}")
    rows = r.json()
    if not isinstance(rows, list): raise RuntimeError("unexpected response")
    posts, seen, errors = [], set(), []
    for t in rows:
        if not t.get("text") or not t.get("tweetId"):
            if t.get("status") not in (None, "success", "no_data"): errors.append(str(t.get("status")))
            continue
        if t["tweetId"] in seen: continue
        seen.add(t["tweetId"]); a = t.get("author") or {}
        posts.append({"text": t["text"], "author_username": t.get("authorUsername") or a.get("username"),
                      "author_created_at": a.get("createdAt"), "followers": a.get("followersCount"),
                      "created_at": t.get("createdAt"), "url": t.get("url")})
    if not posts and errors: raise RuntimeError("actor errors: " + ",".join(sorted(set(errors)))[:80])
    return {"mint": mint, "symbol": sym, "fetched_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": f"apify:{APIFY_ACTOR}", "queries": qs, "posts": posts}

def main():
    if not os.path.exists("pending_symbols.txt"): return
    todo = [l.rstrip("\n").split("\t") + [""] for l in open("pending_symbols.txt") if l.strip()]
    todo = [(m, s) for m, s, *_ in todo if not _fresh(m)]
    if not todo: return
    tok = os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_API_TOKEN")
    if not tok: print("SOURCE DOWN: Apify (APIFY_TOKEN not set), X fetch skipped"); return
    st = deskstate.load(); day = time.strftime("%Y-%m-%d")
    if st.get("apify_day") != day: st["apify_day"], st["apify_fetches"] = day, 0
    os.makedirs("x_posts", exist_ok=True)
    for mint, sym in todo:
        if st["apify_fetches"] >= APIFY_MAX_FETCHES_PER_DAY:
            print(f"{sym or mint[:6]}: X fetch skipped, Apify daily budget used ({APIFY_MAX_FETCHES_PER_DAY}/day)"); continue
        st["apify_fetches"] += 1; deskstate.save(st)       # count before the call: a failed paid call still counts
        try:
            doc = fetch(mint, sym, tok)
        except Exception as e:
            print(f"{sym or mint[:6]}: SOURCE DOWN: Apify ({str(e)[:80]}), X fetch skipped (still queued)"); continue
        tmp = f"x_posts/{mint}.json.tmp"; json.dump(doc, open(tmp, "w"), indent=1); os.replace(tmp, f"x_posts/{mint}.json")
        print(f"{sym or mint[:6]}: {len(doc['posts'])} X posts fetched via Apify")

if __name__ == "__main__":
    main()
