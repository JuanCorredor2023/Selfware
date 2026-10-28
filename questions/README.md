# Evaluation questions: Enron

Public validation set for H1 (D26): does filtering retrieval by PARA folder beat a
flat vector index over the same mailbox, per question category?

The team target is **125 questions per custodian** (100 answerable + 25 unanswerable),
four custodians, 500 in total. `kitchen-l` and `farmer-d` are in progress (Person 2).

| File | Questions |
|---|---|
| `enron_kaminski-v.jsonl` | 200 answerable: 67 `projects`, 67 `areas`, 66 `resources`. One evidence email each, all different |
| `enron_kaminski-v_100.jsonl` | The 100 of the 125 set: a stratified subsample of the 200 (34 / 33 / 33) |
| `enron_kaminski-v_abstain.jsonl` | 25 unanswerable (D21): plausible for this mailbox, answer not in the corpus |
| `enron_shapiro-r.jsonl` | 100 answerable: 34 `projects`, 33 `areas`, 33 `resources` |
| `enron_shapiro-r_abstain.jsonl` | 25 unanswerable |

The corpus is **not** in this repo: these files hold the questions only.

## Reproduce

```bash
# 1. The corpus (public, ~423 MB compressed). Keep it outside the repo.
mkdir -p ~/dev/atlas-lab/enron && cd ~/dev/atlas-lab/enron
curl -O https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz
tar -xzf enron_mail_20150507.tar.gz
cd -

# 2. Extract one custodian: owner folders only, quoted thread cut, deduplicated,
#    PARA category from the folder (tools/enron_para_<custodian>.json).
uv run python -m tools.extraer_enron --maildir ~/dev/atlas-lab/enron/maildir \
    --custodian kaminski-v --mapping tools/enron_para_kaminski-v.json \
    --out ~/dev/atlas-lab/enron/enron_sample.jsonl
# -> 3,084 emails: 1,940 areas, 875 projects, 269 resources
uv run python -m tools.extraer_enron --maildir ~/dev/atlas-lab/enron/maildir \
    --custodian shapiro-r --mapping tools/enron_para_shapiro-r.json \
    --out ~/dev/atlas-lab/enron/shapiro-r/enron_sample.jsonl
# -> 1,179 emails: 584 areas, 275 projects, 320 resources

# 3. Check the questions against that corpus (no network).
uv run python -m tools.verificar_preguntas \
    --corpus ~/dev/atlas-lab/enron/enron_sample.jsonl \
    questions/enron_kaminski-v.jsonl questions/enron_kaminski-v_abstain.jsonl
uv run python -m tools.verificar_preguntas \
    --corpus ~/dev/atlas-lab/enron/shapiro-r/enron_sample.jsonl \
    questions/enron_shapiro-r.jsonl questions/enron_shapiro-r_abstain.jsonl

# 4. Index (spends credits: ~US$0.01 with folder labels, ~US$0.3 with Nano).
uv run python -m scripts.index_enron --labels folders \
    --corpus ~/dev/atlas-lab/enron/enron_sample.jsonl \
    --chroma ~/dev/atlas-lab/enron/chroma_folders

# 5. Evaluate. --retrieval-only: hit@5, MRR, routing (~US$0.05 per index).
#    --real adds Ultra and RAGAS (dollars: estimate and confirm first).
uv run python -m scripts.run_eval --retrieval-only \
    --chroma ~/dev/atlas-lab/enron/chroma_folders --run enron-folders --threshold 0.3 \
    --questions questions/enron_kaminski-v.jsonl \
    --questions questions/enron_kaminski-v_abstain.jsonl
```

## Format (D19)

```json
{"id": "en-p001", "q": "...", "expected": "...", "category": "projects",
 "evidence": "maildir/kaminski-v/<folder>/<n>.", "evidence_quote": "<literal fragment>",
 "answerable": true, "hops": 1, "source": "ai-drafted", "corpus": "enron",
 "hard_case": false, "pii": false}
```

- Ids: `en-` for `kaminski-v`, `sh-` for `shapiro-r`; then `p`/`a`/`r` per category
  and `x?` for unanswerable ones.
- `evidence` is the email's path, which is also its id in the index, so hit@k and MRR
  can check whether an arm retrieved it.
- `evidence_alt` lists the **other** emails that also answer the question: a reminder,
  a reply quoting the original, a later confirmation. In a real mailbox the answer often
  lives in more than one email, so retrieving any of them is a correct retrieval; hit@k
  and MRR accept the evidence or any alternate. Each alternate was read and checked to
  contain the answer.
- `category` is the PARA folder of the **evidence email**, from the owner's folder
  (D20.5), in plural as `ParaFolder` emits it.
- Unanswerable questions have `expected`, `category`, `evidence` and `hops` set to
  `null`, plus `probe`: the literal strings the answer would need. The verifier checks
  that no email contains all of them.

## How they were written

The same method for every custodian:

