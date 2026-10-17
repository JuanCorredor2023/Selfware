# Integration notes — Person 3 (`agent/`, `eval/`)

**Who this is for:** sections A-E are for Person 1, as the owner of `core/`;
section F is for Person 2, as the owner of `context/`; **section G (9 Oct) is
for all four**, and each item names its owner. Each entry says what the two
sides look like today and proposes **who fixes it**. Nothing here has been
changed unilaterally.

**Status of my lane (9 Oct, working tree, not yet committed):** the whole
evaluation now runs end to end with **one command**, against fakes, with no
network and no budget:

```bash
uv run python -m scripts.run_eval --fake --run <label> --threshold 0.3 \
    --questions <answerable>.jsonl --questions <abstain>.jsonl
# -> .cache/reports/<label>.md
```

New since 4 Oct: the agent goes through `core/llm.call_with_logprobs` and fills
`tier_calls` (acta pending item); `eval/report.py` (paired differences,
bootstrap CI, per-group tables, operational and abstention tables, Markdown);
the harness records `fell_back_to_flat` (F4); `eval/pipeline.py`;
`agent/ask.py`, the entry point for `/ask` (G5). The repo is at **331 tests
passing**, no network calls. Still missing from my lane: `ragas_runner.py`
(blocked by D2/B4/G3), `abstain.py`, `tavily.py`, and any **real** run, which
needs G1 and G2.

**What I compared against.** Sections A-E were written on 22 Sep against branch
`feature/setup-producto-observabilidad`, when `main` held only `README.md`.
**Section F was added on 4 Oct** against `main` at `0f31eaf`, which now contains
`core/`, `context/`, `api/`, `observability/` and `web/`, plus the acta of
2026-09-30. **Section G was added on 9 Oct**, against the same `main` (nobody has
pushed since 30 Sep) plus my uncommitted lane. Items settled since then are **marked in the triage table, not
deleted**: the trail of what the drafts looked like is the reason the table is
readable at all.

**How to read the owner column:**

| Owner | Meaning |
|---|---|
| **P1 → `core/`** | Person 1 changes `core/`; I adapt, no discussion needed |
| **P4 → own code** | Person 4 changes `core/llm.py` or `observability/`; nothing for P1 to decide |
| **Talk first** | The team decides, then each person fixes their own module |
| **Me → `agent/`,`eval/`** | Mine to fix once a decision exists |

---

## Triage summary

`Status` as of **9 Oct**, checked against `main` at `0f31eaf` and my working tree
rather than assumed.

| # | Item | Owner | Priority | Status |
|---|---|---|---|---|
| A1 | `Chunk.score` vs `Chunk.similarity` | P1 → `core/` | **Blocker** | **Closed.** `core/schemas.py` ships `similarity`, documented as higher = more relevant |
| A2 | `Chunk.ts` is `str` vs `datetime` | P1 → `core/` | **Blocker** | **Closed.** `ts: datetime`, with "convert to a string only at the HTTP boundary" |
| A3 | `Answer` has no `finish_reason` | Talk first | **Blocker** | **Closed.** `Answer` carries `finish_reason` |
| A4 | Dataclasses frozen or mutable | P1 → `core/` | Low | **Closed.** `Chunk`/`Question` frozen, `TierCall` mutable so `cost.py` can fill `cost_usd` |
| A5 | `Question` is not in `core/schemas.py` | Talk first | Medium | **Closed.** `Question` is in `core/schemas.py`, all nine fields |
| B1 | `call()` discards logprobs | P4 → own code | **Blocker** | **Closed by P4.** `call_with_logprobs() -> LLMResult`. Mine to adopt |
| B2 | `call()` discards `finish_reason` | P4 → own code | **Blocker** | **Closed by P4.** `LLMResult.finish_reason` |
| B3 | No tier for the judge model | P4 → own code | High | **Closed by P4.** `judge` tier added, plus a `super` tier |
| B4 | RAGAS needs its own clients, outside `core/llm.py` | Talk first | High | **Open.** Blocked behind D2 |
| B5 | Judge cost silently reports $0.00 | P4 → own code | Medium | **Closed by P4.** Acta asks to verify the Qwen3-235B prices |
| C1 | `answer_question(query, strategy)` vs my two-argument function | Talk first | High | **Decided — acta D1, built 9 Oct.** `agent/ask.py`. Rule-1 exception: I implemented option 3 (injection at the edge); **team to confirm**. See G5 |
| C2 | `eval/` imports from `agent/_contracts.py` | P1 → `core/` | Medium | **Closed.** `_contracts.py` deleted, everything imports `core/schemas.py` |
| C3 | `agent/cache.py` is not in the plan layout | Talk first | Low | **Closed.** It is in `main` as `src/selfware/agent/cache.py` |
| C4 | `tests/fakes/` is not in the plan layout | P1 → `core/` | Low | **Closed.** `tests/fakes/` is in `main` |
| D1 | `requirements.txt` vs one `pyproject.toml` | P1 → `core/` | Medium | **Closed.** One `pyproject.toml` + `uv.lock`, no `requirements.txt` |
| D2 | The three RAGAS pins are missing | P1 → `core/` | **Blocker** | **Open, and re-measured today.** `ragas` is in neither `pyproject.toml` nor `uv.lock`. See the rewritten item |
| D3 | `.gitignore` does not cover questions or cache | P1 → `core/` | **Blocker (privacy)** | **Closed.** `questions_sebastian_*.jsonl`, `.cache/` and `chroma_data/` are ignored, with the comments |
| D4 | No PII sweep before a `.md` goes into the repo | Talk first | **Blocker (privacy)** | **Open** |
| E1 | PARA category vocabulary | Talk first | **Blocker** | **Answered, and it is a mismatch.** The classifier emits plural. See F2 |
| E2 | PARA path vocabulary | Talk first | Medium | **Answered.** `para_path` is now the bare folder, no subfolder. See F2 |
| E3 | Prompt and reference answers are in Spanish | Talk first | High | **Open** |
| **F1** | **The query classifier ignores the query** | **P2 → `context/`** | **Blocker** | **Open** |
| F2 | `ParaFolder` is plural, my ground truth is singular | Me → `eval/` | **Blocker** | **Half done.** My fake speaks `ParaFolder`, pinned by a test. Relabelling the questions waits on G6 |
| F3 | `retrieve()` is a method on a class, not a function | Me → `agent/` | High | **Half done.** Built once at the edge (`scripts/run_eval.py`, G5). `chroma_data` path and who ingests: still open, see G2 |
| F4 | `RetrievalResult` carries a field the evaluation needs | Talk first | High | **Closed on my side.** `Retrieved` + `Record.fell_back_to_flat`; the report prints the fallback rate next to every PARA number. Its home: G4 |
| F5 | `Strategy` enum vs the string literal in C2 and `/ask` | Me → `agent/` | Low | **Closed.** `answer_question` rejects anything but `"flat"`/`"para"` before retrieving |
| **G1** | **The embedder is fake: random vectors from a hash** | **P2 → `context/`** (+ P4) | **Blocker** | **Almost closed, 10 Oct.** Real Qwen3-Embedding-8B through `core/llm.embed` (`68bd462`), but `embed()` reads `MODEL_IDS["embedding"]` and the key is `"embedder"`: `KeyError` on the first real call. One-line fix |
| **G2** | **Nothing turns `ingest/` output into `context/` input** | **Talk first** (P1, P2) | **Blocker** | **New, 9 Oct** |
| G3 | `scipy` for Wilcoxon (D18), with the RAGAS pins | P1 → `pyproject.toml` | Medium | **New, 9 Oct** |
| G4 | `Retrieved` and `docs_needed` belong in `core/schemas.py` | P1 → `core/` | Medium | **New, 9 Oct** |
| G5 | `/ask`: my side is ready, a paste for `api/app.py` | P4 → `api/` | High | **New, 9 Oct** |
| **G6** | **All 68 answerable questions are `ai-drafted`** | **Talk first** (all four) | **Blocker** | **New, 9 Oct** |
| G7 | D8 is superseded by Person 2's fallback | Me → my decision log | Low | **Closed, 9 Oct** |

