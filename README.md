# Digitain AI QA Agent

> An AI-driven QA agent that reads natural-language test cases (in any language) and executes them against TotoGaming.ro via Playwright, with self-healing locators and a clean HTML report.

**Built for the Digitain AI Automation Specialist task.**

---

## TL;DR

```bash
pip install -r requirements.txt
python -m playwright install chromium

export ANTHROPIC_API_KEY=sk-...     # or OPENAI_API_KEY
python -m src.main --xlsx test_cases.xlsx
open reports/report.html
```

That's it. The agent:

1. Reads the assignment Excel directly (no hardcoded test data).
2. For each case, asks the LLM to plan atomic browser actions.
3. Executes them via Playwright using the **accessibility tree** — not brittle CSS selectors.
4. Self-heals when a locator misses: re-snapshots the page, re-asks the LLM.
5. Has the LLM judge actual vs expected, returning `pass | fail | blocked | inconclusive`.
6. Writes `report.html` (human) + `report.json` (CI / Slack / Jira).

---

## Why this design

The brief asked for an AI agent. The interesting question is *which kind*. Three patterns are common in 2026:

| Pattern | Pros | Cons |
| --- | --- | --- |
| **Pure LLM browser-use** (one agent loop, vision-based) | Fewest lines of code | Non-deterministic, expensive, hard to debug |
| **Pure scripted Playwright** (translate every case manually) | Cheapest, fastest | Doesn't scale — 200 partners × 500 tests = 100k scripts to maintain |
| **LLM-planned, Playwright-executed** (this project) | Adapts to UI churn, deterministic execution, cheap to run | Slightly more architecture |

I chose option 3 because Digitain operates ~200+ partner brands on Centrivo. A self-healing pattern is the only one that pays off at that scale: **write the test once in plain language, run against any brand.**

The architecture follows the **Planner / Executor / Judge** pattern that Microsoft's Playwright team standardized in 2026:

```
   Excel test cases (Armenian / EN / RO)
            │
            ▼
   ┌────────────────┐    ┌──────────────────┐
   │   PLANNER      │───▶│  Atomic action   │
   │ (LLM + a11y    │    │      plan        │
   │   snapshot)    │    └────────┬─────────┘
   └────────────────┘             │
            ▲                     ▼
            │   ┌──────────────────────────┐
            │   │   EXECUTOR (Playwright,  │
   self-heal│   │   accessibility-tree     │
            │   │   locators, dry-run      │
            │   │   safety rails)          │
            │   └────────┬─────────────────┘
            │            │ trace + screenshots
            │            ▼
            │   ┌────────────────┐
            └───│   JUDGE (LLM)  │──▶  pass / fail / blocked
                └────────────────┘
                         │
                         ▼
                 HTML + JSON report
```

---

## Configuration

All knobs are CLI flags. No config files to maintain.

```bash
# Default: Claude Sonnet, headless, dry-run safety ON
python -m src.main --xlsx test_cases.xlsx

# Switch to OpenAI
python -m src.main --xlsx test_cases.xlsx --provider openai --model gpt-4o

# Run only Responsible-Gambling tests (auto-tagged)
python -m src.main --xlsx test_cases.xlsx --tag responsible-gambling

# Run a specific subset
python -m src.main --xlsx test_cases.xlsx --ids simple-1,simple-4,complex-7

# Watch the browser (debugging)
python -m src.main --xlsx test_cases.xlsx --headless=false

# Current live smoke/safe subset for TotoGaming.ro
uv run python -m src.main --xlsx test_cases.xlsx --provider openai --model gpt-4o --difficulty simple --headless false
```

| Flag | Purpose |
| --- | --- |
| `--xlsx` | Path to the test case workbook. |
| `--provider` | `claude` or `openai`. |
| `--model` | Override the default model id. |
| `--difficulty` | Filter to `simple` or `complex`. |
| `--tag` | Filter by auto-inferred tag (e.g. `responsible-gambling`, `betting`, `casino`, `auth`). |
| `--ids` | Comma-separated case IDs to run. |
| `--headless` | `true`/`false`. |
| `--allow-money` | **Disables safety rails.** Required to test real deposits or place real bets. |
| `--report-dir` | Where reports + screenshots + Playwright traces are written. |

The CLI also loads a local `.env` file automatically. Test data can be supplied
as environment variables such as `TEST_USERNAME`, `TEST_PASSWORD`, `TEST_CNP`,
`TEST_EMAIL`, `TEST_PHONE`, and `TEST_STAKE`. The LLM planner is instructed to
use placeholders like `${TEST_USERNAME}`; the executor resolves them locally so
secrets are not sent to the model.

