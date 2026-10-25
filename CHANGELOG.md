# RUG DESK changelog (paper)
- 2026-10-18 12:05 WAT: desk built; START_BALANCE=49, TICKET_USD=25 (article). One paper buy: CATSZN $25 at 12:06.
- 2026-10-18 ~12:20 WAT: user changed START_BALANCE 49 -> 100 and TICKET_USD 25 -> 10. Treated as a **$51 paper capital top-up**:
  trades.csv history is untouched; cash is always recomputed as START_BALANCE - tickets + proceeds, so cash went $24 -> $75.
  equity.csv rows before this time were computed on the $49 base (the chart shows a +$51 step there; it is the top-up, not profit).
  The open CATSZN position keeps its original $25 size (legacy); all new entries use the $10 flat ticket. MAX_OPEN stays 4.
- scan.py dedupe: tokens whose only rows in checks.csv are LIMITS-stage skips (cash/slots/cooldown) are re-checked; real verdicts are not.
- notify.py (Telegram sendMessage only) and dashboard.py (static web/index.html) added; run_cycle.py now runs watch -> scan -> dashboard.
- 2026-10-18 ~19:25 WAT: check 14 judges operator-supplied X posts (x_posts/<mint>.json) via judge_x.py; Gemini without search is primary.
  Added GLM backup judge (glm.py, hcnsec OpenAI-compatible API, key env HCNSEN_KEY): used only when Gemini errors (429/5xx/timeout/bad JSON).
  config.py: new constants GLM_MODEL="glm-5.3", HCNSEC_BASE="https://api.hcnsec.cn/v1" (user-requested). No filter numbers changed.
  checks.csv gains a judge_model column; Telegram BUY alerts name the judge used. If both judges fail the token stays queued.
- 2026-10-20 ~19:00 WAT: GitHub Actions build (user asked to make the desk independent of Grok Bot). Box loop stays PRIMARY; nothing cut over.
  New: actions_run.py (one cycle: listener --once, watch, scan every SCAN_EVERY_MIN, Apify X fetch, judge_x, dashboard, report once/day >= 21:30 WAT),
  x_fetch_apify.py (Apify actor lance_api~x-tweet-scraper-api, $0.0003/tweet, 2 queries x 10 results, max 20 fetches/day; env APIFY_TOKEN),
  deskstate.py (desk_state.json: runs, last_scan_ts, last_report_date, Apify day budget), seed_state.sh (box state -> `state` branch).
  config.py: NEW constants only (APIFY_*, SCAN_EVERY_MIN=30, REPORT_AT_HHMM=2130). No filter number changed.
  notify.py: DESK_NO_TG=1 disables sends (test mode); chat id falls back to env TG_CHAT_ID. bot_listener.py: `--once` mode for Actions,
  gated by DESK_TG_COMMANDS=1 (off until cutover, so no 409 with the box listener); offset kept in tg_offset.json.
  GLM backup re-tested 2026-10-20 with fictional spam: glm-5.3 -> SKIP 0.92 (coordinated bot wave), ~229 s per call.
  Repo layout fairt8/meme-deck: `main` = Pages (+ .github/workflows/desk.yml), `desk` = code, `state` = desk state. Workflow is dispatch-only; cron commented.
  GH_DESK_TOKEN lacks Workflows/Actions-write/Secrets permissions: the workflow file could not be pushed, so it sits in the `desk`
  branch at actions/desk.yml (and /workspace/desk/gh/desk.yml). No workflow exists on GitHub yet; no Actions run happened.
  `state` branch seeded from the box at 18:50 WAT (re-seed with seed_state.sh at cutover). Local simulation of one test-mode cycle: all steps rc=0.
- 2026-10-20 19:27 WAT: CUTOVER to GitHub Actions. Token got Workflows/Actions/Secrets. Secrets set (MEME_TG_TOKEN, TG_CHAT_ID, GEMINI_API_KEY,
  HCNSEN_KEY, APIFY_TOKEN). Workflow lives on main at .github/workflows/desk.yml (box copy web/.github/workflows/desk.yml). Test run 39474673487 green,
  live run 39474908729 green (state + Pages committed). Box loop.sh and bot_listener.py stopped, bot.disabled created; cron */15 and DESK_TG_COMMANDS=1 enabled.
  Rollback: disable the workflow (or comment the cron), rm bot.disabled, `bash -lc 'cd /workspace/desk && setsid nohup ./loop.sh >> loop.log 2>&1 < /dev/null &'`
  after copying the latest state branch files back into /workspace/desk.

