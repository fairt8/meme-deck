# gemini.py
# check 14 (X read) on the free Gemini API with Google Search grounding.
# the ONLY file that reads GEMINI_API_KEY. never prints or logs it. one call per token.
import json, os, time
import requests
from config import GEMINI_MODEL, GEMINI_TEMPERATURE
from prompts import JUDGE_PROMPT, JUDGE_PROMPT_POSTS

URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"

class RateLimited(Exception): pass
class JudgeError(Exception): pass

def _key() -> str:
    k = os.environ.get("GEMINI_API_KEY")
    if not k: raise JudgeError("gemini: GEMINI_API_KEY not set in this process")
    return k

def ask(payload: dict, search: bool = True) -> dict:
    """search=True: Gemini + google_search grounding (429 on this free key). search=False: judge only the posts in payload["x_posts"]."""
    body = {"systemInstruction": {"parts": [{"text": JUDGE_PROMPT if search else JUDGE_PROMPT_POSTS}]},
            "contents": [{"role": "user", "parts": [{"text": json.dumps(payload, default=str)}]}],
            "generationConfig": {"temperature": GEMINI_TEMPERATURE}}
    if search: body["tools"] = [{"google_search": {}}]
    try:
        r = requests.post(URL.format(m=GEMINI_MODEL), json=body, timeout=120,
                          headers={"x-goog-api-key": _key(), "Content-Type": "application/json"})
    except requests.RequestException as e:
        raise JudgeError(f"gemini: network error {type(e).__name__}")
    if r.status_code == 429: raise RateLimited("judge rate limited (Gemini 429 quota)")
    if r.status_code != 200:
        try: msg = r.json().get("error", {}).get("message", "")[:120]
        except Exception: msg = ""
        raise JudgeError(f"gemini: HTTP {r.status_code} {msg}")
    d = r.json()
    cand = (d.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []) if not p.get("thought"))
    s, e = text.find("{"), text.rfind("}")
    if s == -1: raise JudgeError(f"gemini: no JSON in answer ({cand.get('finishReason')})")
    try: ans = json.loads(text[s:e + 1])
    except json.JSONDecodeError: raise JudgeError("gemini: unparseable JSON")
    g = cand.get("groundingMetadata") or {}
    srcs = [(c.get("web") or {}) for c in g.get("groundingChunks") or []]
    ans["_grounding"] = {"queries": g.get("webSearchQueries") or [], "sources": [s.get("title") for s in srcs][:10],
                         "x_sources": sum(1 for s in srcs if any(h in str(s.get("title", "")) + str(s.get("uri", "")) for h in ("x.com", "twitter.com")))}
    return ans


def ask_posts(payload: dict, posts_doc: dict) -> dict:
    """no-search mode. posts_doc = x_posts/<mint>.json: {"mint","symbol","fetched_at","queries":[...],"posts":[{text,author_username,
    author_created_at,followers,created_at,url}, ...]}. returns the judge JSON (+ _grounding describing the supplied posts)."""
    keep = ("text", "author_username", "author_created_at", "followers", "created_at", "url")
    posts = [{k: p.get(k) for k in keep} for p in (posts_doc.get("posts") or [])][:60]
    a = ask({**payload, "x_posts": {"queries": posts_doc.get("queries") or [], "fetched_at": posts_doc.get("fetched_at"),
                                    "count": len(posts), "posts": posts}}, search=False)
    a["_grounding"] = {"mode": "operator_posts", "queries": posts_doc.get("queries") or [], "posts": len(posts)}
    return a
