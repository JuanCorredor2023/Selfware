# Atlas — Final Plan · Nebius x NVIDIA Global AI Hackathon

**Track:** Personal AI · **Submission:** October 27 (official deadline Oct 30, 10:00 PT = 11:00 Mexico City)
**Architecture:** modular monolith · one repo · one package · one deploy · explicit module boundaries
**Team:** 4 · Video, script, README, feedback, and description: **all four**

---

## 1. The idea

> A personal assistant over email that organizes context into PARA, **measures** whether PARA improves retrieval versus flat RAG, **knows when it doesn't know** (and searches the web), and shows it on a dashboard where the judge sees the difference live.

**H1:** classifying into PARA and filtering by that structure improves *context precision* and *context recall* (RAGAS) versus a flat index over the same corpus. Reported **by question category**.

---

## 2. Final diagram

File: `atlas_architecture_final.mermaid` (renders on GitHub; paste it into the README).

One-line read: `Gmail + WhoareU.md → ingest (Nano, Serverless Jobs) → context (two live indexes) → agent (Ultra, confidence, Tavily) → api/web (toggle, provenance, cost)`, with `eval` hanging off context and agent, and `observability` wrapping every call to Token Factory through **a single exit point**.

---

## 3. Modular monolith: repo layout

```
atlas/
├── core/                 # shared · schema owner: Person 1
│   ├── schemas.py        # Document, ContextItem, Chunk, Provenance, Answer, TierCall
│   ├── config.py         # settings, thresholds, PARA paths
│   └── llm.py            # SINGLE client to Token Factory · emits OTel spans · routes Nano/Ultra
├── ingest/               # Person 1
│   ├── gmail.py          # connector (IMAP or MCP)
│   ├── normalize.py      # cleanup, dedup by hash, metadata
│   ├── classify.py       # PARA classification with Nano
│   ├── profile.py        # loads WhoareU.md
│   ├── archive.py        # job: project with no activity for N days → Archive
│   └── jobs.py           # entrypoints for Nebius Serverless Jobs
├── context/              # Person 2
│   ├── store.py          # document store
│   ├── embed.py          # embeddings
│   ├── index_flat.py     # flat index
│   ├── index_para.py     # index + structural PARA filter
│   └── retrieve.py       # retrieve(query, strategy, k) → [Chunk with Provenance]
├── agent/                # Person 3
│   ├── answer.py         # agent on top of Ultra
│   ├── confidence.py     # per-answer confidence estimate
│   ├── abstain.py        # policy: confidence < threshold → web
│   └── tavily.py         # web search
├── eval/                 # Person 3
│   ├── questions/        # ~200 questions, JSONL, labeled by PARA category
│   ├── harness.py        # runs flat vs PARA over the set
│   ├── ragas_runner.py   # RAGAS metrics
│   └── report.py         # per-category table + cost/latency curves
├── observability/        # Person 4 (everyone instruments)
│   ├── otel.py           # OpenTelemetry setup
│   └── cost.py           # tokens → cost per tier
├── api/                  # Person 4
│   └── app.py            # FastAPI: /ask, /ask?strategy=flat|para, /provenance, /cost, /projects
└── web/                  # Person 4
    └── src/              # React: dashboard, toggle, provenance, cost panel
tests/
├── ingest/  context/  agent/  eval/  api/     # each module ships its own
README.md · LICENSE (Apache 2.0) · FEEDBACK.md · docs/video_script.md
```

### Monolith rules
- **No module imports from another except `core/`.** Communication between modules goes through the contracts in section 4. If you need something from another module, it goes into the contract, not into an import.
- **Every call to Token Factory goes through `core/llm.py`.** It's the only way the cost panel and compliance stay verifiable. A `grep` for the Token Factory URL must find exactly one file.
- One `pyproject.toml`, one startup command, one jobs entrypoint.

---

## 4. Contracts between modules (signed on day 5, with fake data if needed)

| Contract | From → To | Signature |
|---|---|---|
| **C1** | ingest → context | `ContextItem(id, source, text, ts, hash, para_path, meta)` |
| **C2** | context → agent, eval, api | `retrieve(query: str, strategy: "flat" \| "para", k: int) -> list[Chunk]`, with `Chunk(text, item_id, para_path, ts, score)` |
| **C3** | agent → api, eval | `Answer(text, confidence: float, provenance: list[Chunk], used_web: bool, tier_calls: list[TierCall])` |
| **C4** | core/llm → observability | every call emits `TierCall(model, tokens_in, tokens_out, latency_ms, cost_usd)` |
| **C5** | ingest/profile → agent | `Profile(text)` from WhoareU.md, injected as system context |
| **C6** | eval → everyone | `questions/*.jsonl`: `{q, expected, category: project\|area\|resource}` |

