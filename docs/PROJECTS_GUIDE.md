# Projects and templates guide

One place for each project: what counts as "complete", where its code lives, and its shareable bot template.
Projects that aren't finished don't get a published template.

*Last updated: 10 Nov 2026, 17:55 WAT. Figures below were read from the live paper book at that time. This guide has no secrets, keys, tokens, chat ids, server addresses or personal details.*

## MEME TRADER (this workstream)

Paper-only Solana memecoin desk. It scans new tokens, runs a 14-check pipeline plus InsightX (check 13b), and books $10 paper tickets from a $100 start. It never buys, sells, signs or moves real funds, and it never connects a wallet.

The workstream is one product with two outputs. The main project is the automated desk. The dashboard plus Telegram mini app, and the Telegram alert bot, are outputs of that desk, not separate products.

**Projects, type and what each produces:**

| Project | Type | Produces |
|---|---|---|
| Paper Solana memecoin desk (MEME Desk) | Automated workflow | 1. Telegram alerts and the evening report (21:30 WAT). 2. The live dashboard and Telegram mini app at [https://meme-deck.pages.dev](https://meme-deck.pages.dev) (mini app at `/app/`). 3. The paper trade book and the kill log. |
| Dashboard and Telegram mini app | Web app (output of the desk) | 1. The card-style dashboard (Home, Positions, Alerts, PnL, More). 2. The same UI as a Telegram mini app at `/app/`. 3. A no-JavaScript tables page at `/static`. |
| Telegram alert bot | App (output of the desk) | 1. Buy, kill and exit alerts. 2. Commands: `/status`, `/report`, `/check`, `/kills`, `/app`. 3. A menu button that opens the mini app. |

### Paper Solana memecoin desk

An unattended loop on a cloud server (systemd): a 10-minute cycle, a long-running Telegram bot, an hourly disk guard, a daily prune, and a nightly backup of the book and logs. The units have memory caps. Working code lives on the `desk` branch of the public repo [fairt8/meme-deck](https://github.com/fairt8/meme-deck). The dashboard is published to Cloudflare Pages each cycle. Nightly state is pushed to the `state` branch.

**Live rules.** Paper only; $100 start, $10 ticket, at most four open positions. Checks 1–13 (Rugcheck, pool size, holder concentration, and the rest), a free judge, check 13b (InsightX: kill if bundlers, or any single non-excluded holder cluster, hold more than 20% of supply), then check 14 (an X read via Apify, judged by Gemini with a GLM backup). Exits: a −35% stop; a take-profit ladder at 3x / 5x / 10x / 20x that sells 25% / 25% / 25% / 15% of the original size, with the last 10% on a 30% trailing stop that arms at +100% (2x) or after any take; a 40% liquidity-drop exit; and a 6-hour / +20% time stop. If a data source fails, the desk logs `SOURCE DOWN` and skips; it never invents numbers.

**Live book, 10 Nov 2026, 17:55 WAT**

| Item | Value |
|---|---|
| Equity / cash | $76.03 (start $100) |
| Realized / unrealized | −$23.97 / $0.00 |
| Open / pending X-review | 0 / 0 |
| Closed trades | 4, all on 18 Oct 2026, all stopped out. 0 wins / 4 losses. No paper trades since 18 Oct. |
| CATSZN (legacy $25 ticket) | −$9.54 (−38.15%) |
| blocus ($10) | −$4.60 (−46.04%) |
| MASSIVE ($10) | −$4.30 (−42.96%) |
| Chaton ($10) | −$5.53 (−55.31%) |
| Win rate / avg return | 0% / −45.62% |
| Expectancy / profit factor | −$5.99 per closed trade / 0.00 |
| Max drawdown | 23.51% ($23.36) |
| Tokens checked | 3,970 total; 191 in the last 24 hours |
| Rugs blocked | 1,852 (pool-stage 1,774; InsightX 13b 32; X-read 34). 190 kills in the last 24 hours. |
| InsightX quota (Nov 2026) | 169 calls used, 831 of the 900 monthly budget left |
| Apify | 0 fetches so far today (cap 20 per day) |
| Sources (last 24 hours) | Rugcheck, DexScreener, Jupiter sell test, InsightX 13b and the X read all had no downtime |
| Runs | 2,408 since 18 Oct 2026, 12:06 WAT. Last scan 17:55 WAT. |

**Complete means all of these:**

- [x] Pipeline checks 1–14 plus 13b InsightX are in the scan path.
- [x] The X judge is Gemini, with GLM as the backup.
- [x] X posts are fetched with Apify (daily cap in place).
- [x] Take-profit ladder 3x / 5x / 10x / 20x with the trailing stop, as above.
- [x] Cloud systemd services with memory caps, prune, disk guard and a nightly backup.
- [x] Cloudflare Pages dashboard and mini app, redesigned in the card style, live at [https://meme-deck.pages.dev](https://meme-deck.pages.dev).
- [x] Telegram alert bot, with the commands listed above.
- [ ] **InsightX-down policy.** Today, if InsightX is over budget, rate-limited, down, or returns an empty snapshot, check 13b is skipped and the token continues to check 14. A decision is still needed: keep skipping only 13b, or skip the whole token until InsightX is back.
- [ ] **GitHub visibility and nightly backups.** The fairt8 GitHub account returned 404 to anonymous visitors from about 20–25 Oct 2026, which put the nightly `state` backups in doubt. Checked on 10 Nov 2026: the account and the public repo are visible again (HTTP 200), and a backup commit has landed on `state` every night since the 25 Oct move, most recently 10 Nov 2026, 02:46 WAT. Keep watching that those pushes still land.
- [ ] **systemd daemon-reload for desk-loop.** This was flagged after a restart on 3 Nov 2026. Checked on 10 Nov 2026, 17:56 WAT: systemd reports that no reload is needed, and the unit file has not changed since 25 Oct. Confirm at the next planned maintenance restart.
- [ ] **Ladder and 13b on a live paper buy.** There have been no paper trades since 18 Oct 2026, which is before 13b and the new ladder were added. Check 13b is working on the scan path — 32 tokens have been killed by it, including during the 17:55 WAT scan on 10 Nov — but no token has passed all the way to a paper entry since those features landed, so the ladder has not been exercised on a live paper position.

**Template:** no template has been published, because the project isn't complete. An unpublished draft is staged, and it gets published only once the to-dos above are closed.

**Repo:** [fairt8/meme-deck](https://github.com/fairt8/meme-deck) (public). Working code is on the `desk` branch. The `main` branch holds a Pages and workflow copy. Nightly book and logs go to the `state` branch. The live dashboard is the public face of the desk; this guide is the operator write-up.

### Dashboard and Telegram mini app

**Type:** web app (output of the desk).

**Produces:** the live card UI at [https://meme-deck.pages.dev](https://meme-deck.pages.dev) and the same page as a Telegram mini app at `/app/`; plus the older tables page at `/static`. Home shows equity, the change versus the $100 start, a sparkline, Realized / Unrealized / Start, and desk stats. Positions shows open trades and the pending X-review, with the 3x / 5x / 10x / 20x ladder bar. Alerts lists kills by stage and reason, including InsightX bundler and cluster figures. PnL lists closed trades, daily P&L and fills. Every number on the page comes from `data.json`; the UI never invents figures.

**Complete means:** both `/` and `/app/` are live and return 200, the redesign is in place, and the page only shows real desk data.

- [x] Cloudflare Pages deploy from the desk cycle; `/`, `/app/` and `/data.json` return 200.
- [x] Card-style redesign (Home, Positions, Alerts, PnL, More), with a light and a dark theme.
- [x] Extra `data.json` fields for the new layout (closed trades, win rate, drawdown, sources, quotas, per-position ladder state).
- [x] Old tables page kept at `/static`.
- [ ] The Positions tab still has nothing to show for a live ladder trade, because no paper position has been opened since 18 Oct 2026.

**Template:** part of "MEME TRADER". Not published on its own.

### Telegram alert bot

**Type:** app (output of the desk).

**Produces:** Telegram alerts when a token is bought, killed or exited on the paper book; the evening report at 21:30 WAT; on-demand `/status`, `/report`, `/check <token>` (a read-only scan, no paper trade) and `/kills`; and a menu button that opens the mini app.

**Complete means:** the bot runs unattended beside the desk loop, alerts and the evening report go out, and the commands above work.

- [x] Runs as its own systemd service, with a memory cap, beside the desk loop.
- [x] Alerts, evening report, `/status`, `/report`, `/check`, `/kills` and the mini-app button.
- [ ] No further bot work is outstanding on its own; it follows the desk to-dos above (the first live paper buy under the new ladder will also be the first new buy or exit alert since 18 Oct).

**Template:** part of "MEME TRADER". Not published on its own.

## Template

No template has been published, because the project isn't complete. An unpublished draft is staged, and it gets published only once the to-dos in this guide are closed.

## Other projects

This workstream is only MEME TRADER. The rows below are the desk and its two outputs.

| Project | Agent | Type | Produces | Complete? | Template |
|---|---|---|---|---|---|
| Paper Solana memecoin desk | MEME TRADER | Automated workflow | Telegram alerts and evening report; live dashboard and mini app; paper trade book and kill log | No (see to-dos above) | Draft, unpublished |
| Dashboard and Telegram mini app | MEME TRADER | Web app (output) | Dashboard and mini app at meme-deck.pages.dev | Almost (waiting on a live ladder trade) | Part of MEME TRADER |
| Telegram alert bot | MEME TRADER | App (output) | Alerts, evening report, commands | Almost (follows the desk) | Part of MEME TRADER |
