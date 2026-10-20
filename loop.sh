#!/bin/bash
# Desk scheduler: watch+dashboard every 10 min, scan every 30 min, report 21:30 Lagos.
cd /workspace/desk
last_report=""
i=0
while true; do
  # keep the Telegram listener alive (restart if dead)
  pgrep -f "python3 bot_listener.py" >/dev/null || setsid nohup python3 bot_listener.py >> bot.log 2>&1 < /dev/null &
  python3 watch.py >> loop.log 2>&1
  if [ $((i % 3)) -eq 0 ]; then python3 scan.py >> loop.log 2>&1; fi
  python3 judge_x.py >> loop.log 2>&1   # check 14 for queued tokens that have x_posts/<mint>.json
  python3 dashboard.py >> loop.log 2>&1
  ./publish.sh
  now=$(date +%H%M); today=$(date +%F)
  if [ "$now" -ge 2130 ] && [ "$last_report" != "$today" ]; then
    python3 report.py --send >> loop.log 2>&1; last_report=$today
  fi
  date +%s > loop.heartbeat
  i=$((i+1)); sleep 600
done