## 2026-10-25 01:13 WAT: desk moved from GitHub Actions to the Oracle server (152.67.154.102)
- Found at the start: the Actions `schedule` never fired after the 10-20 cutover (0 scheduled runs; the book was last updated 2026-10-20 19:28 WAT), and since 10-20 GitHub Pages hasn't built and the account/repo/Pages return 404 to anonymous visitors (authenticated API works). So no trades were lost, but the desk sat idle for about 4.5 days.
- Server: Linux user `memedesk` (no sudo, home 750). SSH: `ssh -i ~/.ssh/oracle_desk memedesk@152.67.154.102`. I installed python3.12-venv. Code is a clone of branch `desk` in /home/memedesk/desk; venv is /home/memedesk/venv; secrets are in /home/memedesk/desk/.env (600, memedesk).
- Units (/etc/systemd/system, sources in server/systemd/), all User=memedesk, Nice=10, TZ=Africa/Lagos, ProtectSystem=strict, ProtectHome=tmpfs (only /home/memedesk visible), NoNewPrivileges:
  - desk-loop.service: server/desk_loop.sh, which runs actions_run.py every 10 min and then server/publish_pages.sh. Restart=always, MemoryMax=512M, CPUQuota=50%.
  - desk-bot.service: bot_listener.py live long-poll. Restart=always, MemoryMax=256M. It now resumes from tg_offset.json and idles when DESK_NO_TG=1.
  - desk-prune.timer: daily 03:15. desk-guard.timer: hourly. desk-backup.timer: 02:45 (push state files to branch `state`).
  - Optional /home/memedesk/desk/mode.env: DESK_NO_TG=1 / DESK_NO_PUBLISH=1 for test mode.
- Logs: service stdout goes to journal namespace `memedesk` (/etc/systemd/journald@memedesk.conf: 50M max, 7 days). Read it with `sudo journalctl --namespace=memedesk -u desk-loop`. File logs use /etc/logrotate.d/memedesk (daily, rotate 7, compress, copytruncate).
- Retention (server/prune.py):
  - x_posts older than 3 days are deleted.
  - checks.csv rows older than 30 days move to archive/checks-YYYY-MM.csv.gz; archives are kept 3 months.
  - notify.log/bot.log lines are kept 7 days; actions.log keeps 2000 lines; the pip cache is cleared.
  - Guard: if the desk folder is over 500 MB or / is over 85% used, prune harder (12 h / 7 days / 1 month / 2 days) and send one Telegram warning a day.
  - trades.csv, equity.csv and positions.json are never pruned.
- Publishing: publish_pages.sh copies web/ into a clone of main, excluding .git and .github, and pushes without force. So main's .github/workflows/desk.yml is kept.
- main + actions/desk.yml: the `schedule` cron is commented out; workflow_dispatch stays as the emergency fallback.
- Cutover: dry run with DESK_NO_TG=1 and no publish (clean cycle 01:09 WAT). At 01:13 WAT I stopped the units, re-pulled the book from `state` (462a5f4), turned Telegram on and started them. I sent one Telegram announcement at 01:15. The box loop stays stopped (bot.disabled).
- Rollback to Actions:
  1. As ubuntu: `sudo systemctl disable --now desk-loop desk-bot desk-prune.timer desk-guard.timer desk-backup.timer`.
  2. As memedesk: `~/desk/server/backup_state.sh` (pushes the latest book to `state`).
  3. On main, uncomment the 2 `schedule`/`cron` lines in .github/workflows/desk.yml (and in actions/desk.yml here). Note the schedule never fired on 10-20, so check that GitHub Actions actually runs for the account, or use workflow_dispatch mode=live.
  4. Never run the server bot and an Actions/box listener together (Telegram 409).


## 2026-10-25 01:40 WAT: Cloudflare Pages publisher prepared (waiting for a token)
- GitHub Pages has been dead for the fairt8 account since 10-20, so the dashboard and mini app move to Cloudflare Pages (account f6420e67…, project `meme-deck`, which will be https://meme-deck.pages.dev unless Cloudflare assigns a suffix).
- server/cf_pages_deploy.py: a small Python implementation of the Pages direct-upload API (upload-token, check-missing, upload, upsert-hashes, deployment with a manifest; blake3 asset keys, same as wrangler). It creates the project if it's missing and writes the live URL to .pages_url. blake3 is added to requirements.
- server/publish_pages.sh: deploys to Cloudflare when CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID are in .env. The GitHub main push for web/ then runs only with DESK_PUBLISH_GITHUB=1. Without the token it keeps the old GitHub push. The nightly state backup to `state` is unchanged.
- bot_listener.py: the dashboard and mini app URL comes from .pages_url (or env DESK_DASH_URL), with old GitHub Pages as the fallback. The menu button, the /app button and the /status button all use it, and setChatMenuButton runs on every listener start.
- Blocked: the Cloudflare MCP connection is OAuth. It can't create API tokens (403: needs "API Tokens Write") and it can't create Pages projects (needs one more permission and a fresh sign-in). CLOUDFLARE_ACCOUNT_ID and CF_PAGES_PROJECT are in the server .env; CLOUDFLARE_API_TOKEN is not yet.
