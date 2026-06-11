# Vault operations

How to run Founders Notes across **Mac mini** (primary bot host and dev machine), optional **laptop**, and **Telegram**. **Librarian + Janitor** run on the mini; the laptop is optional for editing away from the desk and recovery batches.

**Python venv:** use `ingestion/.venv` only (`pip install -r ingestion/requirements.txt -r ingestion/requirements-dev.txt`). A root `.venv` may exist locally — ignore it.

---

## Where each thing happens

| Task | Where |
|------|--------|
| Edit code / notes, PR, merge to `main` | **Laptop** (Cursor) |
| Auto `git pull` + reindex after merge | **Mac mini** (GitHub webhook, ~2–5 min) |
| Daily notes, Q&A, `/sync`, `/settings` | **Phone** (Telegram) |
| Webhook URL, delivery status | **GitHub** → Settings → Webhooks |
| Bot + webhook, Funnel, logs | **Mac mini** (Terminal) |
| Model slugs (primary) | `~/.config/founders-telegram/runtime.json` (or `/setmodel`) |
| Secrets (token, API keys, `VAULT_ROOT`) | `~/.config/founders-telegram/env` — **not in git** |

**Do not** run `python -m bot` on the **laptop** with the production token while the Mac mini bot is running (**409 Conflict**).

---

## Decision matrix

