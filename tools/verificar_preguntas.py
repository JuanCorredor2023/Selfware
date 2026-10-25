"""
tools/verificar_preguntas.py -- Person 3.

Checks a questions `.jsonl` against the corpus it was written from, before any
credit is spent on it. Exits non-zero if any question fails, so it can go into
CI later.

    uv run python -m tools.verificar_preguntas \\
        --corpus ~/dev/atlas-lab/enron/enron_sample.jsonl \\
        questions/enron_kaminski-v.jsonl questions/enron_kaminski-v_abstain.jsonl

Per question:

1. **Format (D19).** Every field present, `category` one of the three PARA
   folders (plural, as `ParaFolder` emits them, F2), `id` unique across files.
2. **Evidence exists.** `evidence` is the `id` of a message in the corpus.
3. **Quote is literal.** `evidence_quote` appears in that message's text
   (whitespace-normalised, case kept).
4. **Evidence is unique.** The quote appears in at most `MAX_COPIES` messages of
   the corpus; more and any of them counts as correct, inflating recall in both
   arms.
5. **Category is the folder's (D20.5).** The question's `category` is the one
   the corpus gave the evidence message.
6. **Alternate evidence exists.** `evidence_alt`, when present, is a list of
   other corpus ids that also answer the question (a reminder, a quoting reply):
   in a real mailbox the answer is often in more than one email. They must
   exist and differ from `evidence`.
7. **Unanswerable really is (D21).** For `answerable: false`, no message
   contains every string in `probe` (the literal words the answer would need).

It also prints the lexical overlap of D27: Jaccard over content words between
each question and its evidence message, per category. High overlap means the
question borrowed the email's vocabulary and retrieval will find it trivially.
"""

import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

CATEGORIES = frozenset({"projects", "areas", "resources"})
MAX_COPIES = 3

REQUIRED = (
    "id",
    "q",
    "expected",
    "category",
    "evidence",
    "evidence_quote",
    "answerable",
    "hops",
    "source",
    "corpus",
    "hard_case",
    "pii",
)
REQUIRED_ABSTAIN = ("id", "q", "expected", "answerable", "source", "corpus", "probe")

#: Small English stopword list: enough for D27's comparison between groups,
#: which only needs the same list applied to every question.
STOPWORDS = frozenset(
    """a about above after again against all am an and any are as at be because
    been before being below between both but by can could did do does doing down
    during each few for from further had has have having he her here hers him his
    how i if in into is it its just me more most my no nor not now of off on once
    only or other our out over own same she should so some such than that the
    their them then there these they this those through to too under until up
    very was we were what when where which while who whom why will with would
    you your yours i'm i'll i've we'll what's""".split()  # noqa: SIM905
)


def norm(text: str) -> str:
    return " ".join(text.split())


def content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9']+", text.lower()) if w not in STOPWORDS}


def jaccard(a: str, b: str) -> float:
    x, y = content_words(a), content_words(b)
    return len(x & y) / len(x | y) if x | y else 0.0


def check(question: dict, corpus: dict[str, dict], texts: list[str]) -> list[str]:
    """The problems of one question; an empty list means it passes."""
    answerable = question.get("answerable")
    fields = REQUIRED if answerable else REQUIRED_ABSTAIN
    missing = [f for f in fields if f not in question]
    if missing:
        return [f"missing fields: {missing}"]

    if not answerable:
        probe = question["probe"]
        if not probe or not all(isinstance(p, str) and p for p in probe):
            return ["probe must be a non-empty list of strings"]
        if question["expected"] is not None:
            return ["expected must be null for an unanswerable question"]
        lowered = [p.lower() for p in probe]
        hits = [i for i, t in enumerate(texts) if all(p in t.lower() for p in lowered)]
        return [f"probe {probe} found in {len(hits)} message(s)"] if hits else []

    problems = []
    if question["category"] not in CATEGORIES:
        problems.append(
            f"category {question['category']!r} not in {sorted(CATEGORIES)}"
        )
    if question["hops"] not in (1, 2):
        problems.append(f"hops {question['hops']!r} must be 1 or 2")
    if not question["expected"]:
        problems.append("expected is empty")
    doc = corpus.get(question["evidence"])
    if doc is None:
        return problems + [f"evidence {question['evidence']!r} not in the corpus"]
    quote = norm(question["evidence_quote"])
    if not quote:
        return problems + ["evidence_quote is empty"]
    if quote not in norm(doc["text"]):
        problems.append("evidence_quote is not literal in the evidence message")
    copies = sum(quote in t for t in texts)
    if copies > MAX_COPIES:
        problems.append(f"evidence_quote appears in {copies} messages (> {MAX_COPIES})")
    alts = question.get("evidence_alt", [])
    if not isinstance(alts, list) or not all(isinstance(a, str) for a in alts):
        problems.append("evidence_alt must be a list of corpus ids")
    else:
        missing = [a for a in alts if a not in corpus]
        if missing:
            problems.append(f"evidence_alt not in the corpus: {missing}")
        if question["evidence"] in alts or len(set(alts)) != len(alts):
            problems.append("evidence_alt repeats an id")
    if doc.get("category") and doc["category"] != question["category"]:
        problems.append(
            f"category {question['category']!r} but the evidence folder is "
            f"{doc['category']!r} (D20.5)"
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.verificar_preguntas")
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("files", type=Path, nargs="+")
    args = parser.parse_args(argv)

    corpus: dict[str, dict] = {}
    for line in args.corpus.expanduser().read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            corpus[row["id"]] = row
    texts = [norm(r["text"]) for r in corpus.values()]

    seen: set[str] = set()
    failed = 0
    total = 0
    overlap: dict[str, list[float]] = defaultdict(list)
    for path in args.files:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            total += 1
            try:
                question = json.loads(line)
            except json.JSONDecodeError as e:
                failed += 1
                print(f"FAIL {path}:{n}: not JSON ({e})")
                continue
            qid = question.get("id", f"{path}:{n}")
            problems = check(question, corpus, texts)
            if qid in seen:
                problems.append("duplicate id")
            seen.add(qid)
            if problems:
                failed += 1
                print(f"FAIL {qid}: " + "; ".join(problems))
            elif question.get("answerable"):
                doc = corpus[question["evidence"]]
                overlap[question["category"]].append(
                    jaccard(question["q"], doc["text"])
                )

    print(f"\n{total} questions, {total - failed} pass, {failed} fail")
    print("D27 lexical overlap (Jaccard question vs evidence), passing questions:")
    for cat in sorted(overlap):
        values = overlap[cat]
        print(
            f"  {cat:10} n={len(values):3}  median={statistics.median(values):.3f}  "
            f"max={max(values):.3f}"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
