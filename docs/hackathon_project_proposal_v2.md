# Project proposal — Nebius x NVIDIA Global AI Hackathon (v2)

**Track:** Personal AI
**Working name:** *Atlas*
**Team:** 4 people (+1 for product if we land one) · **Submission:** October 30, 10:00 PT (11:00 Mexico City time). We're delivering on the 27th.

---

## 1. The idea in one sentence

> A personal assistant over email that organizes the user's context into PARA structure, **measures** whether that structure improves retrieval versus a flat RAG, **knows when it doesn't know**, and shows it all in an interface where the judge sees the difference live.

---

## 2. The hypothesis

**H1:** Classifying personal context into PARA (Projects, Areas, Resources, Archive) and filtering retrieval by that structure improves retrieval quality versus a flat vector index over the same corpus.

- **Baseline:** flat index (AutoRAG) over the email corpus.
- **Treatment:** same corpus, classified into PARA by Nemotron Nano, retrieved with a structural filter.
- **Primary metric:** *context precision* and *context recall* (RAGAS), **reported by question category** (projects / areas / resources), not just the overall figure.
- **Secondary:** p95 latency, cost per query, token distribution per tier (OpenTelemetry).

Reporting by category is the safety net: if PARA doesn't improve the overall number, it almost certainly improves on project questions. There's always a presentable result.

---

## 3. Architecture

```
Gmail ─────┐
           ├──▶ Ingestion (Serverless Jobs)
WhoareU.md ┘      normalize · dedup · classify PARA (Nemotron NANO)
                        │
                        ▼
                  Context  ──── two LIVE indexes, not just for eval
                  ├─ Flat index ──────────────┐
                  └─ Index + PARA filter ─────┤
                                                ▼
                                       Retrieval strategy
                                                │
                                                ▼
                                  Answering agent (Nemotron ULTRA)
                                  · confidence per answer
                                  · if confidence < threshold ──▶ Tavily (web)
                                  · provenance: PARA folder + emails + dates
                                                │
                              ┌─────────────────┴─────────────────┐
                              ▼                                   ▼
                     Dashboard (React, own build)         Evaluation (RAGAS)
                     · flat vs PARA toggle                 → THE NUMBER, by category
                     · visible provenance
                     · cost-per-tier panel
                     · automatic archiving

              OpenTelemetry wraps everything: tokens, latency, cost, tier
```

### Mapping to the platform (goes in the README and gets said in the video)
| Task | Service | Why |
|---|---|---|
| Classify thousands of emails into PARA | **Nemotron Nano** | Cheap, high-volume, a classification task |
| Answer questions with context | **Nemotron 3 Ultra** | Few calls, real reasoning |
| Batch ingestion, automatic archiving, eval runs | **Nebius Serverless Jobs** | Async, doesn't block the app |
| Web search when context isn't enough | **Tavily** | $3,000 bonus; needs a runtime call |
| All inference calls | **Token Factory** | Meets the requirement |

---

## 4. What we're building

### Core (no project without this)
| # | Component | What it is |
|---|---|---|
| N1 | Gmail connector | Just one. IMAP or a Gmail MCP. |
| N2 | Batch ingestion | Normalize → dedup → classify PARA with Nano. Serverless Jobs. |
| N3 | Two indexes | Flat and PARA, both live in production, not just for eval. |
| N4 | Answering agent | Ultra, with retrieved context and confidence per answer. |
| N5 | Evaluation harness | ~200 hand-written questions, RAGAS, OTel, results by category. |
| N6 | Dashboard | One. Our own React. Project tracker derived from PARA. |
| N7 | WhoareU.md | Plain-text user profile. Injected into the agent. |

### Additions to win (each one appears in the video; order = priority)
| # | Addition | What it targets | Cost |
|---|---|---|---|
| A1 | **Live toggle**, flat vs PARA on the same question, two columns | Design, Tech. Impl. | Low (both indexes already exist) |
| A2 | **Visible provenance**: PARA folder + source emails + dates on every answer | Design, Impact | Low |
| A3 | **Abstain → Tavily**: confidence below threshold = search the web and say so | Idea, Tavily bonus | Medium (calibrate the threshold) |
| A4 | **Per-tier cost panel**: % Nano vs Ultra, cost/query, latency | Tech. Impl. (1st tiebreaker) | Very low with OTel |
| A5 | **External user** who uses it for two weeks and appears for 10s in the video | Impact | Low code effort, ask for one NOW |
| A6 | **Automatic archiving**: a project with no activity for N days → Archive, visible | Idea | Low |

