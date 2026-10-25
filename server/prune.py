# prune.py - retention + disk guard for the Oracle desk (desk-prune.timer daily 03:15 WAT; desk-guard.timer hourly with --guard).
# keeps forever: trades.csv, equity.csv, positions.json. prunes:
#   x_posts/*.json older than 3 days | checks.csv rows older than 30 days -> archive/checks-YYYY-MM.csv.gz (archives kept 3 months)
#   rotated logs (*.log.N.gz from logrotate) older than 7 days; notify.log/bot.log/actions.log lines older than 7 days | pip cache
# guard: desk folder > 500 MB or / > 85% used -> prune harder (x_posts 12 h, checks 7 days, archives 1 month, logs 2 days)
#        and send ONE Telegram warning per day (respects DESK_NO_TG=1). never prints secrets.
import csv, datetime as dt, glob, gzip, io, os, re, shutil, subprocess, sys, time
DESK = "/home/memedesk/desk"; os.chdir(DESK); sys.path.insert(0, DESK)
import deskstate
DESK_MAX_MB = 500; DISK_MAX_PCT = 85
NORMAL = dict(xposts_h=72, checks_d=30, archive_months=3, logs_d=7)
HARD = dict(xposts_h=12, checks_d=7, archive_months=1, logs_d=2)

def du_mb(p):
    tot = 0
    for root, _, files in os.walk(p):
        for f in files:
            try: tot += os.lstat(os.path.join(root, f)).st_size
            except OSError: pass
    return tot / 1e6

def disk_pct():
    u = shutil.disk_usage("/"); return 100 * u.used / u.total

def prune(r, tag):
    now = time.time(); out = []
    n = 0
    for f in glob.glob("x_posts/*.json"):
        if now - os.path.getmtime(f) > r["xposts_h"] * 3600: os.remove(f); n += 1
    out.append(f"x_posts -{n}")
    # checks.csv -> monthly gz archives
    if os.path.exists("checks.csv"):
        cut = (dt.datetime.now() - dt.timedelta(days=r["checks_d"])).strftime("%Y-%m-%d %H:%M:%S")
        with open("checks.csv", newline="") as fh: rows = list(csv.reader(fh))
        if rows:
            head, body = rows[0], rows[1:]
            old = [x for x in body if x and x[0] < cut]; keep = [x for x in body if not (x and x[0] < cut)]
            if old:
                os.makedirs("archive", exist_ok=True)
                by = {}
                for x in old: by.setdefault(x[0][:7], []).append(x)
                for ym, xs in by.items():
                    p = f"archive/checks-{ym}.csv.gz"; new = not os.path.exists(p)
                    buf = io.StringIO(); w = csv.writer(buf)
                    if new: w.writerow(head)
                    w.writerows(xs)
                    with gzip.open(p, "at", newline="") as g: g.write(buf.getvalue())
                tmp = "checks.csv.tmp"
                with open(tmp, "w", newline="") as fh: w = csv.writer(fh); w.writerow(head); w.writerows(keep)
                os.replace(tmp, "checks.csv")
            out.append(f"checks archived {len(old)} kept {len(keep)}")
    # archives: keep the newest N months
    first = dt.date.today().replace(day=1); y, m = first.year, first.month - r["archive_months"]
    while m <= 0: m += 12; y -= 1
    oldest = f"{y:04d}-{m:02d}"; n = 0
    for p in glob.glob("archive/checks-*.csv.gz"):
        ym = re.search(r"checks-(\d{4}-\d{2})", p)
        if ym and ym.group(1) < oldest: os.remove(p); n += 1
    out.append(f"archives -{n}")
    # logs: rotated files + lines older than logs_d
    n = 0
    for p in glob.glob("*.log.*"):
        if now - os.path.getmtime(p) > r["logs_d"] * 86400: os.remove(p); n += 1
    cut = (dt.datetime.now() - dt.timedelta(days=r["logs_d"])).strftime("%Y-%m-%d")
    for p in ("notify.log", "bot.log"):
        if os.path.exists(p):
            ls = open(p, errors="replace").readlines()
            ks = [l for l in ls if not (re.match(r"\d{4}-\d{2}-\d{2}", l) and l[:10] < cut)]
            if len(ks) != len(ls): open(p, "w").writelines(ks)
    if os.path.exists("actions.log"):
        ls = open("actions.log", errors="replace").readlines()
        if len(ls) > 2000: open("actions.log", "w").writelines(ls[-2000:])
    out.append(f"rotated logs -{n}")
    shutil.rmtree(os.path.expanduser("~/.cache/pip"), ignore_errors=True)
    for g in ("/home/memedesk/pages", "/home/memedesk/statebr"):
        if os.path.isdir(g + "/.git"): subprocess.run(["git", "-C", g, "gc", "-q", "--prune=now"], capture_output=True)
    print(f"prune[{tag}]: " + ", ".join(out))

def guard():
    mb, pct = du_mb(DESK), disk_pct()
    print(f"guard: desk {mb:.1f} MB (limit {DESK_MAX_MB}), / {pct:.1f}% used (limit {DISK_MAX_PCT}%)")
    if mb <= DESK_MAX_MB and pct <= DISK_MAX_PCT: return
    prune(HARD, "hard")
    mb2, pct2 = du_mb(DESK), disk_pct()
    st = deskstate.load(); today = time.strftime("%Y-%m-%d")
    if st.get("guard_warn_date") != today:
        import notify
        notify.send(f"⚠️ RUG DESK disk guard (Oracle server): desk folder {mb:.0f} MB (limit {DESK_MAX_MB}), "
                    f"root disk {pct:.0f}% (limit {DISK_MAX_PCT}%). Pruned harder -> now {mb2:.0f} MB, {pct2:.0f}%. "
                    "trades.csv and equity.csv kept.")
        st = deskstate.load(); st["guard_warn_date"] = today; deskstate.save(st)

if __name__ == "__main__":
    if "--guard" not in sys.argv: prune(NORMAL, "daily")
    guard()
