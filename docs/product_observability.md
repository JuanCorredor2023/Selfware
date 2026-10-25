# Person 4 — Product & Observability (contract draft)

> Draft for the day-5 contract sign-off. Three paragraphs: what it does, what it exposes, what it consumes.

## What it does

This module is "the evidence": everything the hackathon judge sees live, and the project's single exit point to Nebius Token Factory. It covers four folders: `core/llm.py` (single Token Factory client, routes between Nemotron Nano, Super and Ultra, the evaluation judge, and the embeddings model), `observability/` (OpenTelemetry + per-tier cost calculation), `api/` (the FastAPI that exposes the system), and `web/` (the React dashboard).

## What it exposes

The API exposes `/health`, `/ask?q=...&strategy=flat|para` (ask the agent, choosing the retrieval strategy; the answer carries its own provenance: PARA folder + source snippets + dates), `/cost` (per-tier cost panel data: share of Nano vs Ultra, total, cost per query, latency, tokens), and the PARA tree: `/para` (all four categories) plus `/projects`, `/areas`, `/resources` and `/archive`. `/ask` has two modes. By default it answers from a mock (`api/_mock_agent.py`), so the app and CI need no keys. With `SELFWARE_AGENT=real` it builds the real pipeline in `api/_real_agent.py`: `agent/ask.py::make_answer_question` plus Person 2's `Retrieve` over a Chroma folder (`SELFWARE_CHROMA_PATH`, default `chroma_data`) and the answer cache (`SELFWARE_CACHE_DIR`, default `.cache`). Per the 2026-09-30 meeting (D1/D2), the agent calls `retrieve()`; the API never retrieves by itself. The PARA endpoints (`/para`, `/projects`, ...) are still served from a mock (`api/_mock_para.py`) until Person 2 publishes a contract that reads the index directly. `/cost` is real: it aggregates every TierCall of each `/ask`, including the PARA query classifier's (collected per request in `api/_calls.py`). `scripts/index_emails.py` loads emails into Chroma (classify with Nano, then embed); it only estimates unless run with `--yes`. The dashboard exposes the live flat-vs-PARA toggle (A1), visible provenance (A2), and the cost panel (A4).

`core/llm.py` exposes `call(tier, messages)` (text + `TierCall`) and `call_with_logprobs(tier, messages)` (an `LLMResult` with the text, `finish_reason`, per-token logprobs and the `TierCall`, for the agent's confidence score). Tiers: `nano`, `super`, `ultra` and `judge` (the evaluation model, a different model from the generator); `embed(texts)` serves the embeddings model. `observability/cost.py` prices all of them; a model without a price logs a warning and is counted in `/cost` as `unpriced_calls` instead of silently costing $0.00.

## What it consumes

From the agent (contract C3) it consumes `Answer(text, confidence, provenance, used_web, finish_reason, tier_calls)` to build the `/ask` response. From the context module (contract C2) it indirectly consumes `retrieve(query, strategy, k)` through `/ask`'s `strategy` parameter. And it produces, itself, in `core/llm.py`, contract C4 (`TierCall`), which feeds both the cost panel and Person 3's evaluation report.