Changing a contract requires notifying everyone and updating `core/schemas.py` in the same PR.

---

## 5. Module assignment

| Person | Modules | Owns | Definition of done |
|---|---|---|---|
| **1 · Ingestion** | `ingest/`, `core/schemas.py`, `core/config.py`, Serverless Jobs deploy | The canonical schema. Compliance with the rules (Serverless Jobs + Token Factory). | A job runs on Nebius, reads Gmail, writes N classified `ContextItem`s. Automatic archiving moves inactive projects. |
| **2 · Context** | `context/` | The two live indexes and the retrieval strategy. Provenance as data. | `retrieve()` answers in both strategies with full provenance in < 500 ms over the real corpus. |
| **3 · Agent & evaluation** | `agent/`, `eval/` | **The number.** Confidence, the threshold, Tavily. | RAGAS report by category, flat vs PARA, reproducible with one command. Abstention calibrated against that report. |
| **4 · Product & observability** | `api/`, `web/`, `observability/`, `core/llm.py` | **The evidence.** Everything the judge sees. The single exit point to Token Factory. | Dashboard with toggle, provenance, and cost panel, deployed at a public URL that works with nobody on the team connected. |

**Suggested split**, the decision is theirs: whoever has the most systems experience takes Person 1 (it's the compliance piece and the schema everyone consumes). Whoever most wants to learn LLM evaluation takes Person 3: it's the module with the most transferable learning and the one that produces the result.

### Work for all four
- **Evaluation questions:** 50 per person over their own email, labeled. Person 3 consolidates. **Not AI-generated.**
- **Video script:** written in week 1 by all four (`docs/video_script.md`) and reviewed every Friday.
- **Video, README, Devpost description, FEEDBACK.md:** weeks 7-8, all four.
- **Code review:** nobody merges without another person's review. Nobody merges what they can't explain line by line.

---

## 6. 6-week build plan + 2 weeks of delivery

Every Friday there's a **30-minute internal demo**: everyone shows their module running, the script gets reviewed, and we decide what to cut.

### Week 1 · Sep 7–13 · Foundations & contracts
| Person 1 | Person 2 | Person 3 | Person 4 |
|---|---|---|---|
| Repo, Apache 2.0 visible in About, `pyproject`, minimal CI. `core/schemas.py` v0. Gmail access working (even for one email). | Empty document store + `retrieve()` returning fake data with the C2 signature. | Format for `questions/*.jsonl`. First 20 own questions. `harness.py` skeleton. | `core/llm.py` with one real call to Nano and one to Ultra via Token Factory, emitting `TierCall`. FastAPI with `/health`. |

**All four:** video script v0 (`docs/video_script.md`). Email inventory: how many do we have? Ask the external user. Email Devpost about City Winner. Join the Builder Program (credits).
**Friday the 11th:** contracts C1–C6 signed. Nobody changes a signature without a PR to `core/`.

### Week 2 · Sep 14–20 · Each module isolated, working
| Person 1 | Person 2 | Person 3 | Person 4 |
|---|---|---|---|
| Real Gmail connector, normalization, dedup by hash. PARA classification with Nano over 200 real emails. Dedup and idempotency tests. | Embeddings + flat index over what P1 delivers. Real `retrieve("flat")`. Retrieval tests. | Answering agent on Ultra consuming `retrieve()` (even if flat only). 50 own questions. RAGAS run on flat only. | `/ask` wired to the agent. Dashboard: layout, project list from PARA (fake data). OTel exporting spans. |

**Friday the 18th:** first number, even if just the baseline. Script v1.

### Week 3 · Sep 21–27 · Rough end-to-end integration
| Person 1 | Person 2 | Person 3 | Person 4 |
|---|---|---|---|
| Job deployed on **Serverless Jobs** running full ingestion. WhoareU.md loaded. | Index + PARA filter. Real `retrieve("para")`. **Both indexes live.** | Harness runs flat vs PARA over the ~200 consolidated questions. **First per-category report.** | `/ask?strategy=` working. Dashboard consumes real data. Provenance as data in the response. |

**Friday the 25th — hard milestone:** a real question goes in through the dashboard, through real ingestion, two indexes, Ultra, and comes back. Even if it's rough. If it doesn't happen, week 4 is dedicated to making it happen, and A6 and A3 get cut.

### Week 4 · Sep 28–Oct 4 · Iterate on the number
| Person 1 | Person 2 | Person 3 | Person 4 |
|---|---|---|---|
| Robustness: retries, sync cursor, incremental runs. Automatic archiving job (A6) if milestone 3 was met. | Adjust PARA strategy based on what the report says (k, filter, fallback to flat when a folder is empty). | Analyze by category. Per-answer confidence (`confidence.py`). Start calibrating the threshold against the report. | **Toggle** (A1) on the dashboard. **Visible provenance** (A2). |

**Friday the 2nd:** number v2 by category. Decision: does H1 hold globally, or only by category? The script adjusts to the answer.

### Week 5 · Oct 5–11 · Additions & freeze
| Person 1 | Person 2 | Person 3 | Person 4 |
|---|---|---|---|
| Ingestion run over the external user's corpus. Data cleanup for the video. | Regression tests on retrieval. Document the strategy in `docs/`. | **Abstain → Tavily** (A3) with a calibrated threshold. Final evaluation run. Final report. | **Cost panel** (A4). Deploy to a stable public URL. |

**Friday the 9th — feature freeze.** After today, only bugs, docs, and video. Whatever didn't make it in, doesn't get in.

### Week 6 · Oct 12–18 · Stability & documentation
| Person 1 | Person 2 | Person 3 | Person 4 |
|---|---|---|---|
| README: setup, running it, where Serverless Jobs runs, where Nano fits in. | README: how the two indexes work, how to reproduce retrieval. | README: how to reproduce the report with one command. Final charts. | README: how to run the dashboard. Verify the public URL survives with nobody connected. |

**All four:** `FEEDBACK.md` for Nebius (seriously, it's a $100 prize with ten winners). Devpost description v0. Final script. Record the external user's clip.

### Weeks 7–8 · Oct 19–27 · Delivery (all four)
- **19–23:** record the video. Edit. Watch it. Re-record. Three minutes, with audio explaining Token Factory and Nemotron (a requirement).
- **24–26:** final Devpost description, final README, rules checklist (section 8).
- **27:** **submit.** The remaining three days are buffer, not plan.

---

## 7. What gets cut, and in what order, if we have to cut
1. A6 automatic archiving
2. A3 abstain → Tavily (loses the bonus, not the project)
3. A5 external user (if one doesn't show up in time, the corpus is just the four of ours)
4. A4 cost panel (replaced by a static chart in the video)

**Never cut:** the two indexes, the per-category report, the toggle, the provenance. Without those there's no project.

---

## 8. Compliance checklist (reviewed October 24)
- [ ] Runtime call to Token Factory (`core/llm.py`) and Serverless Jobs deployed
- [ ] At least one open-source NVIDIA model: Nemotron Nano and Ultra
- [ ] Public repo, Apache 2.0 visible in the About section
- [ ] README with setup and where Nemotron / Token Factory / Serverless Jobs are used
- [ ] Working demo URL that doesn't depend on a team member's laptop
- [ ] Video ≤ 3 min, public on YouTube, with audio about Token Factory and Nemotron, no copyrighted music
- [ ] Everything in English (or translated)
- [ ] Track: Personal AI
- [ ] Feedback on Token Factory, AI Cloud, and NVIDIA tools
- [ ] Tavily: working runtime call (if A3 survived)
- [ ] Builders & Brews city noted, if Devpost confirmed it applies

---

## 9. Next steps: the next 5 days

**Today, Friday the 4th:** decide who is Person 1–4. Project name. Create the repo with a license. All four sign up on Devpost and the Builder Program.

**Saturday the 5th:** everyone reads their module's part of the document and writes, in `docs/<module>.md`, three paragraphs: what it does, what it exposes, what it consumes. That's the contract draft.

**Sunday the 6th:** count emails. Everyone exports their Gmail or counts how many they have. If it adds up to under 2,000, Person 3 looks for a complementary public dataset.

**Monday the 7th:** Person 4 makes the first real call to Token Factory. That's the unlock for everything else. Person 1 pushes `core/schemas.py` v0. Email to Devpost.

**Tuesday the 8th:** video script v0, all four, one hour. Ask the external user.

**Friday the 11th:** first internal demo. Contracts signed.

---

## 10. Working rules (don't change)
- AI for what we already know how to do. Humans for what we want to learn.
- Nobody merges code they can't explain line by line.
- Every module ships its own tests. They test invariants we decide on.
- Every Friday: does what we built this week show up in the video? If not, it gets cut.
- The video is the grade.
