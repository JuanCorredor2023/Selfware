# Evaluation questions: Enron, custodian `kaminski-v`

Public validation set for H1 (D26): does filtering retrieval by PARA folder beat a
flat vector index over the same mailbox, per question category?

| File | Questions |
|---|---|
| `enron_kaminski-v.jsonl` | 200 answerable: 67 `projects`, 67 `areas`, 66 `resources`. One evidence email each, all different |
| `enron_kaminski-v_abstain.jsonl` | 25 unanswerable (D21): plausible for this mailbox, answer not in the corpus |

The corpus is **not** in this repo: these files hold the questions only.

## Reproduce

```bash
# 1. The corpus (public, ~423 MB compressed). Keep it outside the repo.
mkdir -p ~/dev/atlas-lab/enron && cd ~/dev/atlas-lab/enron
curl -O https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz
tar -xzf enron_mail_20150507.tar.gz
cd -

# 2. Extract one custodian: owner folders only, quoted thread cut, deduplicated,
#    PARA category from the folder (tools/enron_para_kaminski-v.json).
uv run python -m tools.extraer_enron --maildir ~/dev/atlas-lab/enron/maildir \
    --custodian kaminski-v --mapping tools/enron_para_kaminski-v.json \
    --out ~/dev/atlas-lab/enron/enron_sample.jsonl
# -> 3,084 emails: 1,940 areas, 875 projects, 269 resources

# 3. Check the questions against that corpus (no network).
uv run python -m tools.verificar_preguntas \
    --corpus ~/dev/atlas-lab/enron/enron_sample.jsonl \
    questions/enron_kaminski-v.jsonl questions/enron_kaminski-v_abstain.jsonl

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

- `evidence` is the email's path, which is also its id in the index, so hit@k and MRR
  can check whether an arm retrieved it.
- `evidence_alt` (17 questions, 27 emails) lists the **other** emails that also answer
  the question: a reminder, a reply quoting the original, a later confirmation. In a
  real mailbox the answer often lives in more than one email, so retrieving any of them
  is a correct retrieval; hit@k and MRR accept the evidence or any alternate. Each
  alternate was read and checked to contain the answer.
- `category` is the PARA folder of the **evidence email**, from the owner's folder
  (D20.5), in plural as `ParaFolder` emits it.
- Unanswerable questions have `expected`, `category`, `evidence` and `hops` set to
  `null`, plus `probe`: the literal strings the answer would need. The verifier checks
  that no email contains all of them.

## How they were written

- Two steps per question, against lexical contamination (D27): extract the fact from
  the email, then write the question from the fact only, as the mailbox owner would ask
  it. Median Jaccard overlap between question and email: 0.057–0.073 per category.
- One hop, absolute time anchors (D20). No summaries, opinions or counting.
- Unique quote: `evidence_quote` appears in at most 3 emails. Facts repeated by a few
  emails are kept and listed in `evidence_alt`; facts repeated everywhere (newsletters,
  mass announcements) were dropped, because any chunk would match them. Facts copied into
  emails of other folders were dropped, so the flat arm does not find copies that the
  filter would hide.
- `hard_case: true` (26): a sibling email from the same thread or series could pull
  retrieval away (D28).
- `pii: true` (34): `expected` contains a person's name or personal data.

## Declared limitations

1. **The PARA labels are our interpretation** of another person's folders, frozen on
   2026-10-25 (D23). They are not a ground truth: `risk`, `stanford`, `ut` and `eci`
   are the debatable ones.
2. **All 225 are `source: "ai-drafted"`**. A human reviewer has to read a random sample
   against the email and mark the ones that hold as `"human-verified"` for D27's check
   (does the flat-vs-PARA difference hold in each subset?).
3. **Real private email.** The Enron corpus is public, but it is the correspondence of
   people most of whom had nothing to do with the FERC investigation. Use it for
   research only, and do not republish personal details from it.
4. The corpus is unbalanced (63% `areas`); the questions are balanced (~67 each) so every
   category gets the same statistical power.

## History

- 2026-10-25: an AI pre-review (triage) of all 200 against their evidence emails, checked
  against a human sample of 10 (same verdict on all 10). 27 rewritten to one fact each
  (field `revised`), 67 expected answers trimmed to what the question asks, 35 more
  `hard_case`, and `evidence_alt` added to the 17 whose answer is repeated by other
  emails. This is not a human verification: `source` stays `ai-drafted`.

- 2026-10-25: first 150 + 15 (ids `...001`–`...050`, `en-x?01`–`05`).
- 2026-10-25: +50 + 10 to reach 200 + 25 (ids `...051`–`...067`, `en-x?06`–`09`),
  written with the same method and checked together with the first set (no shared
  evidence, no repeated fact).
