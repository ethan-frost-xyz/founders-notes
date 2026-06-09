# Founders Librarian — Agentic Vision Brief

## What This System Is

The Founders Librarian is a personal AI study partner built on top of Ethan's private vault of Founders podcast notes, expanded datapoints, and episode transcripts. It is not a search tool or a document Q&A interface. It is designed to feel like a brilliant collaborator who has studied the same material and can reason across it — surfacing patterns, making connections across founders, and being honest when the evidence is thin.

The target experience is closest to Perplexity Pro Search: the user asks a question in natural language, and the system does whatever retrieval work is necessary before delivering a sharp, well-grounded answer with citations. Depth and voice matter more than raw speed.

***

## What Has Been Built So Far

The current system is a production-grade hybrid RAG pipeline that runs **once, before the model ever sees the question**:

- **Intent classify** — a rules-based check routes the message to `meta` / `follow_up` / `thematic` and decides whether to retrieve at all
- **Query expansion** — the user's question is rewritten into 5 semantically diverse variants by an LLM
- **Hybrid search** — each variant runs both semantic (vector) and keyword search over the vault's `expanded` + `summary` tiers, searched concurrently and fused via RRF (pool capped at ~40)
- **LLM reranking** — the candidate pool is scored by an LLM and the top ~12 are selected
- **Transcript fallback** — when the top rerank score is weak (< 6) or the question wants a verbatim quote, a keyword search over raw transcripts is mixed in
- **Synthesis** — a synthesis LLM receives the pre-assembled evidence block and produces a cited, thematic answer

Two escape-hatch tools are available to the synthesis turn today: `load_episode` (pull one full episode) and `list_episode_ids` (resolve a guest name or number to `ep-NNNN`). The model tiers are split: a fast/cheap `retrieval_model` handles expand + rerank, and a stronger `librarian_model` handles synthesis.

Source of truth: [`ingestion/lib/retrieval_orchestrator.py`](ingestion/lib/retrieval_orchestrator.py), [`services/telegram/bot/agent.py`](services/telegram/bot/agent.py), [`docs/retrieval.md`](docs/retrieval.md).

***

## The Core Problem with the Current Architecture

The pipeline is single-pass, linear, and **rigidly pre-scripted**. Retrieval is decided and executed before the intelligent model is ever consulted. The model that is actually good at reasoning about what evidence a question needs has no say in how that evidence is gathered.

This produces two failure modes that show up in real use:

1. **Thin or tangential evidence, with no recourse.** If the single pass surfaces weak evidence, the synthesis model is stuck with it. It synthesizes from whatever it was handed, producing answers that feel robotic or confidently vague instead of honestly saying "the vault doesn't really cover this."

2. **Multi-hop and cross-founder questions fall flat.** A question like "how did Edison and Rockefeller differ in how they built teams?" needs evidence about *both* founders held in relationship. A single search pass surfaces one side or a blurry average of both — never a clean two-sided comparison.

There is no feedback loop. There is no way for the model to say "this isn't enough — let me search again from a different angle," and no way to decompose a hard question into the parts it actually contains.

***

## The Vision for the Agentic Layer

Give the model full agency over its own retrieval. Instead of receiving a pre-assembled evidence block passively, the model drives the search process from the start — deciding what to look for, how to decompose it, when to triangulate, and when it has enough to answer well.

### Cold start, full agency

The model receives the user's question and a toolbox — and **no pre-retrieved evidence**. It decides every search itself, including the first one. There is no forced up-front retrieval pass. This is the single most important change from the current architecture: the rigid pre-scripted pipeline is replaced by a model that orchestrates retrieval as the question demands.

### The toolbox (5 tools)

The model composes these as the question requires. Each is a thin surface over retrieval logic that already exists — nothing underneath changes.

- **`search_vault(query)`** — thematic / cross-episode retrieval. Runs the full existing pipeline (expand into variants → concurrent hybrid search → RRF → LLM rerank) on the model's targeted query. The everyday workhorse.
- **`search_vault_many(queries[])`** — **model-driven parallel decomposition.** The model passes its own list of sub-queries (e.g. `["how Edison built teams", "how Rockefeller built teams"]`); each runs the full pipeline concurrently, and results come back **labeled per sub-query** so the model can compare and triangulate. This is the direct fix for multi-hop and multi-founder questions. Soft limit of ~6 sub-queries per call.
- **`search_transcript(query)`** — keyword search over raw transcripts, as a first-class tool the model can choose deliberately (for verbatim quotes, exact dialogue, or to triangulate transcript against expanded notes). This promotes today's hidden rerank-fallback into something the model controls.
- **`list_episode_ids(query)`** — resolve a guest name or episode number to a canonical `ep-NNNN`.
- **`load_episode(episode_id)`** — pull one full episode (post + notes + expanded) when the question is about a single founder in depth.

