# judge_x.py - check 14 for queued tokens. prints one line per verdict, nothing if there's nothing to do.
# for each token in pending_x_review.jsonl with a fresh x_posts/<mint>.json (< 60 min):
#   re-run limits + checks 1-13 + free judge live, then Gemini (no search) on the supplied posts.
#   BUY only if Gemini BUY, confidence >= MIN_CONFIDENCE, non-empty x_read -> paper buy + Telegram + log, then unqueue.
# tokens queued > 6h without a posts file expire as SKIP 'x_read_timeout'.
import os, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import check, xqueue

POSTS_MAX_AGE_MIN = 60
QUEUE_TTL_HOURS = 6

def main():
    for row in xqueue.load():
        mint, sym = row["mint"], row.get("symbol")
        posts = check.load_posts(mint, POSTS_MAX_AGE_MIN)
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        if posts is None:
            if time.time() - row.get("queued_ts", 0) > QUEUE_TTL_HOURS * 3600 and not os.path.exists(f"x_posts/{mint}.json"):
                check._migrate_header()
                check.log({"time": now, "mint": mint, "symbol": sym, "stage": "judge_x", "verdict": "SKIP", "reason": "x_read_timeout"})
                xqueue.unqueue(mint)
                print(f"{sym}: SKIP x_read_timeout (queued {row.get('queued')}, no X posts within {QUEUE_TTL_HOURS}h)")
            continue
        if posts.get("test"):
            # hand-made test file: run the full path read-only. never fills, never logs, never unqueues.
            v = check.check(mint, readonly=True, posts_doc=posts); v.pop("_ctx", None)
            print(f"TEST {v.get('symbol') or sym}: {v['verdict']} at {v['stage']} - {v['reason']} | x_read: {v.get('x_read')} "
                  f"| main_risk: {v.get('main_risk')} | conf {v.get('x_confidence')} | judge: {v.get('judge_model')} (no fill, nothing logged)")
            continue
        v = check.check(mint, readonly=False, posts_doc=posts)
        v.pop("_ctx", None); v["mint"] = mint
        if v["verdict"] == "BUY": check.fill(mint, v)
        check._migrate_header()
        check.log({"time": now, **v})
        if v["stage"] in ("limits",) or "rate limited" in str(v.get("reason")) or "judge error" in str(v.get("reason")) \
                or "down" in str(v.get("reason")):
            # a limit or a failed source is not a verdict on the token: keep it queued
            print(f"{v.get('symbol') or sym}: SKIP at {v['stage']} - {v['reason']} (still queued)")
            continue
        xqueue.unqueue(mint)
        line = f"{v.get('symbol') or sym}: {v['verdict']} at {v['stage']} - {v['reason']}"
        if v.get("x_read"): line += f" | x_read: {v['x_read']}"
        if v.get("judge_model"): line += f" | judge: {v['judge_model']}"
        if v.get("action"): line += f" | {v['action']}"
        print(line)

if __name__ == "__main__":
    main()
