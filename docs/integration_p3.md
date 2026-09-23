# Integration notes — Person 3 (`agent/`, `eval/`)

**Who this is for:** Person 1, as the owner of `core/`, to triage one item at a
time. Each entry says what the two sides look like today and proposes **who
fixes it**. Nothing here has been changed unilaterally.

**Status of my branch (`p3/agent-eval`):** `agent/confidence.py`, `agent/answer.py`,
`agent/cache.py`, `eval/harness.py` and the test doubles are in, with 86 tests
passing and no network calls. Still missing: `abstain.py`, `tavily.py`,
`ragas_runner.py`, `report.py`, `eval/questions/`.

**What I compared against:** branch `feature/setup-producto-observabilidad`
(`core/schemas.py`, `core/llm.py`, `api/_mock_agent.py`, `observability/cost.py`,
`requirements.txt`, `.gitignore`), the contracts in `P3.md`, and the repo layout
in the plan. `main` only has `README.md`, so that branch is the only place
`core/` currently exists.

**How to read the owner column:**

| Owner | Meaning |
|---|---|
| **P1 → `core/`** | Person 1 changes `core/`; I adapt, no discussion needed |
| **P4 → own code** | Person 4 changes `core/llm.py` or `observability/`; nothing for P1 to decide |
| **Talk first** | The team decides, then each person fixes their own module |
| **Me → `agent/`,`eval/`** | Mine to fix once a decision exists |

---

## Triage summary

| # | Item | Owner | Priority |
|---|---|---|---|
| A1 | `Chunk.score` vs `Chunk.similarity` | P1 → `core/` | **Blocker** |
| A2 | `Chunk.ts` is `str` vs `datetime` | P1 → `core/` | **Blocker** |
| A3 | `Answer` has no `finish_reason` | Talk first | **Blocker** |
| A4 | Dataclasses frozen or mutable | P1 → `core/` | Low |
| A5 | `Question` is not in `core/schemas.py` | Talk first | Medium |
| B1 | `call()` discards logprobs | P4 → own code | **Blocker** |
| B2 | `call()` discards `finish_reason` | P4 → own code | **Blocker** |
| B3 | No tier for the judge model | P4 → own code | High |
| B4 | RAGAS needs its own clients, outside `core/llm.py` | Talk first | High |
| B5 | Judge cost silently reports $0.00 | P4 → own code | Medium |
| C1 | `answer_question(query, strategy)` vs my two-argument function | Talk first | High |
| C2 | `eval/` imports from `agent/_contracts.py` | P1 → `core/` | Medium |
| C3 | `agent/cache.py` is not in the plan layout | Talk first | Low |
| C4 | `tests/fakes/` is not in the plan layout | P1 → `core/` | Low |
| D1 | `requirements.txt` vs one `pyproject.toml` | P1 → `core/` | Medium |
| D2 | The three RAGAS pins are missing | P1 → `core/` | **Blocker** |
| D3 | `.gitignore` does not cover questions or cache | P1 → `core/` | **Blocker (privacy)** |
| D4 | No PII sweep before a `.md` goes into the repo | Talk first | **Blocker (privacy)** |
| E1 | PARA category vocabulary | Talk first | **Blocker** |
| E2 | PARA path vocabulary | Talk first | Medium |
| E3 | Prompt and reference answers are in Spanish | Talk first | High |

"Blocker" means the evaluation cannot produce a trustworthy number until it is
resolved. Most of them do **not** crash: they produce a plausible wrong number,
which is worse.

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
    tokens: list[TokenLogprob]   # .token and .logprob, in order
    tier_call: TierCall

def call_with_logprobs(tier: Tier, messages: list[dict], **kwargs) -> LLMResult:
    ...
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

- [ ] Decided

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

`requirements.txt` says `openai` with no version, and does not mention `ragas`,
`langchain-community` or `pillow`. These three pins have to reach the team file
**with their explanation**, or the evaluation stops running and nobody will know
why (D30):

| Pin | Why |
|---|---|
| `ragas==0.3.1` | From `0.3.9` it depends on `instructor`, which pins `openai<2.0.0`. All of `answer.py` runs on `openai>=3.13`. This is what the resolver produces, not a preference |
| `langchain-community<0.4` | 0.3.1 imports `langchain_community.chat_models.vertexai`, which 0.4 removed |
| `pillow` | 0.3.1 imports `PIL` without declaring it |

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

- [ ] Decided

## E2 · PARA path vocabulary · Talk first

Separate from E1 and easy to confuse with it. `para_path` values I have seen in
the repo look like `projects/mock-project`; mine in the test double are
`projects/atlas`, `areas/finance`, `resources/newsletters`, `archive/2026`.

Two vocabularies coexisting (singular category, plural path with a subfolder) is
fine. Nobody having written down which is which is not.

- [ ] Decided

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

# Two things that are not divergences

Recording them so nobody spends time on them.

**My tests never call Token Factory.** 86 tests, no network, no API key read. The
SDK client is received as a parameter and the tests pass a toy one. Run them with
`python -m pytest tests/` from the repo root.

**The cache keys did not move during the port.** I verified that `build_prompt`
and `cache_key` produce byte-identical output to my lab version across 2000
combinations, so the 53 cached responses from before the migration are still
valid. If anyone edits the prompt text, that stops being true — see E3.
