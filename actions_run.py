# actions_run.py - ONE desk cycle for GitHub Actions (replaces loop.sh there; loop.sh stays the box scheduler).
# order: telegram commands (if DESK_TG_COMMANDS=1) -> watch -> scan (every SCAN_EVERY_MIN) -> Apify X fetch -> judge_x
#        -> dashboard -> evening report once a day at REPORT_AT_HHMM WAT. times follow TZ (the workflow sets Africa/Lagos).
# state lives in files; the workflow restores them from the `state` branch before and commits them after.
import os, subprocess, sys, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from config import SCAN_EVERY_MIN, REPORT_AT_HHMM
import deskstate

def run(*args, timeout=900):
    t = time.time()
    try:
        p = subprocess.run([sys.executable, *args], capture_output=True, text=True, timeout=timeout)
        out = (p.stdout + ("\n" + p.stderr.strip().splitlines()[-1] if p.returncode and p.stderr.strip() else "")).strip()
        rc = p.returncode
    except subprocess.TimeoutExpired:
        out, rc = "TIMEOUT", -1
    line = f"[{time.strftime('%H:%M:%S')}] {' '.join(args)} rc={rc} {time.time()-t:.0f}s"
    print(line + ("\n  " + out.replace("\n", "\n  ") if out else ""), flush=True)
    with open("actions.log", "a") as f: f.write(line + (" | " + out.replace("\n", " | ")[:500] if out else "") + "\n")
    return rc

def main():
    st = deskstate.load(); now = time.time()
    st["runs"] = st.get("runs", 0) + 1; deskstate.save(st)
    run("bot_listener.py", "--once", timeout=300)
    run("watch.py")
    force = os.environ.get("DESK_FORCE_SCAN") == "1"
    if force or now - st.get("last_scan_ts", 0) >= SCAN_EVERY_MIN * 60 - 120:
        run("scan.py", timeout=1500); st = deskstate.load(); st["last_scan_ts"] = int(now); deskstate.save(st)
    run("x_fetch_apify.py", timeout=1200)
    run("judge_x.py", timeout=1500)
    run("dashboard.py")
    today = time.strftime("%Y-%m-%d")
    st = deskstate.load()
    if int(time.strftime("%H%M")) >= REPORT_AT_HHMM and st.get("last_report_date") != today:
        run("report.py", "--send"); st["last_report_date"] = today; deskstate.save(st)
    # keep the log small in git
    if os.path.exists("actions.log"):
        lines = open("actions.log").readlines()[-2000:]; open("actions.log", "w").writelines(lines)
    st = deskstate.load(); st["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S"); deskstate.save(st)

if __name__ == "__main__":
    main()
