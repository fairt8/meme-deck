# bot_listener.py - Telegram long-poll listener for the desk (@MemesTradersBot).
# answers ONLY the chat id in .tg_chat; everyone else is ignored. never prints the token. read-only on the desk:
# /check runs check.py --readonly (no paper position, nothing logged). never edits config.py.
import json, os, subprocess, sys, time, traceback
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import requests

# dashboard base: .pages_url (written by server/cf_pages_deploy.py) > env DESK_DASH_URL > old GitHub Pages
DASH_URL = ((open(".pages_url").read().strip() if os.path.exists(".pages_url") else "") or os.environ.get("DESK_DASH_URL", "")
            or "https://fairt8.github.io/meme-deck").rstrip("/")
APP_URL = DASH_URL + "/app/"
TOK = os.environ.get("MEME_TG_TOKEN", "")
CHAT = (open(".tg_chat").read().strip() if os.path.exists(".tg_chat") else "") or os.environ.get("TG_CHAT_ID", "").strip()
API = f"https://api.telegram.org/bot{TOK}/"

def log(msg):
    with open("bot.log", "a") as f: f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")

def call(method, **params):
    try:
        r = requests.post(API + method, json=params, timeout=params.get("timeout", 0) + 20)
        j = r.json()
        if not j.get("ok"): log(f"{method} failed: {str(j)[:200]}")
        return j
    except Exception as e:
        log(f"{method} error: {type(e).__name__}"); return {}

def app_button(text="Open RUG DESK"):
    return {"inline_keyboard": [[{"text": text, "web_app": {"url": APP_URL}}]]}

def say(text, markup=None):
    for i in range(0, max(len(text), 1), 4000):
        p = {"chat_id": CHAT, "text": text[i:i+4000], "disable_web_page_preview": True}
        if markup and i + 4000 >= len(text): p["reply_markup"] = markup
        call("sendMessage", **p)

def data():
    try: return json.load(open("web/data.json"))
    except Exception: return None

def cmd_status():
    d = data()
    if not d: return "no data.json yet (dashboard.py hasn't run)"
    pnl = d["equity"] - d["start_balance"]
    lines = [f"RUG DESK (PAPER) — updated {d['updated']}",
             f"equity ${d['equity']:.2f} ({pnl:+.2f}, {pnl/d['start_balance']*100:+.1f}%) | cash ${d['cash']:.2f}",
             f"realized ${d['realized_pnl']:+.2f} | wins {d['wins']} / losses {d['losses']} | rugs blocked {d['rugs_blocked']}",
             f"open positions: {len(d['positions'])}"]
    for p in d["positions"]:
        lines.append(f"• {p['symbol']} ${p['usd']} | entry {p['entry']:.6g} now {p['last']:.6g} ({p['pct']:+.1f}%)\n  {p['url']}")
    return "\n".join(lines)

def cmd_report():
    out = subprocess.run([sys.executable, "report.py"], capture_output=True, text=True, timeout=120).stdout
    return "\n".join(l for l in out.splitlines() if not l.startswith("chart:")).strip() or "report empty"

def cmd_kills():
    d = data()
    if not d: return "no data.json yet"
    top = ", ".join(f"{r} {n}x" for r, n in d["top_kills"][:6])
    rows = [f"• {k['time'][5:16]} {k['symbol'] or k['mint'][:6]} — {k['stage']}: {k['reason']}" for k in d["kills"][:12]]
    return f"rugs blocked {d['rugs_blocked']}, pool kills {d['pool_kills']}\ntop: {top}\n\nrecent:\n" + "\n".join(rows)

def cmd_check(ca):
    if not ca or not (32 <= len(ca) <= 44) or not ca.isalnum():
        return "usage: /check <Solana token address>"
    try:
        out = subprocess.run([sys.executable, "check.py", ca, "--readonly", "--x"], capture_output=True, text=True, timeout=240).stdout
        v = json.loads(out)
    except Exception as e:
        return f"check failed: {type(e).__name__} (a source may be down) — skipped"
    lines = [f"READ-ONLY CHECK {v.get('symbol') or ca[:6]}", f"verdict: {v['verdict']} at stage {v['stage']}", f"reason: {v.get('reason')}"]
    if v.get("confidence") is not None: lines.append(f"free-signal confidence: {v['confidence']} (needs ≥ 0.7)")
    for k in ("risk_score", "lp_locked_pct", "top10_pct", "dev_pct", "insiders", "liq_usd", "age_min", "price"):
        if v.get(k) is not None: lines.append(f"{k}: {v[k]}")
    if v.get("insightx_note"):   # check 13b (InsightX): bundlers and the largest holder cluster, each must be <= 20%
        lines.append(f"bundler_pct: {v.get('bundler_pct') if v.get('bundler_pct') is not None else 'n/a'}")
        lines.append(f"max_cluster_pct: {v.get('max_cluster_pct') if v.get('max_cluster_pct') is not None else 'n/a'}")
        lines.append(f"check 13b: {v['insightx_note']}")
    if v.get("x_read"): lines.append(f"X read (Gemini, check 14): {v['x_read']}")
    if v.get("main_risk"): lines.append(f"main risk: {v['main_risk']}")
    if v.get("limits_note"): lines.append(f"(desk limits would block a buy right now: {v['limits_note']})")
    if v.get("url"): lines.append(v["url"])
    lines.append("read-only: nothing was bought or logged.")
    return "\n".join(lines)

