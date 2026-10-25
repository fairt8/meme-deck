#!/bin/bash
# publish_pages.sh - copy web/ into a clone of meme-deck main and push (no force). main's .github/ is never touched,
# so .github/workflows/desk.yml (cron commented out = Actions fallback only) survives every publish. token never printed.
D=/home/memedesk/desk; P=/home/memedesk/pages
[ -z "$GH_DESK_TOKEN" ] && { echo "  publish: no GH_DESK_TOKEN"; exit 0; }
URL="https://x-access-token:${GH_DESK_TOKEN}@github.com/fairt8/meme-deck.git"
if [ ! -d "$P/.git" ]; then
  git -c credential.helper= clone -q --depth 1 -b main "$URL" "$P" >/dev/null 2>&1 || { echo "  publish: clone failed"; exit 0; }
  git -C "$P" remote set-url origin https://github.com/fairt8/meme-deck.git
  git -C "$P" config user.name "MEME TRADER"; git -C "$P" config user.email "desk@localhost"
fi
git -C "$P" -c credential.helper= fetch -q --depth 1 "$URL" main >/dev/null 2>&1 && git -C "$P" reset -q --hard FETCH_HEAD
rsync -a --delete --exclude .git --exclude .github "$D/web/" "$P/"
touch "$P/.nojekyll"
git -C "$P" add -A
if git -C "$P" commit -qm "desk update $(date '+%F %H:%M') (oracle)" >/dev/null 2>&1; then
  git -C "$P" -c credential.helper= push -q "$URL" HEAD:main >/dev/null 2>&1 && echo "  publish: pushed" || echo "  publish: push failed"
  git -C "$P" reflog expire --expire=now --all; git -C "$P" gc -q --prune=now 2>/dev/null   # shallow clone stays small
else echo "  publish: no change"; fi