"Blocker" means the evaluation cannot produce a trustworthy number until it is
resolved. Most of them do **not** crash: they produce a plausible wrong number,
which is worse. **As of 9 Oct, G1 matters more than F1**: with a fake embedder
both arms retrieve at random, so not even the flat baseline means anything. The
critical path to a real number is **G1 + G2 + F1 + D2**, none of them in my
lane. My lane can run the full evaluation the hour those land.

---

# A · `core/schemas.py` — data shape

## A1 · `Chunk.score` vs `Chunk.similarity` · P1 → `core/`

```python
# core/schemas.py (draft)        # agent/_contracts.py (mine)
score: float                    similarity: float
```

`P3.md` documents contract C2 with `score` too, so the document needs the same
correction as the code.

**Why it matters.** `score` does not say whether higher is better.
`confidence.py` uses this field as its retrieval signal. If a **distance** ever
arrives in it, the confidence signal is inverted — the system is confident
exactly where it should doubt — and nothing raises. I have a range guard for
`[0,1]`, but a normalised cosine distance falls inside `[0,1]` and passes clean.

**Proposal:** rename to `similarity` in `core/schemas.py` and in `P3.md`.

**Open question for P1:** I recorded this as agreed on 16 Sep. If that agreement
never reached the team, this is the first thing to close.

- [ ] Decided

## A2 · `Chunk.ts` is `str` vs `datetime` · P1 → `core/`

```python
# draft:  ts: str        -> "2026-09-01T00:00:00Z"   (see api/_mock_agent.py)
# mine:   ts: datetime
```

**Why it matters.** `build_prompt()` calls `chunk.ts.strftime()` to put each
chunk's date into the prompt. With a `str` that is an `AttributeError` on the
first real call. The date is in the prompt because a large share of the question
set asks *when* something happened.

**Proposal:** `datetime` in the contract. If serialisation needs a string at the
HTTP boundary, that conversion belongs in `api/`, not in the contract.

- [ ] Decided

## A3 · `Answer` has no `finish_reason` · Talk first

```python
# draft C3:  text, confidence, provenance, used_web, tier_calls
# mine:      text, confidence, provenance, used_web, finish_reason, tier_calls
```

**Why it matters.** D17: anything other than `finish_reason == "stop"` means the
answer was cut off. A truncated answer reads perfectly reasonable until you
compare it in full, and it contaminates the RAGAS average silently.
`eval/harness.py` computes `Record.flagged` from exactly this field.

This is not only mine: without it, `/ask` cannot tell the dashboard whether what
it is showing a judge is complete.

**Note:** `tier_calls` currently defaults to `[]` in my copy, because `TierCall`
is built inside `core/llm.py` and my `answer.py` does not go through it yet (see
C1 and B1). The default is a placeholder, not a design choice.

**Proposal:** `Answer` carries both fields. Depends on B2 — if `core/llm.py`
keeps discarding `finish_reason`, nothing downstream can populate it.

- [ ] Decided

## A4 · Frozen or mutable dataclasses · P1 → `core/`

Mine are `frozen=True` for `Chunk`, `Question` and `Answer`; the draft leaves
everything mutable. A consumer cannot then accidentally modify a chunk another
module is still going to read.

`TierCall` has to stay **mutable**, because `observability/cost.py` does
`tier_call.cost_usd = ...`. That is a legitimate use.

**Proposal:** freeze `Chunk`, `Question` and `Answer`; leave `TierCall` mutable,
or freeze it and have `with_cost()` return a copy via `dataclasses.replace()`.
That second part is between P1 and P4.

- [ ] Decided

## A5 · `Question` is not in `core/schemas.py` · Talk first

Contract C6 says `questions/*.jsonl` is produced by `eval/` and consumed by
everyone, but `Question` is in neither the draft schema nor the plan's file list.
My version has nine fields: `id`, `q`, `expected`, `category`, `evidence`,
`answerable`, `hops`, `source`, `hard_case` (D19, D27, D28).

