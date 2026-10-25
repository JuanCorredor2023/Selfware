"""
scripts/index_enron.py -- Person 3.

Loads `enron_sample.jsonl` (from `tools/extraer_enron.py`) into a Chroma index
that Person 2's `Retrieve` can search. **Spends credits**: one embedding per
email (Qwen3-Embedding-8B), plus one Nano call per email with `--labels nano`.
Estimate and confirm before running it (CLAUDE.md).

    uv run python -m scripts.index_enron --labels folders \\
        --corpus ~/dev/atlas-lab/enron/enron_sample.jsonl \\
        --chroma ~/dev/atlas-lab/enron/chroma_folders

    uv run python -m scripts.index_enron --labels nano \\
        --corpus ~/dev/atlas-lab/enron/enron_sample.jsonl \\
        --chroma ~/dev/atlas-lab/enron/chroma_nano

Two ways to label each email with its PARA folder, one index each, so the two
can be compared on the same questions:

- `folders`: the `category` the extractor took from the folder the owner filed
  it in (`tools/enron_para_kaminski-v.json`). Same source as the questions'
  `category`, so it isolates H1 from classifier error.
- `nano`: Person 2's `Classifier.classify_document`, the real ingestion path.
  Labels are saved next to the index (`labels_nano.jsonl`) so a second run, or
  a crash halfway, does not pay for them again. That file is also what measures
  how often Nano agrees with the owner.

It is a composition root like `run_eval.py`: it may import `context/`.
Emails already in the index are skipped, so it is safe to re-run.
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import selfware.context.classifier as classifier_module
import selfware.context.embedder as embedder_module
from scripts._tally import Tally
from selfware.context.classifier import Classifier
from selfware.context.domain import Document
from selfware.context.embedder import Embedder
from selfware.context.store import ChromaStore

SOURCE = "enron"

#: Emails per embeddings request.
BATCH = 32


def to_document(row: dict, category: str) -> Document:
    """One extracted email as Person 2's `Document`.

    `source_id` is the email's path, the same string the questions carry in
    `evidence`: that is what lets the evaluation check whether an arm brought
    the right email back. Subject, sender and date go in front of the body
    because they are part of what someone remembers about an email.
    """
    content = (
        f"Subject: {row['subject']}\nFrom: {row['from']}\nDate: {row['date']}\n\n"
        f"{row['text']}"
    )
    return Document(
        source_id=row["id"],
        source=SOURCE,
        content=content,
        category=category,
        date=row["date"],
    )


def nano_labels(rows: list[dict], path: Path, workers: int) -> dict[str, str]:
    """`id -> category` from Nano, reusing what `path` already holds."""
    labels: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                labels[item["id"]] = item["category"]
    todo = [r for r in rows if r["id"] not in labels]
    print(
        f"nano labels: {len(labels)} cached, {len(todo)} to classify", file=sys.stderr
    )
    if not todo:
        return labels

    classifier = Classifier()

    def label(row: dict) -> tuple[str, str]:
        doc = to_document(row, category="")
        return row["id"], classifier.classify_document(doc.content).value

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as out, ThreadPoolExecutor(workers) as pool:
        for n, (row_id, category) in enumerate(pool.map(label, todo), 1):
            labels[row_id] = category
            out.write(json.dumps({"id": row_id, "category": category}) + "\n")
            if n % 200 == 0:
                out.flush()
                print(f"  classified {n}/{len(todo)}", file=sys.stderr)
    return labels


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m scripts.index_enron")
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--chroma", type=Path, required=True, help="index folder")
    parser.add_argument("--labels", choices=["folders", "nano"], required=True)
    parser.add_argument("--workers", type=int, default=8, help="parallel Nano calls")
    parser.add_argument("--limit", type=int, default=None, help="first N emails only")
    args = parser.parse_args(argv)

    rows = [
        json.loads(line)
        for line in args.corpus.expanduser().read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][: args.limit]
    chroma = args.chroma.expanduser()

    tally = Tally()
    tally.wrap(classifier_module, "call")
    tally.wrap(embedder_module, "embed")

    if args.labels == "folders":
        labels = {r["id"]: r["category"] for r in rows}
    else:
        labels = nano_labels(rows, chroma / "labels_nano.jsonl", args.workers)

    store = ChromaStore(Embedder(), path=str(chroma))
    docs = [to_document(r, labels[r["id"]]) for r in rows]
    ids = [store._create_id(d.source_id, d.source, 0) for d in docs]
    present = set(store.collection.get(ids=ids, include=[])["ids"]) if ids else set()
    todo = [d for d, i in zip(docs, ids, strict=True) if i not in present]
    print(f"index: {len(present)} already in, {len(todo)} to embed", file=sys.stderr)

    for start in range(0, len(todo), BATCH):
        batch = todo[start : start + BATCH]
        for attempt in range(3):
            try:
                store.add_documents(batch)
                break
            except Exception as e:  # transient API errors
                if attempt == 2:
                    raise
                print(f"  retry after {type(e).__name__}", file=sys.stderr)
                time.sleep(5 * (attempt + 1))
        done = start + len(batch)
        if done % (BATCH * 10) == 0 or done == len(todo):
            print(f"  embedded {done}/{len(todo)}", file=sys.stderr)

    by_category: dict[str, int] = {}
    for d in docs:
        by_category[d.category] = by_category.get(d.category, 0) + 1
    print(f"index {chroma}: {store.collection.count()} emails", file=sys.stderr)
    print(f"by category: {by_category}", file=sys.stderr)
    print("Token Factory spend:\n" + tally.summary(), file=sys.stderr)


if __name__ == "__main__":
    main()
