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