**Question for the team:** does anything outside `eval/` read the questions? If
yes it is a contract and belongs in `core/`; if no it can live in `eval/`.

- [ ] Decided

---

# B · `core/llm.py` and `observability/` — behaviour

`core/llm.py` is marked `Status: DRAFT -- Person 4, week 1`, so these arrive in
time. Current signature:

```python
def call(tier: Tier, messages: list[dict], **kwargs) -> tuple[str, TierCall]
```

## B1 · `call()` discards the logprobs · P4 → own code

**The precise problem.** `**kwargs` *does* forward `logprobs=True` and
`top_logprobs=5` to `client.chat.completions.create()`. The server returns them.
Then `call()` does:

```python
text = response.choices[0].message.content
return text, tier_call
```

The logprobs arrive and are dropped on that line. **The parameter gets in; the
data does not come back.** It is not a configuration gap, it is the return type.

**Why it matters.** `confidence.py` computes `Answer.confidence` (C3) as the
geometric mean of the per-token probabilities of the answer, cutting at
`</think>` (D14, D24). No logprobs, no confidence; no confidence, no
`abstain.py`; no abstention, no web search and no Tavily prize (D21).

**Proposal — a new function, `call()` untouched** so `api/` and `ingest/` do not
change one line:

```python
@dataclass
class LLMResult:
    text: str
    finish_reason: str
    tokens: list[TokenLogprob]  # .token and .logprob, in order
    tier_call: TierCall


def call_with_logprobs(tier: Tier, messages: list[dict], **kwargs) -> LLMResult: ...
```

**Lower-effort alternative:** a `call_raw()` returning `(response, TierCall)` with
the raw SDK object, and I extract what I need on my side. Ten lines, works for me.

**To be clear about scope:** I ask for `top_logprobs=5` but today only use the
chosen token's `logprob`. The five candidates are for a D24 alternative that has
not been measured. If it simplifies things, `logprobs=True` is enough for now.

- [ ] Decided

## B2 · `call()` discards `finish_reason` · P4 → own code

Same line, same cause as B1: only the text comes back, so
`choices[0].finish_reason` disappears. See A3 for the consequence.

**Supporting evidence, already in Person 4's own code.**
`scripts/e2e_smoke.py` records that at `max_tokens=8` both models were cut off,
at 40 Nano still had not finished, and 200 was needed for it to finish in 65
tokens. The truncation case is real and already observed; what is missing is the
field reaching the consumer.

**Side note on `MAX_TOKENS = 100`.** It is a constant in `e2e_smoke.py`, not a
default of `call()`, so it does not affect me. But per R11: on the real task I
measured ~364 output tokens, of which **95% is reasoning**. If that 100 ever
becomes a library default, Ultra will truncate systematically. Worth keeping it
in the script.

- [ ] Decided

## B3 · No tier for the judge model · P4 → own code

```python
MODEL_IDS = {"nano": ..., "ultra": ...}
Tier = Literal["nano", "ultra"]
```

D12 requires the judge to be a **different model from the generator** — otherwise
the metric measures whether the model agrees with itself. The judge chosen on
20 Sep, verified with a real call, is `Qwen/Qwen3-235B-A22B-Instruct-2507`
(fallback `Qwen/Qwen3-30B-A3B-Instruct-2507`). `eval/ragas_runner.py` needs it.

**Question for P4:** add `"judge"` to `MODEL_IDS` and `Tier`, or stop making the
model catalogue a closed `Literal`? The second is more flexible but loses the
type check that stops a typo'd model id from passing silently.

- [ ] Decided

## B4 · RAGAS builds its own clients, outside `core/llm.py` · Talk first

This one threatens an architecture rule, so it needs the team and not just P4.

RAGAS does not take an OpenAI SDK client. It takes LangChain wrappers, and it
needs embeddings as well as a chat model:

```python
ChatOpenAI(model=JUDGE, api_key=..., base_url=BASE_URL, temperature=0)
OpenAIEmbeddings(model="Qwen/Qwen3-Embedding-8B", api_key=..., base_url=BASE_URL)
```

`core/llm.py` only exposes chat completions. So as things stand,
`eval/ragas_runner.py` would have to construct those two objects with the base
URL itself — and **a grep for `tokenfactory.nebius.com` would find two files, not
one.** The rule is in the plan, in `P3.md` and in `core/llm.py`'s own docstring.

`Qwen/Qwen3-Embedding-8B` is the only embedding model in the catalogue, so
`context/` needs it too — this is not only an `eval/` problem.

**Options, cheapest first:** (a) `core/llm.py` exposes factories that build and
return the two configured LangChain objects, keeping the URL in one file;
(b) `core/llm.py` exports `BASE_URL` and `eval/` imports it, so the literal still
appears once; (c) accept two exit points and write down why.

- [ ] Decided

## B5 · Judge cost silently reports $0.00 · P4 → own code

`observability/cost.py` only prices Nano and Ultra, and its own comment says what
happens otherwise:

> A key that doesn't match falls through to $0.0 in estimate_cost_usd() below,
> silently.

When the full evaluation runs, **every judge call will report zero cost**, and
the dashboard's cost panel — which is part of what the jury sees — will show a
number that is not the real spend.

Same failure family as A1 and E1: it does not crash, it produces a plausible
number.

**Proposal:** add the judge's price, and make `estimate_cost_usd()` raise or log
on an unknown model instead of returning `0.0`.

- [ ] Decided

---

# C · Module boundaries

## C1 · `answer_question(query, strategy)` vs my two-argument function · Talk first

`api/_mock_agent.py` documents the C3 shape Person 4 built `/ask` against:

```python
def answer_question(query: str, strategy: str) -> Answer      # P4 expects
```

Mine is:

```python
make_answerer(client, model, cache_dir, ...) -> Callable[[str, list[Chunk]], Answer]
```

**The real difference.** Person 4's version receives `strategy` and assumes
`agent/` does its own retrieval. Mine receives the chunks already retrieved and
lets the caller decide where they come from. That was deliberate: the harness
injects `retrieve` and `answer`, which is why `eval/` is testable end to end with
no network and no budget (R6), and why Person 2's real `retrieve()` drops in
without touching my module.