Rule: if an addition threatens the core, the addition gets cut. A6 is first to go, then A3.

### Out of scope (portfolio, after October 30)
Discovering implicit needs · generating dashboards · a second connector · WhatsApp/social · Lovable in delivered code.

---

## 5. The number

> "Over ___ real emails from ___ people and ___ questions, PARA improves *context recall* on project questions from ___ to ___ (and ___ on areas, ___ on resources), with ___% of calls on Nano and a cost of $___ per query."

**Corpus:** the four of ours' email, plus the external user's. If it's under ~2,000 emails, supplement with a public dataset.
**Questions:** ~200, hand-written, with a known answer, labeled by PARA category. **Not AI-generated**: if a model generates them, we'd be measuring how well the model answers itself.

---

## 6. Lanes

| Lane | Owner | Core | Additions |
|---|---|---|---|
| **A. Ingestion** | ___ | N1, N2, N7 | A6 |
| **B. Context & retrieval** | ___ | N3, retrieval strategy | Supports A1 |
| **C. Evaluation** | ___ | N5, OTel, per-category curves | A4, A3's threshold |
| **D. Product & video** | ___ | N4, N6, 3-min script | A1, A2, A3 (UI), A5 |

Contracts between lanes signed on **day 5**, with fake data if needed. Lane D carries the most load; if we land a fifth person, they go there.

---

## 7. Calendar

| Wk | Dates | Milestone |
|---|---|---|
| 1 | Sep 7–13 | Public repo, Apache 2.0. Contracts. **Video script written.** Corpus inventoried. **Ask for the external user (A5).** Email Devpost about City Winner. |
| 2 | Sep 14–20 | Each lane with its piece isolated. First tests. Eval questions: first 50. |
| 3 | Sep 21–27 | **Rough end-to-end integration.** First RAGAS run with a preliminary number. |
| 4 | Sep 28–Oct 4 | Iterate on the number. Dashboard working. A1 and A2. |
| 5 | Oct 5–11 | A3, A4. Final eval run. **Feature freeze.** |
| 6 | Oct 12–18 | README, description, feedback for Nebius (seriously go for the $100 prize). A6 if there's time left. |
| 7 | Oct 19–25 | **Video.** Record, edit, re-record. |
| 8 | Oct 26–30 | Submit on the **27th**. Buffer. |

---

## 8. Video script (3:00)

| Time | What's on screen |
|---|---|
| 0:00–0:20 | The problem. The external user on camera saying what was costing them time. |
| 0:20–1:00 | A real question. Answer with **visible provenance** (A2). |
| 1:00–1:40 | **The toggle** (A1): same question, flat vs PARA. The judge sees the difference. |
| 1:40–2:10 | **The number**, by category. **Cost panel** by tier (A4): "91% Nano." |
| 2:10–2:40 | A question email can't answer. The system admits it and goes to **Tavily** (A3). |
| 2:40–3:00 | Close: what it is, who it's for, what we measure, the repo. |

Every week: does what we're building show up here? If not, it gets cut.

---

## 9. Working rules

- **AI:** for what we already know how to do (boilerplate, scaffolding, wrappers, CSS). Not for what we want to learn (schema, classification, invariant tests).
- **Merging:** nobody merges code they can't explain line by line to another teammate. If they can't, it gets rewritten or deleted.
- **Tests:** every lane ships tests with its module. They test invariants we decide on.
- **Video:** the judge can grade using only the video and description. The video **is** the grade.

---

## 10. If we don't make it

The hackathon is a strict subset of the portfolio. Same repo. After October 30: discovering needs, more connectors, schema evolution.

The ablation study with numbers is already a portfolio piece the day it's done. Blog post: *"We measured whether PARA improves RAG over personal email,"* with charts and the repo.

---

## 11. Today's decisions

1. H1 as the axis? Yes / No.
2. Owner per lane.
3. How many emails do we have? Public dataset?
4. Gmail MCP or IMAP.
5. Who do we ask to be the external user? Ask this week.
6. Are we looking for a fifth person for product?
7. Name.