If `TEST_USERNAME` and `TEST_PASSWORD` are real player credentials, the agent
blocks account-dependent tests unless `ALLOW_REAL_ACCOUNT_TESTS=true` is set.
Keep that disabled for normal runs. The safe live checks (`simple-1`, `simple-6`,
`simple-7`, `simple-8`) do not need your real login.

For `simple-2`, you can opt in to a safe account precondition check:

```bash
ALLOW_REAL_ACCOUNT_TESTS=true uv run python -m src.main \
  --xlsx test_cases.xlsx \
  --provider openai \
  --model gpt-4o \
  --ids simple-2 \
  --headless false \
  --report-dir reports/simple_2_account_check
```

That mode logs in with `TEST_USERNAME`/`TEST_PASSWORD`, disables trace
screenshots/snapshots for privacy, then stops. It does not activate
self-exclusion and does not open or submit a deposit/payment flow.

If the account is already self-excluded, the agent can verify the actual
expected result and pass the test when deposit access is blocked:

```bash
ALLOW_REAL_ACCOUNT_TESTS=true TEST_ACCOUNT_ALREADY_SELF_EXCLUDED=true \
uv run python -m src.main \
  --xlsx test_cases.xlsx \
  --provider openai \
  --model gpt-4o \
  --ids simple-2 \
  --headless false \
  --report-dir reports/simple_2_self_excluded
```

This still does not activate self-exclusion and does not submit a payment. It
only checks that the already-self-excluded account cannot reach/use deposit.

## Telegram QA Bot

The project also includes a Telegram bot wrapper for running the same QA agent
from a controlled chat interface. It is designed for one admin and two regular
users. Telegram-triggered runs always keep dry-run safety enabled: the bot does
not expose `--allow-money` and will not submit real deposits or real bets.

Create a bot with BotFather, put the token and access list in `.env`, then run:

```bash
uv run python -m src.bot
```

Minimum `.env` settings:

```env
TELEGRAM_BOT_TOKEN=123456:abc...
TELEGRAM_ADMIN_IDS=123456789
TELEGRAM_ALLOWED_USER_IDS=111111111,222222222
TELEGRAM_ADMIN_INVITE_CODE=
TELEGRAM_DEFAULT_PROVIDER=openai
TELEGRAM_DEFAULT_MODEL=gpt-4o
TELEGRAM_DEFAULT_HEADLESS=false
```

Optional invite-code login:

```env
TELEGRAM_ADMIN_INVITE_CODE=admin-setup-2026
TELEGRAM_INVITE_CODE=qa-demo-2026
TELEGRAM_MAX_USERS=2
```

If a person is not allowlisted, `/start` tells them their Telegram numeric ID.
If `TELEGRAM_ADMIN_IDS` is empty, the first admin can be created once with:

```text
/admin_login admin-setup-2026
```

After an admin exists, admin bootstrap is disabled. The admin can then run:

```text
/add_user 123456789
/remove_user 123456789
/users
```

User commands:

```text
/menu
/login qa-demo-2026
/run_all
/run_simple
/run_complex
/run_tag betting
/run_id simple-1
/run_ids simple-1,complex-3
/status
/reports
/whoami
```

The bot uses inline menus for the same hierarchy:

```text
Run tests -> All / Simple / Complex / By category / Specific ID
Reports   -> Latest report / List reports
Status    -> current job and latest output
Admin     -> users and cancellation controls
```

Each run is executed as a subprocess of the existing CLI and writes artifacts to
`reports/bot_runs/<run_id>/`. When the run finishes, the bot sends the summary
plus `report.html` and `report.json` back to the chat.

For the difficult/complex sheet, the production-safe live run is:

```bash
uv run python -m src.main \
  --xlsx test_cases.xlsx \
  --provider openai \
  --model gpt-4o \
  --difficulty complex \
  --headless false \
  --report-dir reports/complex_final_v2
```

The complex suite intentionally separates safe UI flows from regulated account
and money flows:

- `complex-1` verifies sportsbook filtering by opening Sport, selecting Tennis,
  applying the Today filter, and confirming filtered events remain visible.
- `complex-2` and `complex-3` verify Bet Generator criteria and generated
  selections in the bet slip, then stop before the final Place Bet action.
- `complex-4` audits Romanian sports-market labels against a small glossary
  using the Virtual Sports market list.
- `complex-5` places a demonstrative Virtual Sports bet in `FUN` mode and
  verifies it in bet history.
- `complex-6` verifies casino demo stake controls and live-casino min/max ranges
  without submitting a real invalid stake.
- `complex-7` opens a casino slot in `/play/fun/` mode and performs a demo spin.
- Cases that require live-casino real-play wagers, duplicate CNP registration,
  SMS OTP, or controlled registration fixtures are reported as `blocked` with
  the exact missing precondition.

