# Founders Librarian — Agentic Vision Brief

## What This System Is

The Founders Librarian is a personal AI study partner built on top of Ethan's private vault of Founders podcast notes, expanded datapoints, and episode transcripts. It is not a search tool or a document Q&A interface. It is designed to feel like a brilliant collaborator who has studied the same material and can reason across it — surfacing patterns, making connections across founders, and being honest when the evidence is thin.

The target experience is closest to Perplexity Pro Search: the user asks a question in natural language, and the system does whatever retrieval work is necessary before delivering a sharp, well-grounded answer with citations. Speed matters, but depth and voice matter more.

***

## What Has Been Built So Far

The current system is a production-grade hybrid RAG pipeline:

- **Query expansion** — the user's question is rewritten into 5 semantically diverse variants by an LLM
- **Hybrid search** — each variant runs both semantic (vector) and keyword search over the vault, results are fused via RRF
- **LLM reranking** — a pool of up to 40 candidates is scored by an LLM and the top 12 are selected
- **Synthesis** — a synthesis LLM receives the evidence block and produces a cited, thematic answer

The prompts governing expansion, reranking, and synthesis have recently been rewritten to improve voice quality and retrieval precision. The variant search loop has been parallelized. The retrieval and synthesis model tiers are now split (fast/cheap model for expand + rerank; stronger model for synthesis).

***

## The Core Problem with the Current Architecture

The pipeline is single-pass and linear. Retrieval runs once, before the synthesis model sees the question. If that single pass surfaces weak or tangential evidence, the synthesis model has no recourse — it synthesizes from whatever it was handed, producing answers that feel robotic or confidently vague.

There is no feedback loop. There is no ability to say "this evidence doesn't answer the question — search again from a different angle." There is no way to handle multi-hop questions (e.g., "how did Edison and Rockefeller differ in how they built teams?") because a single search pass will surface evidence about one or the other, not both in meaningful relationship.

***

## The Vision for the Agentic Layer

The goal is to give the synthesis model agency over its own retrieval. Instead of receiving a pre-assembled evidence block passively, the model should be able to call back into the vault as a tool — deciding when to search, what to search for, and when it has enough to answer well.

Concretely, this means:

**The synthesis model becomes the orchestrator.** It receives the user's question and a `search_vault` tool. It decides whether the pre-retrieved evidence is sufficient or whether it needs to search again — with a tighter, more targeted query derived from its own reasoning about what's missing.

**The loop is bounded and purposeful.** This is not open-ended agent behavior. The loop caps at 2 iterations maximum. The model is expected to answer on the first pass for most questions. The second search is reserved for cases where the first evidence is genuinely insufficient — multi-hop questions, requests that span multiple founders, or cases where the initial retrieval returned near-miss results.

**The voice stays consistent.** The agentic layer changes the retrieval architecture, not the synthesis persona. The Librarian still sounds like a sharp, opinionated thought partner. It still makes cross-episode connections. It still flags when evidence is thin. The only difference is that it now has the ability to go find better evidence before answering rather than being stuck with what it was handed.

**Speed is managed, not ignored.** The second search call adds latency. This is acceptable because: (a) most questions will resolve in one pass, (b) the user's experience of a slightly slower but meaningfully deeper answer on complex questions is the right trade-off, and (c) the retrieval model tier (fast/cheap) handles the tool call, not the synthesis model.

***

## What the Coding Agent Should Build

The agentic implementation should be minimal and surgical — a wrapper around the existing retrieval pipeline, not a rebuild of it.

The synthesis model should be given the `search_vault` tool as an OpenRouter/OpenAI-format tool definition. The existing `retrieve_for_turn()` pipeline becomes the implementation behind that tool. The agent loop runs until the model stops calling the tool or the 2-call cap is hit. The final synthesis call happens when the model has decided it has sufficient evidence.

Nothing in the underlying retrieval logic changes. The chunks pipeline, embeddings, RRF merge, and reranker all stay exactly as they are. The change is purely at the orchestration layer — who decides when retrieval runs.

***

## Success Criteria

The system is working correctly when:

- Simple, single-founder questions answer on the first pass with no second search
- Multi-hop or cross-founder questions trigger a second targeted search and produce noticeably better answers
- The synthesis voice remains consistent regardless of whether one or two search passes ran
- The model correctly surfaces evidence-quality warnings when even two passes don't return strong results
- Total latency for single-pass questions does not increase meaningfully versus the current pipeline