**This also involves Person 2**, because the question is who calls `retrieve()`:

- If `agent/` calls it, then `agent/` imports from `context/`, which breaks the
  monolith rule ("no module imports from another except `core/`").
- If `api/` calls it, the rule holds but `/ask` becomes two steps.

**Proposal:** keep my two-argument function as the network-free core, and expose
an `answer_question(query, strategy)` wrapper on top that does both steps. Then
`/ask` changes one line as Person 4 planned, and `eval/` stays testable. What is
left to decide is which module that wrapper lives in.

- [x] **Decided — acta of 2026-09-30, decision D1.** `retrieve()` is called by
  `agent/`, because the agent is what reasons about whether the query was
  actually resolved by what retrieval returned. The adapter Person 4 had
  proposed inside `api/` is dropped. The proposed signature is
  `answer_question(query, strategy) -> Answer`, listed in the acta as **still to
  confirm** -- so the wrapper is mine and it lives in `agent/`, which is the half
  of this item that was open.

**One consequence nobody has written down yet.** Of the two options above, D1
picked the one I flagged as breaking architecture rule 1 of `P3.md`: *"no module
imports from another except `core/`"*. For `agent/` to call `retrieve()` it has
to import `selfware.context`, and `context/` is not `core/`. Three ways out, and
I do not think this is mine to pick alone:

1. **Accept the exception and write it down.** `agent/ → context/` is allowed,
   justified by D1, recorded as an amendment to rule 1. Cheapest, and honest.
2. **Lift the seam into `core/`.** `core/` declares a `Retrieval` protocol that
   `context/` implements and `agent/` depends on. The rule survives intact, at
   the cost of a third file to keep in sync.
3. **Inject it at the edge.** `agent/` never imports `context/`; whoever builds
   the agent (`api/app.py`) passes `retrieve` in. The rule survives, the import
   moves to `api/`, and `eval/` keeps using the fake with no changes.

**My preference is 3**, because it is what `make_answerer` already does with the
LLM client and what keeps the harness network-free (R6). But rule 1 is a team
rule, so it is a team call.

- [ ] Rule-1 exception decided

## C2 · `eval/` imports from `agent/_contracts.py` · P1 → `core/`

`eval/harness.py` currently does:

```python
from agent._contracts import Answer, Chunk, Question
```

**That breaks the monolith rule, and I know it.** `agent/_contracts.py` is a
provisional local copy of the types that belong in `core/schemas.py`, marked
`PROVISIONAL` at the top of the file. I chose one shared copy over two copies
because two definitions of the same contract drifting apart in silence is the
failure family of A1 and E1.

**Action at integration:** delete `agent/_contracts.py` and point both
`agent/*.py` and `eval/harness.py` at `core.schemas`. That is the whole fix —
five import lines. Grep for `_contracts` to find them all.

- [ ] Done at integration

## C3 · `agent/cache.py` is not in the plan layout · Talk first

The plan lists `agent/{answer,confidence,abstain,tavily}.py` and
`eval/{harness,ragas_runner,report}.py`. `cache.py` (D16, on-disk response cache)
is in neither.

Today its only consumer is `answer.py`, so `agent/cache.py` is the natural home.
But if `ragas_runner.py` later wants to cache judge verdicts — and D12 says the
judge is a different model, so a different key — it would end up importing from
`agent/`, which breaks the same rule as C2.

**Question:** accept `agent/cache.py` and that risk, or move it to `core/` in the
same PR that settles the contracts?

- [ ] Decided

## C4 · `tests/fakes/` is not in the plan layout · P1 → `core/`

The plan has `tests/{ingest,context,agent,eval,api}/`. I added `tests/fakes/`
holding `retrieve_fake.py`: a deterministic, hash-based stand-in for Person 2's
`retrieve()` that satisfies C2's invariants with no network, so the harness runs
end to end today (R6). It is scaffolding and produces no project results.

Nothing to decide beyond accepting the directory.

**Already aligned:** `tests/__init__.py` exists on both branches, which matters —
without it, `tests/agent/` shadows the top-level `agent/` package on `sys.path`
and every import fails.

- [ ] Accepted

---

# D · Repo plumbing

## D1 · `requirements.txt` vs one `pyproject.toml` · P1 → `core/`

The plan says "a single `pyproject.toml`". The branch carries `requirements.txt`
and no `pyproject.toml`. My lab used `uv` with a `pyproject.toml`. One has to win.

My code needs, beyond the standard library: `openai`, `python-dotenv`, `ragas`,
`langchain-community`, `pillow`, and `pytest` for tests. `agent/confidence.py`,
`agent/cache.py` and the test doubles need **nothing external at all**.

- [ ] Decided

## D2 · The three RAGAS pins are missing · P1 → `core/`

**Still open, and the only one of the D items that is.** `pyproject.toml` has no
`ragas`, and `uv.lock` has no `ragas` either, so the evaluation half of this
project currently cannot run at all. `requires-python` also moved to `>=3.14`,
which was worth re-checking: the pins below were measured on 3.11.

**Re-measured on 4 Oct against Python 3.14**, with `uv pip compile`, so these are
resolver output and not recollection. The good news first: `ragas` resolves on
3.14, 92 packages, nothing exotic. The three pins all survive, and the mechanism
behind the first one is **exactly** the one written here two weeks ago -- only the
version numbers moved:

| Pin | Why, verified today |
|---|---|
| `ragas==0.3.1` | Unconstrained, the resolver picks `ragas==0.4.3`, which pulls `instructor==1.17.0`, and **`instructor` caps `openai` at `3.3.0`**. Add `openai>=3.22` as a floor and the resolver drops back to `ragas==0.3.1` on its own, with `openai==3.24.0`. The repo runs `openai 3.22.1` today, and `core/llm.py` is built on it. The cap is no longer `openai<2.0.0` as it was in September, but it is the same `instructor` dependency doing the same thing |
| `langchain-community<0.4` | Still required, and **the resolver will not protect you**: with `ragas==0.3.1` pinned it still happily resolves `langchain-community==0.4.2`. The breakage is an import of `langchain_community.chat_models.vertexai` at runtime, which no resolver can see |
| `pillow` | Still required. Absent from the `ragas==0.3.1` resolution entirely; it only appears via `ragas==0.4.3`, which declares it. 0.3.1 imports `PIL` without declaring it |