HELP = ("RUG DESK — paper trading, no real funds.\n/app open the mini app\n/status balance & open positions\n"
        "/report today's report\n/check <CA> read-only 13-check scan\n/kills recent kills")

def handle(msg):
    text = (msg.get("text") or "").strip()
    cmd, _, arg = text.partition(" "); cmd = cmd.split("@")[0].lower()
    if cmd in ("/start", "/app", "/help"): say(HELP, app_button())
    elif cmd == "/status": say(cmd_status(), app_button("Open dashboard"))
    elif cmd == "/report": say(cmd_report())
    elif cmd == "/kills": say(cmd_kills())
    elif cmd == "/check":
        say("checking (read-only)…"); say(cmd_check(arg.strip()))
    elif text.startswith("/"): say("unknown command.\n" + HELP)

def setup():
    call("setMyCommands", commands=[
        {"command": "app", "description": "Open the RUG DESK mini app"},
        {"command": "status", "description": "Paper balance and open positions"},
        {"command": "report", "description": "Today's evening report"},
        {"command": "check", "description": "Read-only 13-check scan: /check <CA>"},
        {"command": "kills", "description": "Recent kills and reasons"}])
    call("setChatMenuButton", chat_id=int(CHAT), menu_button={"type": "web_app", "text": "RUG DESK", "web_app": {"url": APP_URL}})

def main():
    if os.path.exists("bot.disabled"):
        log("not started: bot.disabled present (remove it to enable)"); return
    if not TOK or not CHAT:
        log("not started: MEME_TG_TOKEN or .tg_chat missing"); return
    if os.environ.get("DESK_NO_TG") == "1":   # server dry run: stay idle (no polling, no sends) so systemd does not restart-loop
        log("idle: DESK_NO_TG=1 (test mode), not polling")
        while True: time.sleep(3600)
    call("deleteWebhook")   # long polling needs no webhook set
    setup(); log("listener started")
    try: offset = json.load(open(OFFSET_FILE)).get("offset")   # resume after a restart, never re-answer old commands
    except Exception: offset = None
    while True:
        try:
            j = call("getUpdates", timeout=50, offset=offset, allowed_updates=["message"])
            for u in j.get("result", []):
                offset = u["update_id"] + 1
                m = u.get("message") or {}
                if str((m.get("chat") or {}).get("id")) != CHAT:
                    log(f"ignored update from chat {(m.get('chat') or {}).get('id')}"); continue
                log(f"cmd: {(m.get('text') or '')[:60]}")
                try: handle(m)
                except Exception: log("handler error: " + traceback.format_exc().splitlines()[-1])
            if j.get("result"):
                try: json.dump({"offset": offset}, open(OFFSET_FILE, "w"))
                except Exception: pass
            if not j: time.sleep(5)
            elif not j.get("ok"):
                if j.get("error_code") == 409:
                    log("409 conflict: another process is polling this bot token; backing off 60s")
                time.sleep(60)
        except Exception as e:
            log(f"loop error: {type(e).__name__}"); time.sleep(5)

OFFSET_FILE = "tg_offset.json"   # Actions --once mode: last processed update id (kept in the state branch)

def once():
    """GitHub Actions mode: process pending commands once, no long poll. never run while the box listener is polling (409)."""
    if os.environ.get("DESK_TG_COMMANDS") != "1":
        print("listener --once: off (DESK_TG_COMMANDS != 1; box listener is primary)"); return
    if os.environ.get("DESK_NO_TG") == "1":
        print("listener --once: off (DESK_NO_TG=1 test mode)"); return
    if not TOK or not CHAT:
        print("listener --once: MEME_TG_TOKEN or TG_CHAT_ID missing"); return
    try: offset = json.load(open(OFFSET_FILE)).get("offset")
    except Exception: offset = None
    if offset is None: call("deleteWebhook"); setup()
    j = call("getUpdates", timeout=0, offset=offset, allowed_updates=["message"])
    if not j.get("ok"):
        print(f"listener --once: getUpdates failed (error {j.get('error_code')})"); return
    n = 0
    for u in j.get("result", []):
        offset = u["update_id"] + 1
        m = u.get("message") or {}
        if str((m.get("chat") or {}).get("id")) != CHAT:
            log(f"ignored update from chat {(m.get('chat') or {}).get('id')}"); continue
        log(f"cmd (once): {(m.get('text') or '')[:60]}"); n += 1
        try: handle(m)
        except Exception: log("handler error: " + traceback.format_exc().splitlines()[-1])
    if offset is not None:
        call("getUpdates", timeout=0, offset=offset)    # confirm the processed updates with Telegram
        json.dump({"offset": offset}, open(OFFSET_FILE, "w"))
    print(f"listener --once: {n} command(s) answered")

if __name__ == "__main__":
    once() if "--once" in sys.argv else main()