| Goal | Primary | Fallback |
|------|---------|----------|
| File today's notes | Telegram **Janitor** | — |
| Ask questions over studied episodes | Telegram **Librarian** | — |
| Batch expand / promote | `maintain.py` or CLI scripts | Janitor on mini |
| Fix catalog / layout gaps | `pipeline/verify.py`, `maintain.py` | — |
| Refresh search index after content change | Webhook on merge, Janitor promote, `/sync` | `maintain.py` menu 8 |
| Sync X posts into vault | Mac mini weekly cron (`install-x-posts-cron.sh`) | Laptop: `x/x_posts_sync.py` + `x/x_posts_attribute.py` |
| Ship bot/ingestion code | Laptop PR → merge → mini **pull + `/restart`** | See [Remote product workflow](#remote-product-workflow) |

---

## Primary path (Telegram)

| Role | What |
|------|------|
| **Janitor** | Paste bullets → clean → file `.notes.md` → expand → promote → reindex |
| **Librarian** | Q&A over studied corpus (agentic retrieval loop; [`AGENTS.md`](../AGENTS.md) voice; optional streaming — `/settings` → Stream replies) |

Runbook: [services/telegram/README.md](../services/telegram/README.md). Architecture: [telegram-vault-agent.md](telegram-vault-agent.md). Janitor guide: [janitor.md](janitor.md).

**BotFather menu:** `/start`, `/janitor`, `/settings`, `/sync`, `/newchat`, `/restart`.

---

## Development and testing

`pytest`, the mock harness, and live Librarian harness all run on the **Mac mini** (same clone as production). They use a **mocked Telegram transport** — safe alongside the launchd bot. Do **not** start a second `python -m bot` poller (409 Conflict).

Full guide: [telegram-mock-harness.md](telegram-mock-harness.md) · [testing.md](testing.md).

### Mac mini — quick test ladder

From repo root (`ingestion/.venv`):

```bash
# 1. Fast (no API) — agent loop + handlers
ingestion/.venv/bin/pytest tests/test_vault_agent.py tests/test_harness_scenarios.py -q

# 2. Interactive REPL with tool traces (no API)
ingestion/.venv/bin/python dev/mock_telegram_cli.py --stub-llm --debug

# 3. Live Librarian regression (~8 min, OpenRouter; does not use Bot API)
ingestion/.venv/bin/python dev/mock_telegram_cli.py --preflight
ingestion/.venv/bin/python dev/mock_telegram_cli.py --suite librarian --live-only -v

# 4. Production smoke — Telegram app on your phone (same launchd bot)
#    /restart after code pull, then ask a thematic Q and a multi-founder Q
```

Configs: `~/.config/founders-telegram/env` + `runtime.json` on this host. Reports: `dev/logs/runs/*-report.json` when using `-v`.

## Laptop development (optional)

### One-time setup

```bash
git clone git@github.com:ethan-frost-xyz/founders-notes.git founders-notes
cd founders-notes
python3 -m venv ingestion/.venv
ingestion/.venv/bin/pip install -r ingestion/requirements.txt -r ingestion/requirements-dev.txt
pytest tests -q
python dev/mock_telegram_cli.py --stub-llm --run-scenarios
```

Optional for **live** harness: `cp .env.example .env` and set `OPENROUTER_API_KEY`. Default dev does **not** need `catalog/embeddings.npy`.

### Daily loop

| Step | Where | Action |
|------|--------|--------|
| 1 | Laptop | `git checkout -b feature/...` → edit |
| 2 | Laptop | `pytest tests -q` (harness if touching Telegram) |
| 3 | GitHub | PR → merge to **`main`** |
| 4 | Mac mini | Webhook pulls (~2–5 min) |
| 5 | Phone | **Code change:** `/restart` then test. **Content only:** optional Librarian smoke |

**Fallback:** `/sync` on Telegram when webhook fails (bot idle).

### What belongs on the laptop (when you use one)

| OK | Avoid |
|----|--------|
| Code, docs, tests, `maintain.py` batches | `python -m bot` with **production** token while mini bot runs |
| `pytest`, mock harness (optional mirror of mini) | Assuming only the laptop can run tests |
| Merge / revert on GitHub | Assuming the laptop clone is the production bot host |

### Tailscale (laptop ↔ Mac mini)

Laptop (`ethans-macbook-air`) and mini (`ethans-mac-mini`) share tailnet `ethan-frost-xyz@`. From the laptop:

```bash
tailscale ping ethans-mac-mini
ssh ethans-mac-mini   # ethanfrost; Host in ~/.ssh/config
```

Use SSH for logs (`~/Library/Logs/founders-telegram/`) and `~/.config/founders-telegram/runtime.json`. **Model tuning** (`/setmodel`, `/settings`) and Librarian/Janitor daily use need **Telegram only** — no laptop Tailscale required. **Tailscale Funnel** for the GitHub webhook runs **on the mini only**; do not run Funnel on the laptop.

**Harness reports** (`dev/logs/runs/*-report.json`, paired `*-report.md`, suite summaries) are **committed to git** — browse on GitHub or locally after pull. Runs on the mini still write there first; sync then commit:

```bash
./dev/pull-harness-reports.sh    # rsync mini → laptop (then git add/commit)
./dev/pull-harness-reports.sh --list
```

Or commit and `git push` directly from the mini after a suite. `dev/logs/sessions/` and `dev/logs/sandbox/` remain gitignored.

### CI parity

```bash
pytest tests -q
cd ingestion && python pipeline/verify.py
```

---

## Remote product workflow

Use when you change **product code** (bot, ingestion the bot calls, prompts, deploy scripts) and want to test on the **real** Telegram bot.

**Content-only** merges do not need a bot restart.

### The one rule

After new **code** is on the Mac mini disk, the bot must **exit and start again** before you are testing that build.

| Action | New files on disk? | New Python in bot? |
|--------|-------------------|-------------------|
| Merge to `main` + webhook | Yes (~2–5 min) | **No** |
| `/sync` or `/pull` | Yes (when idle) | **No** |
| `/restart` | No | **Yes** |
| `deploy/restart-bot.sh` | No | **Yes** |

### Happy path

1. **Edit host (mini or laptop):** branch → edit → `pytest` (+ harness if needed) → PR → merge `main`.
2. **Mini:** confirm webhook **202** or `/sync` when idle (`tail sync.log`).
3. **Phone:** `/restart` → wait → `/start` → smoke test.

### Checklist

```
[ ] Merged to main
[ ] Mini has new commit (webhook or /sync)
[ ] /restart
[ ] /start works
[ ] Changed feature behaves differently
```

### Common hiccups

| Symptom | Fix |
|---------|-----|
| Merged but behavior unchanged | Forgot `/restart`, or pull never ran — check `git log -1`, `/sync`, `/restart` |
| Webhook 401 | `GITHUB_WEBHOOK_SECRET` mismatch; restart webhook launchd job |
| `409 Conflict` | Only one poller — `stop-bot.sh`, then `restart-bot.sh` |
| Bot won't come back | Read `bot.stderr.log`; fix on laptop → merge → `/sync` → restart block |
| Bad merge on `main` | Revert/fix on GitHub → `/sync` → `/restart` |

Full detail: historical steps preserved in git history of `docs/remote-product-workflow.md` (removed; see this section).

---

## Mac mini operator

**Paths (this host):**

| What | Path |
|------|------|
| Repo | `/Users/ethanfrost/projects/my-github-projects/founders-podcast-brain/founders-notes` |
| Telegram env | `~/.config/founders-telegram/env` |
| Models + tuning | `~/.config/founders-telegram/runtime.json` |
| Logs | `~/Library/Logs/founders-telegram/*.log` |
| Git remote | `git@github.com:ethan-frost-xyz/founders-notes.git` |

### Status & restart (paste on mini)

```bash
REPO="/Users/ethanfrost/projects/my-github-projects/founders-podcast-brain/founders-notes"
ENV="$HOME/.config/founders-telegram/env"
GUI="gui/$(id -u)"

set -a && source "$ENV" && set +a

echo "=== launchd ==="
launchctl print "$GUI/com.founders.telegram.bot" 2>/dev/null | grep "state =" || echo "BOT: not loaded"
launchctl print "$GUI/com.founders.telegram.webhook" 2>/dev/null | grep "state =" || echo "WEBHOOK: not loaded"
tailscale funnel status 2>/dev/null | head -6 || echo "(install tailscale CLI if missing)"

echo "=== restart ==="
"$REPO/services/telegram/deploy/restart-bot.sh"
launchctl kickstart -k "$GUI/com.founders.telegram.webhook"

sleep 2
tail -8 "$HOME/Library/Logs/founders-telegram/bot.stderr.log" 2>/dev/null
tail -5 "$HOME/Library/Logs/founders-telegram/webhook.log" 2>/dev/null
```

### Weekly X posts (optional cron)

Requires `X_BEARER_TOKEN`, `X_USERNAME`, and `OPENROUTER_API_KEY` in `~/.config/founders-telegram/env`. The mini must be able to `git push` (SSH remote).

```bash
REPO="/Users/ethanfrost/projects/my-github-projects/founders-podcast-brain/founders-notes"
"$REPO/services/telegram/deploy/install-x-posts-cron.sh"   # Sunday 5:00
"$REPO/services/telegram/deploy/install-x-posts-cron.sh" --print   # review line only
tail -f "$HOME/Library/Logs/founders-telegram/x-posts.log"
```

Manual run: `"$REPO/services/telegram/deploy/weekly-x-posts.sh"`. Status without API: `cd "$REPO/ingestion" && ../ingestion/.venv/bin/python x/x_posts_status.py`.

### Webhook verify

GitHub → repo → Settings → Webhooks → Recent Deliveries: ping **200**, push to `main` **202**.

### Troubleshooting

| Symptom | Fix |
|---------|-----|
| Merge didn't update mini | Check webhook deliveries + `sync.log` |
| `could not read Username` in sync.log | `git remote` must be SSH |
| Stale Librarian answers | `/sync` when idle after content merge |
| Reindex embed shape error | `/sync` when idle (self-heal on current `main`) |

First-time install: [services/telegram/README.md](../services/telegram/README.md).

---

## Recovery / tactical (laptop)

When batching expand/promote or working without Telegram:

| Tool | Purpose |
|------|---------|
| `cd ingestion && python maintain.py` | Coverage, expand backlog, drafts, promote, reindex (menu 8), expand log |
| `notes/expand_datapoints_llm.py` | OpenRouter → draft; `--promote` → `.expanded.md` |
| `notes/expand_tune.py` | Ad-hoc prompt A/B (local `fixtures/expand-runs/`, not committed) |
| `pipeline/verify.py` | Regenerate `catalog/gaps.md`; exit 1 on blocking gaps |

See [datapoint-workflow.md](datapoint-workflow.md), [expanded-backfill.md](expanded-backfill.md).

**Do not** duplicate Janitor in `maintain.py` — daily filing stays on Telegram.

---

## Index refresh

Canonical: [`ingestion/lib/reindex_vault.py`](../ingestion/lib/reindex_vault.py) — `build_chunks.py` then `build_embeddings.py`.

| Entry | How |
|-------|-----|
| Webhook | Push to `main` → `sync-and-index.sh` |
| Telegram | `/sync` when idle |
| Janitor | Promote & reindex |
| Laptop | `maintain.py` menu **8** or `python lib/reindex_vault.py` |

Embeddings need `OPENROUTER_API_KEY` and embed model in `runtime.json` (`/setmodel embed`) or `OPENROUTER_EMBED_MODEL` in env.

### When to refresh

| Situation | Action |
|-----------|--------|
| Promoted on mini (Janitor) | Usually automatic; if failed, `/sync` when idle |
| Committed notes/expanded on laptop → merged | Webhook; if stale, `/sync` |
| Stale Librarian after pull | `/sync` when idle; re-ask question |
| Active Telegram session | Wait until idle before `/sync` |
| Laptop-only | `maintain.py` menu 8 — no `git pull` unless you want it |

`catalog/.sync-in-progress` prevents overlapping webhook/cron/manual syncs.

---

## Path bootstrap (`VAULT_ROOT`)

| Context | Resolution |
|---------|------------|
| `cd ingestion && python …` | `ingestion/_bootstrap.setup_paths(__file__)` |
| Telegram / Janitor | `VAULT_ROOT` in `~/.config/founders-telegram/env` |
| `pytest` | `tests/conftest.py` → `setup_ingestion_paths(REPO)` |

---

## Related

- [retrieval.md](retrieval.md) — chunk index, orchestrated retrieval
- [ingestion/README.md](../ingestion/README.md) — script index
- [testing.md](testing.md) — CI, harness, v0 checklist tests
- [telegram-mock-harness.md](telegram-mock-harness.md) — pre-merge bot testing
