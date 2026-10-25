"""
scripts/index_emails.py -- Person 4 (proposal for G2 in docs/integration_p3.md).

The missing link between the pieces that already exist:

    ingest/gmail.py  ->  emails.json  ->  Document  ->  classify_documents (Nano)
                                                    ->  ChromaStore.add_documents

    uv run python -m scripts.index_emails --input emails.json           # estimate only
    uv run python -m scripts.index_emails --input emails.json --yes     # really do it
    uv run python -m scripts.index_emails --demo --yes                  # invented emails

It spends credits (one Nano call per email to classify, plus the embeddings), so
WITHOUT `--yes` it only prints what it would do and an estimate. Nothing is
sent to Token Factory until you add `--yes`.

`--demo` loads a dozen INVENTED emails (no real person's data), enough to try
the whole chain with `SELFWARE_AGENT=real`. Do not mix demo and real emails in
the same chroma folder: pass a different `--chroma-path`.

This is a composition script, like `run_eval.py`: it is not a module of the
monolith, so it may import `context/` and `ingest` formats freely.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from selfware.context.domain import Document
from selfware.core.schemas import TierCall
from selfware.observability.cost import estimate_cost_usd

NANO = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
EMBEDDER = "Qwen/Qwen3-Embedding-8B"

#: Rough, on purpose: ~4 characters per token, and the classifier prompt is
#: about 150 tokens. Good for "cents or dollars?", not for an invoice.
CHARS_PER_TOKEN = 4
CLASSIFIER_PROMPT_TOKENS = 150
CLASSIFIER_OUTPUT_TOKENS = 300  # Nemotron reasons first: 99-286 tokens measured (P3, 25 Oct)

DEMO_EMAILS = [
    # Projects: concrete goal, an end.
    (
        "demo-01",
        "2026-09-02T10:15:00+00:00",
        "Thesis: committee meeting moved to Oct 14",
        "Hi, the committee meeting for your thesis defense moved to October 14 at 3pm in room B204. Please send the final chapter draft by October 7.",
    ),
    (
        "demo-02",
        "2026-09-05T18:40:00+00:00",
        "Re: Thesis chapter 3 feedback",
        "Chapter 3 reads well. Main concern: the evaluation section needs a baseline comparison. Please add one before the committee sees it.",
    ),
    (
        "demo-03",
        "2026-09-12T09:00:00+00:00",
        "Hackathon: submission checklist",
        "Reminder for the hackathon team: the demo video must be three minutes, the repo needs an Apache 2.0 license, and the public URL must stay up until judging ends.",
    ),
    (
        "demo-04",
        "2026-09-20T14:20:00+00:00",
        "Lisbon trip: flights and hotel confirmed",
        "Your flights to Lisbon on November 3 are confirmed, returning November 10. Hotel Alfama is booked for 7 nights; check-in from 2pm.",
    ),
    # Areas: ongoing responsibility, no end date.
    (
        "demo-05",
        "2026-09-01T08:00:00+00:00",
        "Gym membership: monthly invoice",
        "Your monthly membership fee of 45 dollars was charged on the 1st. Your plan renews automatically; you can cancel any time from the app.",
    ),
    (
        "demo-06",
        "2026-09-15T12:30:00+00:00",
        "Health insurance: annual checkup reminder",
        "It has been twelve months since your last checkup. Your plan covers one annual visit at no cost. Book through the member portal.",
    ),
    (
        "demo-07",
        "2026-09-18T16:10:00+00:00",
        "Rent receipt for September",
        "Receipt: rent for September, 900 dollars, received on the 3rd. Next payment is due October 3.",
    ),
    # Resources: reference material, topics of interest.
    (
        "demo-08",
        "2026-08-28T07:30:00+00:00",
        "Weekly digest: retrieval-augmented generation",
        "This week: a survey of chunking strategies, why hybrid search beats pure vectors on short queries, and an open-source reranker comparison.",
    ),
    (
        "demo-09",
        "2026-09-10T11:00:00+00:00",
        "Saved: Postgres indexing cheat sheet",
        "Notes you saved: B-tree vs GIN indexes, when partial indexes help, and how to read EXPLAIN ANALYZE output.",
    ),
    # Archive: inactive, finished.
    (
        "demo-10",
        "2025-12-20T10:00:00+00:00",
        "Old apartment: lease ended, deposit returned",
        "Your lease at Calle Mayor ended on December 15 and the deposit was returned in full. No further action needed.",
    ),
    (
        "demo-11",
        "2025-06-30T09:00:00+00:00",
        "Course finished: Intro to Databases certificate",
        "Congratulations, you completed Intro to Databases. Your certificate is attached. The course space will close in 30 days.",
    ),
    (
        "demo-12",
        "2025-03-14T13:00:00+00:00",
        "Cancelled: streaming subscription",
        "Your streaming subscription was cancelled as requested. You will keep access until the end of the billing period.",
    ),
]


@dataclass
class Plan:
    emails: int
    chars: int
    classify_cost_usd: float
    embed_cost_usd: float

    @property
    def total_usd(self) -> float:
        return self.classify_cost_usd + self.embed_cost_usd


def to_documents(raw: list[dict], source: str) -> list[Document]:
    """emails.json entries `{id, ts, subject, body}` -> Documents without a category
    (the classifier fills it). Empty emails are dropped: nothing to embed."""
    docs = []
    for item in raw:
        content = (
            f"Subject: {item.get('subject', '')}\n\n{item.get('body', '')}".strip()
        )
        if not item.get("body", "").strip() and not item.get("subject", "").strip():
            continue
        docs.append(
            Document(
                source_id=item["id"],
                source=source,
                content=content,
                category=None,
                date=item["ts"],
            )
        )
    return docs


def demo_documents() -> list[Document]:
    raw = [{"id": i, "ts": ts, "subject": s, "body": b} for i, ts, s, b in DEMO_EMAILS]
    return to_documents(raw, source="demo")


def plan(docs: list[Document]) -> Plan:
    chars = sum(len(d.content) for d in docs)
    text_tokens = chars // CHARS_PER_TOKEN
    classify = estimate_cost_usd(
        NANO,
        text_tokens + CLASSIFIER_PROMPT_TOKENS * len(docs),
        CLASSIFIER_OUTPUT_TOKENS * len(docs),
    )
    embed = estimate_cost_usd(EMBEDDER, text_tokens, 0)
    return Plan(len(docs), chars, classify, embed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--input", type=Path, help="emails.json written by ingest/gmail.py"
    )
    source.add_argument(
        "--demo", action="store_true", help="index a dozen invented emails"
    )
    parser.add_argument("--chroma-path", default="chroma_data")
    parser.add_argument("--yes", action="store_true", help="spend credits for real")
    args = parser.parse_args(argv)

    if args.demo:
        docs = demo_documents()
    else:
        docs = to_documents(json.loads(args.input.read_text()), source="gmail")
    if not docs:
        print("Nothing to index.")
        return 1

    estimate = plan(docs)
    print(
        f"{estimate.emails} emails, ~{estimate.chars:,} characters -> "
        f"{estimate.emails} Nano classification calls + embeddings.\n"
        f"Estimated cost: ~${estimate.total_usd:.4f} "
        f"(classify ${estimate.classify_cost_usd:.4f}, embed ${estimate.embed_cost_usd:.4f}). "
        f"Chroma folder: {args.chroma_path}"
    )
    if not args.yes:
        print("Dry run: nothing was sent. Add --yes to do it.")
        return 0

    # Heavy imports only now: the dry run needs neither chromadb nor a key.
    from selfware.context.classifier import Classifier
    from selfware.context.embedder import Embedder
    from selfware.context.ingest_classify import classify_documents
    from selfware.context.store import ChromaStore
    from selfware.observability.cost import with_cost

    calls: list[TierCall] = []
    classified = classify_documents(docs, Classifier(on_tier_call=calls.append))
    ChromaStore(Embedder(), path=args.chroma_path).add_documents(classified)

    spent = sum(with_cost(c).cost_usd for c in calls)
    by_category: dict[str, int] = {}
    for d in classified:
        by_category[d.category] = by_category.get(d.category, 0) + 1
    print(f"Indexed {len(classified)} emails: {by_category}")
    print(
        f"Classification cost (measured): ${spent:.4f}. Embedding cost is not measured."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
