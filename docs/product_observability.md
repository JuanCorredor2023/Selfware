# Person 4 — Product & Observability (contract draft)

> Draft for the day-5 contract sign-off. Three paragraphs: what it does, what it exposes, what it consumes.

## What it does

This module is "the evidence": everything the hackathon judge sees live, and the project's single exit point to Nebius Token Factory. It covers four folders: `core/llm.py` (single Token Factory client, routes between Nemotron Nano and Nemotron Ultra), `observability/` (OpenTelemetry + per-tier cost calculation), `api/` (the FastAPI that exposes the system), and `web/` (the React dashboard).

## What it exposes

The API exposes `/health` (ready since week 1), and soon `/ask` and `/ask?strategy=flat|para` (ask the agent, choosing the retrieval strategy), `/provenance` (an answer's provenance: PARA folder + source emails + dates), `/cost` (per-tier cost panel: % Nano vs Ultra, cost per query, latency), and `/projects` (a project tracker derived from PARA). The dashboard exposes the live flat-vs-PARA toggle (A1), visible provenance (A2), and the cost panel (A4).

## What it consumes

From the agent (contract C3) it consumes `Answer(text, confidence, provenance, used_web, tier_calls)` to build the `/ask` response. From the context module (contract C2) it indirectly consumes `retrieve(query, strategy, k)` through `/ask`'s `strategy` parameter. And it produces, itself, in `core/llm.py`, contract C4 (`TierCall`), which feeds both the cost panel and Person 3's evaluation report.