So the choice is a real one, not a formality: **`ragas==0.3.1` with `openai` on
3.x**, or `ragas==0.4.3` and `openai` pinned down to `3.3.0` for the whole repo,
including `core/llm.py` and `call_with_logprobs()`. I want the first, because
capping the SDK that every lane calls through, to suit the evaluation library, is
the tail wagging the dog.

Anyone who sees `langchain-community<0.4` in a month will want to upgrade it and
will break the whole evaluation. The explanation has to travel with the pin.

- [ ] Decided

## D3 · `.gitignore` does not cover questions or cache · P1 → `core/`

The branch's `.gitignore` covers `__pycache__`, `*.pyc`, `.venv/`, `venv/`,
`.env` and `.pytest_cache/`. It does **not** cover the question sets or the
response cache.

My question corpus is derived from my own Gmail: it carries real sender
addresses, amounts, a partial bank account number, and six rows flagged
`pii: true` (R9). The cache cannot ship either — the key is derived from the full
prompt, and the prompt contains the question.

Two lines, with the comment that explains them:

```gitignore
# Questions derived from personal email (R9, D26). The pattern is deliberately
# specific: questions_enron_*.jsonl or others from the public corpus DO get
# versioned.
questions_sebastian_*.jsonl

# Model response cache (D16). The payload is not the problem: the KEY derives
# from the prompt, and the prompt contains the question.
.cache/
```

This is the one item on the list with a consequence that cannot be undone after
the fact: the repo is public.

- [ ] Decided

## D4 · No PII sweep before a `.md` goes into the repo · Talk first

D3 closes the door the corpus would walk through. This one closes the door
**people** walk through, and it is the one we are actually more likely to leave
open.

**The pattern.** Personal data does not only leak through the obvious files that
`.gitignore` already covers. It leaks through **examples** — when someone is
making a technical point and reaches for the nearest real datum to illustrate it.
The file is legitimate, the point is legitimate, and the example is a receipt
number.

**Two real instances, both mine, both found in the last hour:**

1. **In this file.** Item E3 argues that the reference answers are in Spanish.
   The first draft illustrated that with two literal `expected` values from
   questions flagged `pii: true` — a food-delivery amount and a store branch.
   It was caught on review and replaced with a description of the *format*. The
   argument survived intact, which is the point: the real value was never
   needed.
2. **In `DECISIONES.md`.** The D31 table quotes a real receipt reference number
   from my own invoices, as an example of how `faithfulness` scores two phrasings
   differently. That file is not in the repo yet. If it ever goes in — and there
   is a good case for it, it is the clearest evidence of rigour the project has —
   that line has to be scrubbed first. **Mine to fix.**

Neither of these is the corpus. Both are single facts, in prose, written by a
person who had just finished writing the rule they were breaking.

**Proposal — a convention, not a gate.** Before any `.md`, docstring or test
fixture is committed, grep it and *look at every hit*. Most will be false
positives; that is fine, the point is that a human looks:

```bash
grep -nEi '\$[0-9]+\.[0-9]{2}|[0-9]{4}-[0-9]{4}-[0-9]{4}|\*\*[0-9]{4}|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' -- '*.md' '*.py'
```

Amounts, reference numbers, masked account digits, email addresses. Add vendor
and person names as we find them.

**Why it is worth a line in a document rather than just good intentions:** the
four of us are writing a README, a video script, a FEEDBACK.md and a public
report, all about a system whose input is our own mail. Every one of those
documents will want a concrete example.

**Scope question for the team:** does this apply only to `.md`, or also to test
fixtures? My vote is both — a fixture that hard-codes a real amount or reference
number as its `expected` value is the same leak with a `.py` extension.

**One more data point on how easy this is.** The paragraph above originally
illustrated that sentence by quoting the same amount this item had just been
written to remove — third occurrence in one hour, inside the item about not doing
it. That is why the proposal is a grep and not a reminder to be careful. Being
careful is what failed.

- [ ] Decided

---

# E · String vocabularies — the silent ones

None of these crashes. All of them produce a believable wrong number.

## E1 · PARA category vocabulary · Talk first

There are **two different PARA labels**: the one I hand-write on each question
(the ground truth) and the one `ingest/`'s classifier emits (which drives the
PARA arm's filter). I use **`project` / `area` / `resource`**, singular, English.

If the classifier emits `projects`, or Spanish, or capitalised, the PARA filter
finds nothing, D8 returns `[]`, the system abstains on all 56 questions, and the
report concludes **"PARA destroys retrieval"** when the cause was one letter.

**This duplicates**, because there are now two classifiers: emails (Person 1) and
questions (Person 2, confirmed 20 Sep — see R17). They can disagree with each
other *and* with my hand-written `category`.

**What I need:** the exact string each classifier emits, in writing. Then we
measure real agreement on a sample.

**Data for Person 1 (R7):** across 68 answerable questions from my inbox the
split is 26 `resource`, 30 `area`, 12 `project`, **0 `archive`**. The archive
drawer is empty, so PARA splits in three, not four. I need the counts from the
other three inboxes.

- [x] **Answered on 4 Oct, and it is a mismatch.** `context/domain.py` defines
  `ParaFolder` with the values `projects` / `areas` / `resources` / `archive`:
  **plural**. Mine are singular. This is the "one letter" scenario above, no
  longer hypothetical. The migration is mine and it is cheap -- see **F2**, where
  I also say why I am not asking for the enum to change.

## E2 · PARA path vocabulary · Talk first

Separate from E1 and easy to confuse with it. `para_path` values I have seen in
the repo look like `projects/mock-project`; mine in the test double are
`projects/atlas`, `areas/finance`, `resources/newsletters`, `archive/2026`.

