# notify.py - Telegram push via sendMessage ONLY (no getUpdates, no webhooks).
# token comes from env MEME_TG_TOKEN (never printed or logged); chat id from .tg_chat, else env TG_CHAT_ID (GitHub Actions).
# DESK_NO_TG=1 disables every send (Actions test mode).
# if anything is missing or fails, log to notify.log and carry on - the desk never crashes on a notification.
import os, sys, time
import requests
BASE = os.path.dirname(os.path.abspath(__file__))

def _log(msg):
    with open(os.path.join(BASE, "notify.log"), "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")

def send(text: str) -> bool:
    try:
        if os.environ.get("DESK_NO_TG") == "1":
            _log(f"skipped (DESK_NO_TG=1, test mode): {text[:80]!r}"); return False
        tok = os.environ.get("MEME_TG_TOKEN")
        if not tok: _log("skipped: MEME_TG_TOKEN not set"); return False
        p = os.path.join(BASE, ".tg_chat")
        chat = (open(p).read().strip() if os.path.exists(p) else "") or os.environ.get("TG_CHAT_ID", "").strip()
        if not chat: _log("skipped: no chat id in .tg_chat or TG_CHAT_ID"); return False
        ok = True
        for i in range(0, max(len(text), 1), 4000):   # Telegram limit 4096 chars
            r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                              json={"chat_id": chat, "text": text[i:i+4000], "disable_web_page_preview": True}, timeout=15)
            if r.status_code != 200:
                ok = False; _log(f"send failed: HTTP {r.status_code} {r.text[:150]}")
        if ok: _log(f"sent {len(text)} chars")
        return ok
    except Exception as e:
        _log(f"send error: {type(e).__name__}"); return False

if __name__ == "__main__":
    print("sent" if send(" ".join(sys.argv[1:]) or sys.stdin.read()) else "not sent (see notify.log)")
