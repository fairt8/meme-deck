#!/bin/bash
# seed_state.sh [branch] - push the box's CURRENT desk state to the `state` branch of fairt8/meme-deck.
# run it at cutover, right after stopping the box loop, so Actions continues from the exact same book.
# needs env GH_DESK_TOKEN (contents write). token never printed.
set -e
BR=${1:-state}
SRC=/workspace/desk; W=$(mktemp -d)
cd "$W" && git init -q -b "$BR" && git config user.name "MEME TRADER" && git config user.email "desk@localhost"
for f in positions.json trades.csv checks.csv equity.csv pending_x_review.jsonl pending_symbols.txt notify.log; do
  [ -f "$SRC/$f" ] && cp "$SRC/$f" .
done
mkdir -p x_posts && cp -r "$SRC"/x_posts/. x_posts/ 2>/dev/null || true
python3 - <<'PY'
import json, time
st = {"runs": 0, "last_scan_ts": 0, "seeded_from_box": time.strftime("%Y-%m-%d %H:%M:%S")}
if int(time.strftime("%H%M")) >= 2130: st["last_report_date"] = time.strftime("%Y-%m-%d")   # box already sent today's report
json.dump(st, open("desk_state.json", "w"), indent=1)
PY
printf '# desk state (written by the desk each run). paper only. no secrets here.\n' > README.md
git add -A && git commit -qm "state seeded from box $(date '+%F %H:%M') WAT"
git -c credential.helper= push -q -f "https://x-access-token:${GH_DESK_TOKEN}@github.com/fairt8/meme-deck.git" "$BR:$BR"
echo "state pushed to branch $BR"; rm -rf "$W"
