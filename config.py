# config.py
# every number on the desk lives here. when you retune, you edit this file and nothing else.
# THE BOT READS config.py, IT NEVER WRITES IT. a filter is loosened in writing, by you, never by the bot.
PAPER = True                    # week one: fake fills at the live price. the desk never holds a key.
START_BALANCE = 100.0           # paper bankroll. raised from 49 on 2026-10-18 12:20 WAT (user accepted; see CHANGELOG.md)

TICKET_USD = 10                 # flat. never sized up. (article used 25; user chose 10 on 2026-10-18)
MAX_OPEN = 4                    # 4 x $10 = $40 in the market at most (kept at 4 per user)
MAX_ENTRIES_PER_DAY = 6
DAILY_LOSS_HALT_USD = 50        # realized loss today at or below -$50: no new entries
COOLDOWN_HOURS = 24             # no re-entry into a mint closed in the last 24h

FACTS = {                       # the rug filter. code kills, no opinions.
    "max_risk_score": 40,       # rugcheck score_normalised (0-100)
    "min_lp_locked_pct": 90,    # biggest pool: LP locked or burned
    "max_top10_pct": 30,        # top 10 holders, pools and lockers excluded
    "max_dev_pct": 5,           # supply still sitting in the creator wallet
    "max_insiders": 0,          # insider-flagged holders (or insider-graph hit)
    "min_liquidity_usd": 30000,
    "max_ticket_share": 0.01,   # your ticket is at most 1% of the pool
    "min_age_min": 30,          # younger than this: too fresh for any report
    "max_age_hours": 72,        # older than this: the move already happened
}

# JUDGE (check 14 replacement): NO paid API. confidence from free signals only;
# the X read itself is left to a human via pending_x_review.jsonl.
MIN_CONFIDENCE = 0.7            # BUY below this becomes SKIP
# check 14 (X read) via free Gemini + Google Search grounding. added 2026-10-18 at the user's request.
# gemini-2.5-flash returns 404 "no longer available to new users" for this key, so the alias is used.
GEMINI_MODEL = "gemini-flash-latest"
GEMINI_TEMPERATURE = 0.1
# backup check-14 judge (used only when Gemini errors). added 2026-10-18 at the user's request.
GLM_MODEL = "glm-5.3"
HCNSEC_BASE = "https://api.hcnsec.cn/v1"
WHALE_MIN_SOL = 200             # a 200+ SOL single buy only counts after checks 1-13 passed
EXTRA_SELL_TEST = True          # stricter extra: Jupiter must quote a sell back (honeypot sim)
SELL_TEST_SOL = 0.05
MIN_ROUNDTRIP = 0.75            # buy->sell round trip returning < 75% => cant_sell

# paper fill realism on top of the live DexScreener price
FEE_PCT = 1.0                   # per side: DEX/aggregator + priority fee allowance
SLIPPAGE_PCT = 1.0              # per side minimum; Jupiter price impact is added on entry

EXIT = {
    "stop_pct": -35,                       # hard stop
    "ladder": [(100, 0.50), (200, 0.25)],  # +100%: half goes. +200%: another quarter.
    "trail_pct": 30,                       # after the first take, out when price drops 30% from peak
    "time_stop_hours": 6,                  # six hours without +20%: out
    "time_stop_min_pct": 20,
    "liq_drop_pct": 40,                    # pool liquidity down 40% from entry: out, all of it
}

SCAN_MAX_NEW = 5                # scan.py checks the first 5 fresh mints per run
LOG = "checks.csv"
POSITIONS = "positions.json"
TRADES = "trades.csv"
PENDING_X = "pending_x_review.jsonl"

# ---- GitHub Actions / Apify X fetch (added 2026-10-20 at the user's request; no filter number changed) ----
APIFY_ACTOR = "lance_api~x-tweet-scraper-api"   # pay per result: $0.0003 per tweet on the Apify FREE plan, no start fee
APIFY_RESULTS_PER_QUERY = 10                    # 2 queries per token -> at most 20 tweets (~$0.006) per token
APIFY_MAX_FETCHES_PER_DAY = 20                  # budget guard: ~$0.12/day worst case, inside the $5/month free credit
APIFY_TIMEOUT_S = 180
SCAN_EVERY_MIN = 30                             # Actions runs every 15 min; scan on every other run
REPORT_AT_HHMM = 2130                           # evening report, WAT

# check 13b (added 2026-10-29): InsightX bundlers + holder clusters, only on tokens that passed 1-13, before the X queue.
# KILL if bundlers > 20% of supply or any single cluster > 20% (liquidity_pool / exchange / vesting / locker clusters ignored).
# free plan = 1,000 calls/month; stop at 900 so manual /check calls never hit the hard cap. over budget -> SOURCE DOWN, 13b skipped.
INSIGHTX = {"max_bundler_pct": 20, "max_cluster_pct": 20, "monthly_budget": 900}
