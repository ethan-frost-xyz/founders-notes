# Laptop development

Develop on a **laptop** (Cursor), merge to **`main`**, and the **Mac mini** refreshes the vault automatically (GitHub webhook → `sync-and-index.sh`). Daily notes stay on **Telegram Janitor** on the mini — not on the laptop.

**Product/code changes (bot, ingestion the bot uses):** step-by-step pull + **restart** + hiccups → **[remote-product-workflow.md](remote-product-workflow.md)**.

**Mac mini runbook (status, restart, webhook checks):** [mac-mini-operator-setup.md](mac-mini-operator-setup.md).

---

## One-time laptop setup

```bash
git clone git@github.com:ethan-frost-xyz/founders-notes.git founders-notes
cd founders-notes
python3 -m venv ingestion/.venv
ingestion/.venv/bin/pip install -r ingestion/requirements.txt -r ingestion/requirements-dev.txt
pytest tests -q
python dev/mock_telegram_cli.py --stub-llm --run-scenarios
```

Optional for **live** harness only: `cp .env.example .env` and set `OPENROUTER_API_KEY`. Default dev does **not** need `catalog/embeddings.npy`.

---

## Daily loop (laptop)

| Step | Where | Action |
|------|--------|--------|
| 1 | **Laptop** | `git checkout -b feature/...` → edit |
| 2 | **Laptop** | `pytest tests -q` (and harness if touching Telegram handlers) |
| 3 | **Laptop** / **GitHub** | PR → merge to **`main`** |
| 4 | **Mac mini** | Webhook pulls in ~2–5 min (content + code files) |
| 5 | **Phone** | **Code change:** `/restart` then test — see [remote-product-workflow.md](remote-product-workflow.md). **Content only:** optional Librarian smoke; no restart |

**Fallback:** if auto-sync fails, **`/sync`** on Telegram (mini, bot idle).

---

## What belongs on the laptop

| OK on laptop | Avoid on laptop |
|--------------|-----------------|
| Code, docs, tests, `maintain.py` expand/promote batches | `python -m bot` with **production** token (409 vs Mac mini) |
| `pytest`, mock harness | Editing `~/.config/founders-telegram/env` expecting mini to change (that file is on the **mini**) |
| Merge / revert PRs on GitHub | Assuming a local laptop clone runs the production bot |

**Bad merge recovery:** revert or fix-forward on **GitHub** from the laptop → mini pulls via webhook → optional [restart](mac-mini-operator-setup.md#mac-mini--status--restart-paste-in-terminal) on mini. No second bot instance required.

---

## CI parity

```bash
pytest tests -q
cd ingestion && python pipeline/verify.py
```

Same as GitHub Actions and [AGENTS.md](../AGENTS.md).

---

## Related

- [remote-product-workflow.md](remote-product-workflow.md) — laptop → merge → pull → restart → Telegram test  
- [mac-mini-operator-setup.md](mac-mini-operator-setup.md) — production host  
- [manual-operations.md](manual-operations.md) — Telegram vs `maintain.py`  
- [telegram-mock-harness.md](telegram-mock-harness.md)  
- [services/telegram/README.md](../services/telegram/README.md) — deploy reference  
