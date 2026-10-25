"""Evidence-based retrieval metrics: did each arm bring back the right email?

Every answerable question carries `evidence`, the id of the one email it was
written from, and every `Record` carries the `item_ids` of what its arm
retrieved. Comparing the two needs no judge model: it is deterministic, free,
and runs before any credit goes to Ultra or RAGAS. It answers H1 in its most
literal form -- "does the PARA filter find the right email more often than the
flat index?" -- and RAGAS's context precision/recall then add how *useful* the
retrieved text was.

- `hit_at_k`: 1 if the evidence is among the first `k` chunks, else 0.
- `reciprocal_rank`: 1/rank of the evidence (1, 0.5, 0.33, ...), 0 if absent.
  Its mean is the MRR; it rewards putting the email first, not just in.

Both return a `ScoreFn`, so they plug into `pipeline.evaluate` like RAGAS does.

**Several accepted emails per question.** In a real mailbox the answer often
lives in more than one email: the original, a reminder, a reply quoting it. If
only `evidence` counted, an arm that brought back the reminder would score a
miss for a correct retrieval. `accepted` maps a question id to its other valid
emails (the `evidence_alt` field of the question files); the evidence or any of
them counts. `Question` (contract C6, Person 1's `core/schemas.py`) has no field
for it, so the caller reads it from the JSONL and passes it in.

`routing_table` is about the PARA arm's classifier, not about H1: per question
category, how often the classifier chose the folder the evidence lives in. A
PARA number next to a 40% routing rate is a finding about the classifier, not
a verdict on PARA (same spirit as the fallback rate, F4).
"""

from collections import defaultdict
from dataclasses import dataclass

from selfware.core.schemas import Question
from selfware.eval.harness import Record
from selfware.eval.pipeline import ScoreFn
from selfware.eval.report import Scores

#: Question id -> the other emails that also answer it (`evidence_alt`).
Accepted = dict[str, frozenset[str]]


def _rank(question: Question, record: Record, accepted: Accepted) -> int | None:
    """1-based position of the first accepted email among the retrieved ids
    (the evidence or any of its alternates), or `None`."""
    valid = {question.evidence} | accepted.get(question.id, frozenset())
    for position, item_id in enumerate(record.item_ids, start=1):
        if item_id in valid:
            return position
    return None


def _score_rows(
    questions: list[Question], records: list[Record], value, accepted: Accepted
) -> Scores:
    by_id = {q.id: q for q in questions}
    scores: Scores = {}
    for r in records:
        q = by_id[r.question_id]
        if q.answerable and q.evidence:
            scores[(r.question_id, r.strategy)] = value(_rank(q, r, accepted))
    return scores


def hit_at_k(k: int, accepted: Accepted | None = None) -> ScoreFn:
    """`ScoreFn`: 1.0 if an accepted email is in the first `k` chunks, else 0.0."""

    def score(questions: list[Question], records: list[Record]) -> Scores:
        return _score_rows(
            questions,
            records,
            lambda rank: float(rank is not None and rank <= k),
            accepted or {},
        )

    return score


def make_reciprocal_rank(accepted: Accepted | None = None) -> ScoreFn:
    """`ScoreFn`: 1/rank of the first accepted email, 0.0 if none was retrieved."""

    def score(questions: list[Question], records: list[Record]) -> Scores:
        return _score_rows(
            questions, records, lambda rank: 1.0 / rank if rank else 0.0, accepted or {}
        )

    return score


#: MRR with the evidence alone, as before `accepted` existed.
reciprocal_rank = make_reciprocal_rank()


@dataclass(frozen=True)
class RoutingRow:
    """How the PARA arm's classifier routed the questions of one category.

    Attributes:
        category: the question's `category` (the folder of its evidence).
        n: PARA rows of answerable questions in this category.
        routed_right: rows whose `query_category` equals `category`.
        fell_back: rows where the PARA filter found nothing and served flat.
        chosen: how many times each folder was chosen, most frequent first.
    """

    category: str
    n: int
    routed_right: int
    fell_back: int
    chosen: tuple[tuple[str, int], ...]


def routing_table(questions: list[Question], records: list[Record]) -> list[RoutingRow]:
    """One `RoutingRow` per question category, sorted by category."""
    by_id = {q.id: q for q in questions}
    groups: dict[str, list[Record]] = defaultdict(list)
    for r in records:
        q = by_id[r.question_id]
        if r.strategy == "para" and q.answerable and q.category:
            groups[q.category].append(r)
    rows = []
    for category in sorted(groups):
        rs = groups[category]
        chosen: dict[str, int] = defaultdict(int)
        for r in rs:
            chosen[r.query_category or "none"] += 1
        rows.append(
            RoutingRow(
                category=category,
                n=len(rs),
                routed_right=sum(r.query_category == category for r in rs),
                fell_back=sum(r.fell_back_to_flat for r in rs),
                chosen=tuple(sorted(chosen.items(), key=lambda kv: (-kv[1], kv[0]))),
            )
        )
    return rows


def render_routing(rows: list[RoutingRow]) -> str:
    """The routing table as a Markdown section."""
    lines = [
        "## PARA routing (query classifier)",
        "",
        (
            "How often the PARA arm searched the folder the evidence lives in. "
            "A wrong folder makes the filter hide the right email."
        ),
        "",
        "| category | n | routed right | fell back | chosen |",
        "|---|---:|---:|---:|---|",
    ]
    for r in rows:
        share = f"{r.routed_right / r.n:.0%}" if r.n else "-"
        chosen = ", ".join(f"{c} {n}" for c, n in r.chosen)
        lines.append(
            f"| {r.category} | {r.n} | {r.routed_right} ({share}) | {r.fell_back} "
            f"| {chosen} |"
        )
    return "\n".join(lines) + "\n"
