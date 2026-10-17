"""
scripts/run_eval.py -- Person 3.

The one command behind the plan's "reproducible with one command": question
files in, Markdown report out.

    uv run python -m scripts.run_eval --fake --run 2026-10-09-fake \\
        --threshold 0.3 \\
        --questions ~/dev/atlas-lab/questions_sebastian_candidatas.jsonl \\
        --questions ~/dev/atlas-lab/questions_sebastian_abstain.jsonl

Run it from the repo root as a module (`-m`), like `scripts.e2e_smoke`: that
puts the repo root on the import path, which `tests.fakes` needs.

This is the **composition root**: the only place that picks which `retrieve`,
`answer` and `score` the pipeline gets. It is not a module of the monolith, so
it may import `eval/`, `agent/`, `context/` and `tests/fakes/` without breaking
architecture rule 1 (option 3 of integration item C1). `eval/pipeline.py`
itself never imports any of them.

Today only `--fake` exists, and it is mandatory: `retrieve_fake`,
`answer_fake` and `scores_fake`, no network, no budget, and the report always
carries a warning that it is not a result. The real mode (Person 2's
`Retrieve`, Ultra through `core/llm.py`, RAGAS) is integration step 11; it
spends credits, so it will come with an estimate and an explicit confirmation.

The report goes to `.cache/reports/<run>.md` by default. `.cache/` is
gitignored, so a fake report can never be committed by accident.
"""

import argparse
import re
import sys
from pathlib import Path

from selfware.core.schemas import Question
from selfware.eval.harness import load_questions
from selfware.eval.pipeline import evaluate
from tests.fakes.answer_fake import answer_fake
from tests.fakes.retrieve_fake import retrieve_fake
from tests.fakes.scores_fake import scores_fake

#: Shown at the top of every fake report (see `render_markdown`'s `warning`).
FAKE_WARNING = (
    "FAKE run: `retrieve_fake`, `answer_fake` and `scores_fake`. "
    "It checks the pipeline end to end; it is NOT a result."
)

#: Name of the metric the fake scorer stands in for.
FAKE_METRIC = "fake_score"

#: The run label becomes a file name: letters, digits, `.`, `_` and `-` only.
RUN_LABEL = re.compile(r"[A-Za-z0-9._-]+")


def _run_label(value: str) -> str:
    """argparse type: reject labels that would escape or break the file name."""
    if not RUN_LABEL.fullmatch(value) or value in {".", ".."}:
        raise argparse.ArgumentTypeError(
            f"{value!r}: use only letters, digits, '.', '_' and '-'"
        )
    return value


def _threshold(value: str) -> float:
    """argparse type: a float in [0, 1], like `abstention_table` requires."""
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise argparse.ArgumentTypeError(f"{value}: must be in [0, 1]")
    return number


def load_all(paths: list[Path]) -> list[Question]:
    """Load several question files into one set, in the order given.

    `load_questions` rejects a repeated `id` inside one file; this does the same
    across files. The answerable and the unanswerable questions live in
    separate files (D21), and two files sharing an id would make the report
    join the wrong rows -- with no error, just odd numbers.

    Raises:
        ValueError: if an `id` appears in more than one file.
    """
    questions: list[Question] = []
    seen: dict[str, Path] = {}
    for path in paths:
        for q in load_questions(path):
            if q.id in seen:
                raise ValueError(f"duplicate id {q.id!r} in {seen[q.id]} and {path}")
            seen[q.id] = path
            questions.append(q)
    return questions


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.run_eval",
        description="Run the flat-vs-PARA evaluation and write the Markdown report.",
    )
    parser.add_argument(
        "--fake",
        action="store_true",
        help="use the fake retriever, agent and scorer (no network, no budget). "
        "Mandatory until the real mode exists (integration step 11).",
    )
    parser.add_argument(
        "--run", required=True, type=_run_label, help="label of the run"
    )
    parser.add_argument(
        "--questions",
        required=True,
        action="append",
        type=Path,
        help="a questions .jsonl file; repeat for several files",
    )
    parser.add_argument(
        "--threshold",
        required=True,
        type=_threshold,
        help="abstention threshold in [0, 1] (D13). No default on purpose.",
    )
    parser.add_argument("--k", type=int, default=5, help="chunks per query (D11)")
    parser.add_argument(
        "--n-resamples", type=int, default=10_000, help="bootstrap resamples (D18)"
    )
    parser.add_argument("--seed", type=int, default=0, help="bootstrap seed")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="where to write the report (default: .cache/reports/<run>.md)",
    )
    args = parser.parse_args(argv)

    if not args.fake:
        parser.error(
            "only --fake exists for now. The real mode (Person 2's retrieve, "
            "Ultra, RAGAS) is integration step 11 and spends credits."
        )
    return args


def main(argv: list[str] | None = None) -> Path:
    """Parse the arguments, run the evaluation, write the report.

    Returns:
        The path the report was written to.
    """
    args = parse_args(argv)
    out = args.out or Path(".cache") / "reports" / f"{args.run}.md"

    report = evaluate(
        load_all(args.questions),
        retrieve_fake,
        answer_fake,
        scores_fake,
        run=args.run,
        metric=FAKE_METRIC,
        threshold=args.threshold,
        k=args.k,
        n_resamples=args.n_resamples,
        seed=args.seed,
        warning=FAKE_WARNING,
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    return out


if __name__ == "__main__":
    path = main()
    print(f"Report written to {path}", file=sys.stderr)
