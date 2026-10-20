# run_cycle.py - one manual cycle: watch open positions, then scan for new leads, then snapshot.
import os, subprocess, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
for script in ("watch.py", "scan.py", "dashboard.py"):
    out = subprocess.run([sys.executable, script], capture_output=True, text=True).stdout.strip()
    if out: print(out)
