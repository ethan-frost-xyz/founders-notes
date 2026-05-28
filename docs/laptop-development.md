# Laptop development

Develop on a laptop (Cursor), merge to `main`, and let the **Mac mini** refresh the vault via GitHub webhook + `sync-and-index.sh`. Daily notes filing stays on **Telegram Janitor** on the mini — do not duplicate that workflow on the laptop.

## One-time setup

```bash
git clone <repo-url> founders-notes && cd founders-notes
python3 -m venv ingestion/.venv
ingestion/.venv/bin/pip install -r ingestion/requirements.txt -r ingestion/requirements-dev.txt
pytest tests -q
python dev/mock_telegram_cli.py --stub-llm --run-scenarios
```

Optional for **live** harness only:

```bash
cp .env.example .env   # OPENROUTER_API_KEY
# Optional: copy Mac mini runtime.json for model parity
# cp ~/.config/founders-telegram/runtime.json ~/.config/founders-telegram/runtime.json
```

- Default dev needs **no** local `catalog/embeddings.npy` — echo harness + unit tests suffice.
- Live Librarian scenarios need `OPENROUTER_API_KEY`, `catalog/chunks.jsonl`, and `catalog/embeddings.npy` on the machine running the harness.

## Daily loop

1. `git checkout -b feature/...`
2. Edit code or content; run `pytest tests -q` (and harness if touching Telegram).
3. Open PR → merge to `main`.
4. Mac mini webhook runs `sync-and-index.sh` within a few minutes (or `/sync` on Telegram if webhook not installed).
5. Optional: Librarian smoke on phone for **content** changes only.

## What to do on the laptop

| OK | Avoid |
|----|--------|
| Ingestion scripts, tests, docs, Telegram bot code | Running two Telegram pollers (mini + laptop) |
| `maintain.py` expand/promote when batching | Expecting Janitor on laptop without bot |
| Notes/posts in git for episodes you are studying | Bulk-filling empty note scaffolds “ahead” of listening |

Operator matrix: [manual-operations.md](manual-operations.md). Mac mini runbook: [services/telegram/README.md](../services/telegram/README.md).

## CI parity

From repo root:

```bash
pytest tests -q
cd ingestion && python pipeline/verify.py
```

Same as GitHub Actions and [AGENTS.md](../AGENTS.md).

## Mac mini (after you merge)

Operator checklist (runtime cutover + webhook): **[mac-mini-operator-setup.md](mac-mini-operator-setup.md)**.

## Related

- [telegram-mock-harness.md](telegram-mock-harness.md)
- [manual-operations.md](manual-operations.md)
- [mac-mini-operator-setup.md](mac-mini-operator-setup.md)
- [`.cursor/plans/laptop_remote_hardening.plan.md`](../.cursor/plans/laptop_remote_hardening.plan.md)
