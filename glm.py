# glm.py
# BACKUP check-14 judge: GLM via hcnsec (OpenAI-compatible chat/completions). Gemini stays primary.
# the ONLY file that reads HCNSEN_KEY. never prints or logs it. no search: judges only the supplied X posts.
import json, os, re
import requests
from config import GLM_MODEL, HCNSEC_BASE
from prompts import JUDGE_PROMPT_POSTS

class RateLimited(Exception): pass
class JudgeError(Exception): pass

def _key() -> str:
    k = os.environ.get("HCNSEN_KEY")
    if not k: raise JudgeError("glm: HCNSEN_KEY not set in this process")
    return k

def _parse(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    text = re.sub(r"```(?:json)?", "", text)
    s, e = text.find("{"), text.rfind("}")
    if s == -1 or e <= s: raise JudgeError("glm: no JSON in answer")
    try: a = json.loads(text[s:e + 1])
    except json.JSONDecodeError: raise JudgeError("glm: unparseable JSON")
    if str(a.get("verdict", "")).upper() not in ("BUY", "SKIP"): raise JudgeError("glm: malformed verdict")
    c = a.get("confidence")
    if not isinstance(c, (int, float)) or not 0 <= c <= 1: raise JudgeError("glm: malformed confidence")
    for k in ("why", "x_read", "main_risk"):
        if not isinstance(a.get(k, ""), str): raise JudgeError(f"glm: malformed {k}")
    return a

def ask_posts(payload: dict, posts_doc: dict) -> dict:
    """same input/output shape as gemini.ask_posts."""
    keep = ("text", "author_username", "author_created_at", "followers", "created_at", "url")
    posts = [{k: p.get(k) for k in keep} for p in (posts_doc.get("posts") or [])][:60]
    user = {**payload, "x_posts": {"queries": posts_doc.get("queries") or [], "fetched_at": posts_doc.get("fetched_at"),
                                   "count": len(posts), "posts": posts}}
    body = {"model": GLM_MODEL, "temperature": 0.1,
            "messages": [{"role": "system", "content": JUDGE_PROMPT_POSTS},
                         {"role": "user", "content": json.dumps(user, default=str)}]}
    try:
        r = requests.post(f"{HCNSEC_BASE}/chat/completions", json=body, timeout=300,
                          headers={"Authorization": f"Bearer {_key()}", "Content-Type": "application/json"})
    except requests.RequestException as e:
        raise JudgeError(f"glm: network error {type(e).__name__}")
    if r.status_code == 429: raise RateLimited("glm rate limited (429)")
    if r.status_code != 200: raise JudgeError(f"glm: HTTP {r.status_code}")
    try: msg = r.json()["choices"][0]["message"]
    except Exception: raise JudgeError("glm: malformed response")
    a = _parse(msg.get("content") or "")
    a["_grounding"] = {"mode": "operator_posts", "queries": posts_doc.get("queries") or [], "posts": len(posts)}
    return a