### A dynamic, non-rigid loop

The model keeps searching until it judges the evidence sufficient, then answers. There is **no fixed iteration count and no forced minimum** — stopping is the model's own judgment, not a mandatory checklist or procedure. Most questions will resolve quickly; genuinely hard ones can dig as deep as they need.

A hard safety ceiling of **6 search rounds** prevents a runaway loop. The ceiling counts **tool-call rounds, not sub-queries**: one `search_vault_many` call is a single round no matter how many sub-queries it contains. The ceiling bounds reasoning loops — it never penalizes decomposition breadth on a single hard question.

### Composition guidance, not just tools

A custom toolset underperforms when the model is only handed tool descriptions. The prompt ([`AGENTS.md`](AGENTS.md)) must teach the model *how to wield* the toolbox: decompose multi-founder questions with `search_vault_many`, triangulate `search_transcript` against expanded notes, and actively seek disconfirming evidence before committing to a comparison. This guidance is written as **soft heuristics, never as mandatory steps** — it sharpens the model's judgment without making the backend rigid again.

### The model tiers stay split

The strong `librarian_model` drives the loop — judging evidence, deciding to search again, writing each query, and producing the final answer. The cheap/fast `retrieval_model` does the grunt work *inside* each search (expand + rerank). The decision to re-search needs the same intelligence as synthesis; the costly model stays out of the mechanical retrieval steps.

### The voice stays consistent

The agentic layer changes the retrieval architecture, not the synthesis persona. The Librarian still sounds like a sharp, opinionated thought partner. It still makes cross-episode connections. It still flags when evidence is thin. The only difference is that it now goes and gathers the right evidence itself before answering.

### Quality first; speed is a later problem

Answer quality is the only thing that matters right now. Cost is not a concern. Latency and speed are explicitly **deferred future optimization**, not a design constraint on this layer. A deeper, slower answer to a hard question is the right trade-off today; making it fast comes later.

***

## Influence: Perplexity "Search as Code" and 2026 agentic-RAG patterns

This design borrows a principle from Perplexity's June 2026 "Search as Code" architecture and the broader agentic-RAG literature: stop treating search as one monolithic, pre-scripted endpoint, and instead **expose the search stack as atomized, composable primitives that the model assembles per question** — with parallel fan-out over sub-queries and a distinct tool per corpus. That principle is exactly what motivates `search_vault_many` (decomposition / parallel fan-out) and `search_transcript` (a separate corpus the model can triangulate against).

What is **explicitly out of scope**: Perplexity runs model-generated Python in a secure sandbox over a web-scale search stack doing thousands of operations per minute. This vault is ~1.2k studied-episode vectors on a Mac mini. A code-generation sandbox would be massive over-engineering here. The brief takes the *granularity, decomposition, and triangulation* principles — not literal code execution.

***

## What the Coding Agent Should Build

The change is at the orchestration and tool-surface layer, not the retrieval internals.

- Give the `librarian_model` the **five tools** above as OpenRouter/OpenAI-format tool definitions.
- **Remove the mandatory up-front retrieval call** so the turn cold-starts with no evidence; drop the rules-based retrieve/skip pre-gating (`classify_intent`) and trust the model not to search for a greeting.
- Implement `search_vault` as a thin adapter over the existing `retrieve_for_turn()` pipeline.
- Implement `search_vault_many` as a concurrent fan-out of that same pipeline across the model's sub-queries, returning results labeled per sub-query.
- Expose `search_transcript` over the existing `search_transcript_evidence()`.
- Run the agent loop until the model stops calling tools and answers, or the **6-round** safety cap (rounds, not sub-queries) is hit.
- Add the composition guidance to [`AGENTS.md`](AGENTS.md), and update its now-inaccurate "Retrieval already ran before you see this message" line — under cold start, retrieval has *not* run.

Everything underneath stays exactly as it is: the chunks pipeline, embeddings, RRF merge, and reranker are unchanged. The change is *who decides when retrieval runs* — and that is now the model.

***

## Success Criteria

The system is working correctly when:

- Multi-hop and cross-founder questions come back noticeably sharper and better-grounded, because the model decomposed them and triangulated the evidence
- Thin-evidence questions get an honest "the vault doesn't really cover this" instead of confident, vague filler
- The synthesis voice stays consistent regardless of how many search rounds ran
- It is judged primarily by **reading real answers** — Ethan's qualitative read is the bar
- A small, repeatable set of hard questions (multi-founder comparisons, thin-evidence probes) lives in the mock harness ([`docs/telegram-mock-harness.md`](docs/telegram-mock-harness.md)) so quality stays testable as prompts are tuned

Speed and cost are explicitly **not** part of the success bar for this layer.
