#!/bin/bash
# Push web/ to github.com/fairt8/meme-deck (GitHub Pages). Token from env, never printed.
cd /workspace/desk/web || exit 0
[ -z "$GH_DESK_TOKEN" ] && { echo "publish: no GH_DESK_TOKEN" >> ../loop.log; exit 0; }
touch .nojekyll
if [ ! -d .git ]; then git init -q -b main && git config user.name "MEME TRADER" && git config user.email "desk@localhost"; fi
git add -A && git commit -qm "desk update $(date '+%F %H:%M')" >/dev/null 2>&1
git -c credential.helper= push -q -f "https://x-access-token:${GH_DESK_TOKEN}@github.com/fairt8/meme-deck.git" main >/dev/null 2>&1 || echo "publish: push failed $(date)" >> ../loop.log