Two vocabularies coexisting (singular category, plural path with a subfolder) is
fine. Nobody having written down which is which is not.

- [x] **Answered on 4 Oct.** `Chunk.to_contract()` sets
  `para_path = source.para_folder.value`, so a real `para_path` arriving at my
  module is now the **bare folder** -- `"projects"`, not `"projects/atlas"`. The
  subfolder level does not exist in the data.

  **The blast radius is small, by an earlier decision.** `para_path` is
  deliberately kept out of the prompt in `agent/answer.py` -- it is the label
  under test -- and `grep para_path src/selfware/agent src/selfware/eval` finds
  that comment and nothing else. No code of mine parses it, so nothing silently
  breaks.

  What is wrong is my **test double**: `PARA_PATHS` holds `projects/atlas`,
  `areas/finance`, `resources/newsletters`, `archive/2026`, and its filter does
  an exact membership test on them. So the harness's PARA arm is exercised today
  against a folder vocabulary that does not exist in production, and
  `archive/2026` -- my deliberately empty folder for the D8 abstention path --
  becomes plain `archive`. Mine to fix in `tests/fakes/retrieve_fake.py`, in the
  same pass as F2.

  Worth knowing for Person 4 too: `api/_mock_para.py` and the front end show a
  `projects/mock-project` shape, which real chunks will not have.

## E3 · The prompt and the reference answers are in Spanish · Talk first

All of my code is in English. Three strings are deliberately **not**: the system
prompt in `agent/answer.py`, its two section labels, and the abstention sentinel
value. They are experiment data, not prose, and translating them costs three
things:

1. **It invalidates the cache.** The prompt is part of the cache key (D16), so
   translating it kills all cached entries and the run has to be paid again.
2. **It breaks the evaluation.** The `expected` answers of my 66 questions are
   written in Spanish — dates spelled out as `"28 de agosto de 2026"`, answers
   that open with `"Sí, ..."`, amounts with a Spanish decimal reading. A model
   answering in English would be judged by RAGAS against Spanish references, and
   `context_recall` and `faithfulness` would degrade without anything failing.
3. **It invalidates the R18 measurement.** The sentinel's 0-of-8 false positives
   were measured with this exact wording.

This interacts with D26 (public corpus): if validation runs on Enron, that corpus
is in English and will need its own prompt and its own references anyway. Worth
deciding once, for both corpora, rather than twice.

- [ ] Decided

---

# F · `context/retrieve()` — the real contract vs C2

**Who this is for:** Person 2, as the owner of `context/`. Sections A-E were
written against drafts. This one is written against code that is merged in
`main` (`src/selfware/context/`), and by decision D1 of the acta the module that
calls `retrieve()` is mine — so these are the five things I hit the moment I
wire it in. One of them is a blocker; three of the five are mine to fix.

## F1 · The query classifier ignores the query · Blocker · P2 → `context/`

`classifier.py`, in full — nine lines:

```python
class Classifier:
    def __init__(self, category_to_return: ParaFolder):
        self.category_to_return = category_to_return

    def classify_query(self, query: str) -> ParaFolder:
        return self.category_to_return
```

`query` is accepted and discarded. The folder is fixed at construction time, and
`grep -rl classify src/` finds no other implementation in the repo.

**Why this outranks everything else in this document.** `retrieve(strategy="para")`
calls `classify_query` to choose the folder it filters on. With a constant
classifier the PARA arm has exactly two behaviours:

- the answer happens to live in the hard-coded folder → PARA looks excellent;
- it does not → `search_filtered` finds nothing, `fell_back_to_flat` goes `True`,
  and PARA **is** flat with extra steps.

Either way H1 measures the hard-coded constant, not PARA. And it measures it
quietly: no exception, no empty report, just a number with a confidence interval
that means nothing. That is the definition of Blocker in this document, and this
is the cleanest example of it in the whole project.

**The trap I want named before someone walks into it.** The constructor takes the
category to return, and my `Question` already carries a `category` field holding
the right answer. So this line is available, and it type-checks, and it makes
every number beautiful:

```python
Classifier(question.category)  # DO NOT
```

That hands the PARA arm the answer sheet. It is ground-truth leakage straight
into retrieval, it would make PARA beat flat on every question, and the result
would be worthless in a way that is almost impossible to spot from the report
alone. If a real classifier is not ready in time, the honest fallback is to
**report the flat arm only** and state that the PARA arm is not yet measurable.
A missing number is a result. A leaked one is not.

**What I need:** either a `classify_query` that reads `query`, or an explicit
team decision that H1 ships measured against a named stand-in. I am not going to
write a classifier inside `agent/` to work around this — it is your module, and
two classifiers disagreeing is already item E1.

- [ ] Decided

## F2 · `ParaFolder` is plural, my ground truth is singular · Blocker · Me → `eval/`

This answers E1. Run, not remembered:

```python
>>> [f.value for f in ParaFolder]
['projects', 'areas', 'resources', 'archive']
```

My 68 hand-written questions label `category` as **`project` / `area` /
`resource`**, singular. `Question.category` is what sorts questions into the
per-category report, and `ParaFolder.value` is what reaches `para_path` through
`Chunk.to_contract()`. Two vocabularies, one comparison.

**This one is mine and I am not asking you to change the enum.** Four plural
strings match the PARA literature, and `api/_mock_para.py`, the `/projects`
`/areas` `/resources` `/archive` endpoints and the front end all already speak
plural. Mine is the minority spelling; mine moves.

**What I need from you:** confirmation that `ParaFolder.value` is the vocabulary
of record and is not going to change again — before I rewrite 68 labels, not
after.

- [ ] Confirmed

## F3 · `retrieve()` is a method on a class, not a function · High · Me → `agent/`

Contract C2 as written in `P3.md`:

```python
retrieve(query: str, strategy: Literal["flat","para"], k: int) -> list[Chunk]
```

What is merged:

```python
Retrieve(store, classifier).retrieve(query, strategy: Strategy, k) -> RetrievalResult
```