To gather stronger evidence for `complex-8` without placing a real live-casino
wager, run the login-first readiness check:

```bash
ALLOW_REAL_ACCOUNT_TESTS=true uv run python -m src.main \
  --xlsx test_cases.xlsx \
  --provider openai \
  --model gpt-4o \
  --ids complex-8 \
  --headless false \
  --report-dir reports/complex_8_logged_in
```

This logs in with `TEST_USERNAME`/`TEST_PASSWORD`, opens a real-play live-casino
provider session, then stops before selecting chips/seats or placing a wager.
The verdict is `inconclusive` by design because the original expected result
requires an accepted live-casino bet and balance update, which needs staging or
operator-issued test funds.

---

## Safety rails

This site is **a regulated, real-money gambling platform.** I treated it that way:

- **Dry-run by default.** A keyword blocklist (`place bet`, `confirm deposit`, `withdraw`, etc.) refuses to execute the final-confirmation step of any money-moving action.
- **PII masking in logs.** Usernames, passwords, CNPs are masked (`ab***ef`) in the trace output.
- **Test-account discipline.** The README and brief both call out that the agent should run against a dedicated staging/test account, never real player accounts.
- **Trace recording.** Every run produces a Playwright trace (`reports/trace_<id>.zip`) you can replay step-by-step in case a regulator asks for evidence.

In a regulated industry, "the AI did it" is not a defense. The rails are not optional — they're the product.

---

## How to verify it actually works (no API key needed)

```bash
python -m tests.smoke_test
```

This runs the entire pipeline against a local HTML page using a `FakeLLM` that returns canned plans. You'll see:

```
▶ Smoke test: AI QA agent pipeline

Verdict:   PASS
Duration:  6.29s
Reasoning: Saw 'Invalid username or password' on page after submit.
Steps run: 7
  ✓ step 1: fill textbox=Username <- ba***er 
  ✓ step 2: fill textbox=Password <- wr***ss 
  ✓ step 3: click button=Log in 
  ...
```

Reports land in `reports/smoke_report.html`.

---

## Running against TotoGaming.ro

The site is geo-blocked to Romania. To run for real:

1. Connect your machine (or a Docker container) to a **Romania-routed VPN**.
2. Set `PROXY_URL` env var if you'd rather route Playwright through a SOCKS/HTTP proxy.
3. Provide credentials for a dedicated **staging account** via env vars referenced by your test data.
4. `python -m src.main --xlsx test_cases.xlsx`

`PROXY_URL` supports plain and authenticated proxy URLs:

```env
PROXY_URL=http://host:port
PROXY_URL=http://username:password@host:port
PROXY_URL=socks5://username:password@host:port
```

For the live TotoGaming checks, prefer a Romania residential or ISP-style proxy
with sticky sessions over a shared datacenter proxy. The browser context already
uses Romanian locale/timezone settings; `PROXY_URL` controls the network exit.

If the CDN returns an access denial (for example HTTP 403 from Akamai), the agent
records the case as `blocked`, captures a screenshot/trace, and writes the
evidence into the report instead of spending LLM tokens on a page it cannot test.

In the current local environment, command-line traffic exits from Bucharest. The
site blocks headless Chromium with an Akamai HTTP 403, while headed Chromium
loads the live UI. Use `--headless false` for live TotoGaming.ro runs unless you
have a whitelisted test environment or operator-provided proxy.

---

## What's next

Things I'd build in the next sprint, listed in `docs/strategic_brief.pdf`:

1. **CI integration.** GitHub Actions / GitLab CI with a Slack webhook on failures. The JSON report is already CI-shaped.
2. **Parallelization.** `asyncio.gather` with a semaphore — 20 cases in ~2 minutes instead of ~20.
3. **Live-monitoring mode.** Run a subset every 15 minutes against production, alert on regression.
4. **Multi-brand fanout.** Same test cases, N partner URLs, one report per brand — directly leveraging Centrivo's white-label architecture.
5. **Productize as a Centrivo add-on.** See the brief for the business case.

---

## Project layout

```
digitain_qa_agent/
├── src/
│   ├── test_loader.py    # Excel → TestCase objects, auto-tagging
│   ├── llm_client.py     # Claude / OpenAI behind one interface
│   ├── agent.py          # Planner + Executor + Judge + self-heal
│   ├── reporter.py       # HTML + JSON report writers
│   └── main.py           # CLI entry point
├── tests/
│   └── smoke_test.py     # End-to-end pipeline test, no API needed
├── docs/
│   └── strategic_brief.pdf   # Business case + ideas beyond the brief
├── reports/                  # Generated artifacts (HTML, JSON, traces, screenshots)
├── test_cases.xlsx           # The assignment file
├── requirements.txt
└── README.md
```
