#!/bin/bash
# pull_state.sh - copy the book from branch `state` into the desk folder (cutover / rollback from Actions).
set -e; cd /home/memedesk; set -a; . desk/.env; set +a
U="https://x-access-token:${GH_DESK_TOKEN}@github.com/fairt8/meme-deck.git"
rm -rf statebr; git -c credential.helper= clone -q --depth 1 -b state "$U" statebr >/dev/null 2>&1 || { echo "state clone failed"; exit 1; }
git -C statebr remote set-url origin https://github.com/fairt8/meme-deck.git
git -C statebr config user.name "MEME TRADER"; git -C statebr config user.email "desk@localhost"
for f in positions.json trades.csv checks.csv equity.csv pending_x_review.jsonl pending_symbols.txt desk_state.json insightx_state.json tg_offset.json notify.log actions.log; do
  [ -f statebr/$f ] && cp statebr/$f desk/$f
done
mkdir -p desk/x_posts; rsync -a --delete statebr/x_posts/ desk/x_posts/
echo "state pulled: $(git -C statebr log -1 --format='%h %cd %s' --date=iso)"
