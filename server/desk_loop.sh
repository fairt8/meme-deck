#!/bin/bash
# desk_loop.sh - Oracle server scheduler (systemd desk-loop.service, User=memedesk, TZ=Africa/Lagos).
# same cycle as loop.sh / actions_run.py: every 10 min watch; scan every SCAN_EVERY_MIN (30); Apify X fetch + judge_x;
# dashboard; publish to meme-deck main (Pages); evening report once a day at/after REPORT_AT_HHMM (21:30 WAT).
# actions_run.py does one cycle (its bot_listener --once step is off here: DESK_TG_COMMANDS is unset; desk-bot.service polls live).
# output goes to stdout -> journald (namespace memedesk, capped). secrets come from .env via systemd, never printed.
cd /home/memedesk/desk || exit 1
PY=/home/memedesk/venv/bin/python
while true; do
  start=$(date +%s)
  echo "cycle start $(date '+%F %H:%M:%S %Z')"
  flock .cycle.lock $PY actions_run.py 2>&1 | sed 's/^/  /'
  if [ "${DESK_NO_PUBLISH:-0}" != "1" ]; then ./server/publish_pages.sh; else echo "  publish skipped (DESK_NO_PUBLISH=1)"; fi
  date +%s > loop.heartbeat
  took=$(( $(date +%s) - start )); echo "cycle done in ${took}s"
  sleep $(( took < 600 ? 600 - took : 30 ))
done