- Two steps per question, against lexical contamination (D27): extract the fact from
  the email, then write the question from the fact only, as the mailbox owner would ask
  it, without seeing the email or the quote.
- One hop, absolute time anchors (D20). No summaries, opinions or counting.
- Unique quote: `evidence_quote` appears in at most 3 emails. Facts repeated by a few
  emails are kept and listed in `evidence_alt`; facts repeated everywhere (newsletters,
  mass announcements) were dropped, because any chunk would match them. Facts copied into
  emails of other folders were dropped, so the flat arm does not find copies that the
  filter would hide.
- `hard_case: true`: a sibling email from the same thread or series could pull
  retrieval away (D28).
- `pii: true`: `expected` contains a person's name or personal data.
- Human review with 5 criteria (answered by the email, expected exact, unique, natural
  and not copied, category), in batches of 20. Rejected questions are rewritten (field
  `revised` says why) and reviewed again.

| | `kaminski-v` (200) | `kaminski-v_100` | `shapiro-r` (100) |
|---|---|---|---|
| Median Jaccard question/email (p / a / r) | 0.057–0.073 | 0.067 / 0.063 / 0.051 | 0.043 / 0.056 / 0.047 |
| `hard_case` | 65 | 29 | 55 |
| `pii` | 34 | 14 | 18 |
| `evidence_alt` (questions / emails) | 20 / 30 | 7 / 14 | 2 / 3 |
| `revised` | 45 | 20 | 4 |
| `source` | all `human-verified` | all `human-verified` | all `human-verified` |

### `kaminski-v`

- 2026-10-25: first 150 + 15 (ids `...001`–`...050`, `en-x?01`–`05`), then +50 + 10 to
  reach 200 + 25 (ids `...051`–`...067`, `en-x?06`–`09`), checked together (no shared
  evidence, no repeated fact).
- 2026-10-25: an AI pre-review (triage) of all 200 against their evidence emails, checked
  against a human sample of 10 (same verdict on all 10). 27 rewritten to one fact each,
  67 expected answers trimmed to what the question asks, 35 more `hard_case`, and
  `evidence_alt` added to the 17 whose answer is repeated by other emails. This was not
  a human verification.
- 2026-10-25: human review of all 200 by a member of the team (Person 3). 18 more were
  rejected and rewritten, then reviewed again; 3 more alternates were added. All 200 are
  `human-verified`.
- 2026-10-27: `enron_kaminski-v_100.jsonl`, for the 125-per-custodian plan. Stratified
  random sample of the 200 (seed `20261027`), ids and fields unchanged:

  ```python
  rng = random.Random(20261027)
  for cat, n in (("projects", 34), ("areas", 33), ("resources", 33)):
      pool = [r for r in rows if r["category"] == cat and r["source"] == "human-verified"]
      out += sorted(rng.sample(pool, n), key=lambda r: r["id"])
  ```

  With `enron_kaminski-v_abstain.jsonl` it passes the verifier 125/125.

### `shapiro-r`

Richard Shapiro, Enron's head of government and regulatory affairs: 91 owner folders,
1,179 emails after extraction.

- 2026-10-27: 45 facts extracted per category, 135 questions written from the facts
  alone, 30 unanswerable ones. Selection: drop verifier failures, questions that ask for
  two facts or leak the answer, and the 9 the extractors named weakest; then keep the
  lowest Jaccard up to 34 / 33 / 33. 5 unanswerable ones dropped (near-misses of facts
  the corpus does contain, and one about a named person's severance, for privacy).
- 2026-10-27: human review of the 100 answerable ones (Person 3), 5 batches of 20. 96
  passed on the first read; 4 were rewritten (two copied the email's wording, two had
  more in `expected` than the question asks) and passed on the second. All 100 are
  `human-verified`. The verifier passes 125/125.

## Declared limitations

1. **The PARA labels are our interpretation** of another person's folders, frozen
   before the questions were written (D23). They are not a ground truth. Debatable:
   - `kaminski-v`: `risk`, `stanford`, `ut`, `eci`.
   - `shapiro-r`: the regional folders (`california`, `europe`, `texas`, `west`, …)
     are `areas`, ongoing responsibilities, while dated or deal folders inside the same
     regions (`europe_june`, `california_legal_issues`, `sce_deal`) are `projects`.
     Policy-topic folders (`ferc`, `nerc`, `antitrust`, `rto_filings__order_2000`) are
     `resources`, although a regulatory-affairs head could see them as `areas`.
2. **The answerable questions are `human-verified`**: written by an AI with the two-step
   method, then read one by one against their evidence email by a member of the team.
   **The unanswerable ones are still `ai-drafted`** for both custodians.
3. **Real private email.** The Enron corpus is public, but it is the correspondence of
   people most of whom had nothing to do with the FERC investigation. Use it for
   research only, and do not republish personal details from it.
4. The corpora are unbalanced (`kaminski-v` 63% `areas`, `shapiro-r` 50% `areas`); the
   questions are balanced so every category gets the same statistical power.