**This is not a complaint.** A class is the right shape when there is a
persistent client behind it. It is a note that somebody now has to own a
lifetime, and that somebody is me:

```python
embedder = Embedder(...)
store = ChromaStore(embedder, path="chroma_data")  # opens a PersistentClient
classifier = Classifier(...)  # see F1
retrieve = Retrieve(store, classifier)
```

`ChromaStore.__init__` opens a `PersistentClient` on a path, so it is built
**once per process, not once per query**. A harness that builds it inside the
loop would open it 136 times for one run (68 questions × 2 arms) — which is the
kind of thing that works on a laptop and falls over in the demo.

**What I will do unless told otherwise:** build the three objects once, at the
edge, and keep injecting the seam — the same pattern `make_answerer` already uses
for the LLM client. `eval/` keeps using `tests/fakes/retrieve_fake.py`, so the
harness stays runnable with no Chroma, no ingest and no budget (R6). See the
rule-1 discussion in C1 for where that wiring should physically live.

**What I need:** the `path` convention (`chroma_data` relative to the repo root?
it is `.gitignore`d, so each of us has our own) and who runs the ingest that
fills the collection before an evaluation. An empty collection and a broken
filter both look like `[]` to me.

- [ ] Decided

## F4 · `RetrievalResult` carries a field the evaluation needs · High · Talk first

`retrieve()` returns `RetrievalResult`, not `list[Chunk]`. Adapting is one line,
and I want to be clear that the adapter you wrote is exactly right:

```python
chunks = [c.to_contract() for c in result.chunks]
```

`Chunk.to_contract()` maps `score` to `similarity` in [0,1] — the store already
converts cosine distance `d` to `1 - d/2` — and `ts` to a `datetime`. That closes
A1 and A2 from my side, in the direction I asked for, with the invariant written
in the docstring. Thank you for that.

**But flattening to a list throws away `fell_back_to_flat`, and that field is the
most valuable thing in the object.** It says: *on this question the PARA arm
found nothing in the folder it chose and served flat results instead.* A
PARA-vs-flat comparison that averages those questions in is not comparing PARA
against flat — it is comparing flat against a blend of PARA and flat, and the
measured effect shrinks toward zero for a reason that has nothing to do with H1.
Given F1, that rate could be most of the set.

**Proposal:** the harness records `fell_back_to_flat` and `query_category` per
question next to the metrics, and the report prints the **fallback rate beside
every PARA number**. A high rate is then a finding about the classifier, not a
verdict on PARA. This is what keeps the headline result honest, and it is also
the cheapest insurance against reporting "PARA does not help" when what happened
was that PARA never ran.

The change is inside `eval/`, so it is mine to make. I am flagging it because it
changes what the harness records, and those records are what the report and the
`/cost` strip read.

- [ ] Decided

## F5 · `Strategy` enum vs the string literal in C2 and `/ask` · Low · Me → `agent/`

C2, `/ask` and the front end all speak `"flat"` / `"para"` as plain strings;
`retrieve()` is typed `strategy: Strategy`. It happens to work:

```python
>>> "flat" == Strategy.FLAT
True
```

because `Strategy` subclasses `str`, and `RetrievalResult.__post_init__`
validates with `==`, so a raw string passes that too. Nothing is broken today —
by a property of the declaration rather than by intent.

I will coerce explicitly at my boundary, `Strategy(strategy)`, instead of leaning
on it. The day `Strategy` stops inheriting from `str`, the failure is then a loud
`ValueError` at the edge and not a filter that silently matches nothing.

- [ ] Noted

---

# G · What building the end-to-end run uncovered (9 Oct)

**Who this is for:** all four; each item names its owner. Between 7 and 9 Oct I
built my lane end to end against fakes (see the status at the top), and wiring
it to the real pieces surfaced these. Two are blockers on the critical path and
neither is in my lane.

## G1 · The embedder is fake: random vectors from a hash · Blocker · P2 → `context/` (+ P4)

`context/embedder.py`, `_to_embedding`, verbatim:

```python
hash_obj = hashlib.sha256(raw_document.encode("utf-8"))
res_hex = hash_obj.hexdigest()
seed = int(res_hex, 16)

rng = random.Random(seed)

embedding: list[float] = [rng.random() for _ in range(self.dimensions)]
```

The vector is a function of the exact bytes of the text and of nothing else, so
two texts that mean the same thing are as far apart as two that do not. The
cosine between a question and an email is **noise**.

**This is not a bug, and it is documented.** Person 2's
`docs/decisiones_carril_context (2).md` says the fake validates "plomería ... no
relevancia" (plumbing, not relevance; my translation) and plans MiniLM, then a
production embedder. The point of this item is only its **rank**: it outranks F1. A constant
classifier breaks the PARA arm; a random embedder breaks **both** arms, so not
even the flat baseline means anything. Any number produced before this changes
is not a result, whatever the classifier does.

**One decision rides on it, and it touches Person 4.** If the production
embedder is `Qwen/Qwen3-Embedding-8B` on Token Factory (on 14 Sep it was the
only embeddings model in the catalog), the calls must go
through `core/llm.py` (rule 2), which today has no embeddings function. That is
item 2 of "Pendientes para la junta" in Person 2's own decision log ("¿los
embeddings entran por el mismo `core/llm.py` o por una puerta aparte?"). Worth
settling before writing either side.

- [ ] Embedder chosen, and where its calls live

## G2 · Nothing turns `ingest/` output into `context/` input · Blocker · Talk first (P1, P2)

What each side has today:

| | Produces / expects |
|---|---|
| `ingest/gmail.py` (P1) | writes `emails.json`: `{id, ts, subject, body}` per message |
| `ChromaStore.add_documents` (P2) | expects `Document(source_id, source, content, category, date)` |
| Contract C1 | `ContextItem(id, source, text, ts, hash, para_path, meta)` |

Three gaps between them, none of them big, all of them unowned:

1. **No PARA category.** The Nano classification of emails (plan, week 2 of
   Person 1) is not in the repo, and `Document.category` has to come from
   somewhere. With no category, the PARA filter has nothing to filter on.
