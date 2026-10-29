#!/bin/bash
# backup_state.sh - nightly push of the desk state files to branch `state` (desk-backup.timer, 02:45 WAT).
# also what the Actions fallback restores from. one commit per night; history squashed weekly-ish to stay small.
D=/home/memedesk/desk; S=/home/memedesk/statebr
[ -z "$GH_DESK_TOKEN" ] && { echo "backup: no GH_DESK_TOKEN"; exit 1; }
URL="https://x-access-token:${GH_DESK_TOKEN}@github.com/fairt8/meme-deck.git"
if [ ! -d "$S/.git" ]; then
  git -c credential.helper= clone -q --depth 1 -b state "$URL" "$S" >/dev/null 2>&1 || { echo "backup: clone failed"; exit 1; }
  git -C "$S" remote set-url origin https://github.com/fairt8/meme-deck.git
  git -C "$S" config user.name "MEME TRADER"; git -C "$S" config user.email "desk@localhost"
fi
git -C "$S" -c credential.helper= fetch -q --depth 1 "$URL" state >/dev/null 2>&1 && git -C "$S" reset -q --hard FETCH_HEAD
for f in positions.json trades.csv checks.csv equity.csv pending_x_review.jsonl pending_symbols.txt desk_state.json insightx_state.json tg_offset.json notify.log actions.log; do
  [ -f "$D/$f" ] && cp "$D/$f" "$S/$f"
done
rsync -a --delete "$D/x_posts/" "$S/x_posts/" 2>/dev/null
git -C "$S" add -A
if git -C "$S" commit -qm "state $(date '+%F %H:%M') WAT (oracle nightly backup)" >/dev/null 2>&1; then
  git -C "$S" -c credential.helper= push -q "$URL" HEAD:state >/dev/null 2>&1 && echo "backup: pushed" || { echo "backup: push failed"; exit 1; }
else echo "backup: no change"; fi
git -C "$S" gc -q --prune=now 2>/dev/null