2. **No converter.** Nothing reads `emails.json` and calls `add_documents`, and
   `ContextItem` (C1) is not produced or consumed by anyone.
3. **No dedup by hash** yet (plan, week 2), which `sd-p11` was written to catch.

**What I need:** a name next to "who fills the collection before an evaluation",
and the `chroma_data` path convention (F3). An empty collection and a broken
filter both look like `[]` to me.

- [ ] Owner of the email → classified `Document` → Chroma pipeline

## G3 · `scipy` for Wilcoxon (D18), with the RAGAS pins · Medium · P1 → `pyproject.toml`

D18 promises a paired bootstrap CI **and** a Wilcoxon signed-rank test. The
bootstrap is done in pure standard library (`eval/report.py`). Wilcoxon needs
`scipy`, which is not in `pyproject.toml` (it is not even a transitive
dependency today). Since `pyproject.toml` is going to be touched anyway for the
three RAGAS pins of D2, I am asking for both in the same PR. `numpy` is
installed only because `chromadb` pulls it in; I do not rely on it.

- [ ] `ragas==0.3.1`, `langchain-community<0.4`, `pillow`, `scipy` added, with the
  D2 explanation next to the pins

## G4 · `Retrieved` and `docs_needed` belong in `core/schemas.py` · Medium · P1 → `core/`

Two shapes that are contract material and today live in my lane only because I
cannot write to `core/`:

1. **`Retrieved(chunks, fell_back_to_flat, query_category)`**, in
   `eval/harness.py`. It is what F4 asked for: C2 as the real retriever returns
   it. Because it lives in `eval/`, `agent/` cannot import it (rule 1), so
   `agent/ask.py` asks for a plain `list[Chunk]` instead and the edge adapts with
   `.chunks`. In `core/` both would share one type, and the strategy strings
   (`"flat"`, `"para"`, today repeated in `eval/harness.py` and `agent/ask.py`)
   could live next to it.
2. **`docs_needed: int | None`** on `Question` (D36). It is already in the JSONL
   files; `load_questions` ignores it because it is not in the contract. Without
   it the report cannot separate questions that are **impossible** with `k=5`
   (`sd-a17`, `sd-a31`) from hard ones, and the `hops` table averages both.

Moving `Retrieved` changes one import on my side. I will do it the day it lands.

- [ ] Agreed, and in a `core/` PR

## G5 · `/ask`: my side is ready, a paste for `api/app.py` · High · P4 → `api/`

`agent/ask.py` exposes the function the acta (D1) asked for:

```python
make_answer_question(retrieve, answer, k=5) -> answer_question(query, strategy) -> Answer
```

It validates `strategy` (F5), retrieves, answers, and returns the agent's
`Answer` untouched -- `tier_calls` included, now filled for real, so `/cost`
gets real numbers from the first real question.

**How I solved the rule-1 question from C1:** option 3. `agent/` imports nothing
from `context/`; whoever builds the app passes `retrieve` in. For the evaluation
that place is `scripts/run_eval.py`, which is not a module of the monolith. For
the API it is `api/app.py`. **If the team prefers option 1 or 2, it is a small
change; this is the one I am asking you to confirm.**

What to paste the day real data exists, replacing the mock import (the
`Retrieve` object built **once per process**, F3):

```python
from pathlib import Path

from selfware.agent.answer import make_answerer
from selfware.agent.ask import make_answer_question
from selfware.context.domain import Strategy

answer_question = make_answer_question(
    retrieve=lambda q, s, k: [
        c.to_contract() for c in person_2_retrieve.retrieve(q, Strategy(s), k).chunks
    ],
    answer=make_answerer(Path(".cache")),
)
```

Until then, keep the mock: with G1 open, real answers would be built on random
retrieval.

- [ ] Option 3 confirmed
- [ ] Pasted (integration step 11)

## G6 · All 68 answerable questions are `ai-drafted` · Blocker · Talk first (all four)

Running the first end-to-end report against my real question files printed this
in the `by source` table:

| group | n |
|---|---:|
| ai-drafted | 68 |

No `human` group at all. Two consequences:

1. **The plan says "Not AI-generated"** (section 5, evaluation questions).
2. **D27's control cannot run.** D27 accepts AI-drafted questions only together
   with a check that the flat-vs-PARA difference **holds in both subsets**,
   because a question drafted from an email inherits its vocabulary and makes
   retrieval easy in both arms (ceiling effect). With one subset there is
   nothing to compare.

There is a second question about the same files that I have not resolved: **where
a question's `category` comes from.** I labelled them by hand. D20.5 says "the
drawer where the answer lives" -- but in the real system that drawer is the
`para_path` Person 1's classifier assigns to the evidence email, which may not
match my label. Two sources of truth for the same field.

**What I propose:** a short session, before any real run, on the question
format: where `category` comes from, how many `human` questions we need for D27,
and the state of the 50-per-person questions (C6) -- I have only seen mine.

- [ ] Session held; format and sources decided

## G7 · D8 is superseded by Person 2's fallback · Low · Closed

D8 (14 Sep, mine) said `retrieve("para")` returns an empty list when the filter
leaves the folder empty, precisely so the report would not mix PARA and flat
without telling them apart. Person 2 implemented the opposite -- fall back to
flat -- **and** flags it with `fell_back_to_flat`. Since the harness now records
that flag and the report prints the fallback rate next to every PARA number
(F4), the reason for D8 is covered without D8. I adopted the fallback: my fake
mirrors it, and my decision log marks D8 as superseded.

---

# Two things that are not divergences

Recording them so nobody spends time on them.

**My tests never call Token Factory.** No network, no API key read: the function
that talks to Token Factory is received as a parameter (`llm_call`) and the tests
pass a toy one. The repo is at **331 passing**; run them with `uv run pytest`
from the repo root.

**The cache keys did not move during the port.** I verified that `build_prompt`
and `cache_key` produce byte-identical output to my lab version across 2000
combinations, so the 53 cached responses from before the migration are still
valid. If anyone edits the prompt text, that stops being true — see E3.
