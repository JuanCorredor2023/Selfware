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

Three modes, exactly one required:

- `--fake`: `retrieve_fake`, `answer_fake` and `scores_fake`. No network, no
  budget, and the report carries a warning that it is not a result.
- `--retrieval-only --chroma <index>`: Person 2's real `Retrieve` (one query
  embedding per arm, one Super call per PARA question) and **no answers**. It
  reports hit@k and MRR against each question's `evidence`, plus the PARA
  routing table. Cents, and the first real H1 number.
- `--real --chroma <index>`: the same retrieval, answers from Ultra through
  `core/llm.py` (cached, D16) and RAGAS context precision and recall from the
  judge model. Dollars: estimate and confirm first (CLAUDE.md).

Both real modes print the Token Factory spend at the end (`scripts/_tally.py`).

The report goes to `.cache/reports/<run>.md` by default. `.cache/` is
gitignored, so a fake report can never be committed by accident.
"""

import argparse
import re
import sys
from pathlib import Path

from scripts._tally import Tally
from selfware.core.schemas import Answer, Chunk, Question
from selfware.eval.harness import Record, Retrieved, load_questions
from selfware.eval.harness import run as run_harness
from selfware.eval.pipeline import ScoreFn, evaluate, render_report
from selfware.eval.retrieval_metrics import (
    hit_at_k,
    reciprocal_rank,
    render_routing,
    routing_table,
)

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
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--fake",
        action="store_true",
        help="fake retriever, agent and scorer (no network, no budget)",
    )
    mode.add_argument(
        "--retrieval-only",
        action="store_true",
        help="real retrieval, no answers: hit@k and MRR (spends cents)",
    )
    mode.add_argument(
        "--real",
        action="store_true",
        help="real retrieval, Ultra and the RAGAS judge (spends dollars)",
    )
    parser.add_argument("--chroma", type=Path, help="Chroma index (real modes)")
    parser.add_argument(
        "--workers", type=int, default=4, help="(question, arm) pairs at once"
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="only the first N questions"
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

    if not args.fake and args.chroma is None:
        parser.error("--retrieval-only and --real need --chroma <index folder>")
    return args


def make_real_retrieve(chroma: Path):
    """Person 2's `Retrieve` over `chroma`, adapted to the harness's `Retrieved`
    (the one-liner in `Retrieved`'s docstring). Built once per process (F3)."""
    from selfware.context.classifier import Classifier
    from selfware.context.domain import Strategy
    from selfware.context.embedder import Embedder
    from selfware.context.retrieve import Retrieve
    from selfware.context.store import ChromaStore

    if not chroma.expanduser().is_dir():
        raise SystemExit(f"no index at {chroma}: run scripts.index_enron first")
    store = ChromaStore(Embedder(), path=str(chroma.expanduser()))
    retriever = Retrieve(store, Classifier())

    def retrieve(query: str, strategy: str, k: int) -> Retrieved:
        result = retriever.retrieve(query, Strategy(strategy), k)
        return Retrieved(
            chunks=[c.to_contract() for c in result.chunks],
            fell_back_to_flat=result.fell_back_to_flat,
            query_category=result.query_category and result.query_category.value,
        )

    return retrieve


def no_answer(query: str, chunks: list[Chunk]) -> Answer:
    """`--retrieval-only`: no model call. Confidence is the retrieval signal
    alone (top similarity, D24), so the abstention table is only indicative."""
    return Answer(
        text="",
        confidence=chunks[0].similarity if chunks else 0.0,
        provenance=list(chunks),
        used_web=False,
        finish_reason="stop",
    )


def _report_sections(
    questions: list[Question],
    records: list[Record],
    metrics: dict[str, ScoreFn],
    args: argparse.Namespace,
    warning: str | None,
) -> str:
    sections = [
        render_report(
            questions,
            records,
            score,
            run=args.run,
            metric=name,
            threshold=args.threshold,
            k=args.k,
            n_resamples=args.n_resamples,
            seed=args.seed,
            warning=warning,
        )
        for name, score in metrics.items()
    ]
    sections.append(render_routing(routing_table(questions, records)))
    return "\n\n---\n\n".join(sections)


def main(argv: list[str] | None = None) -> Path:
    """Parse the arguments, run the evaluation, write the report.

    Returns:
        The path the report was written to.
    """
    args = parse_args(argv)
    out = args.out or Path(".cache") / "reports" / f"{args.run}.md"
    questions = load_all(args.questions)[: args.limit]

    if args.fake:
        from tests.fakes.answer_fake import answer_fake
        from tests.fakes.retrieve_fake import retrieve_fake
        from tests.fakes.scores_fake import scores_fake

        report = evaluate(
            questions,
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
    else:
        report = _run_real(questions, args)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    return out


def _run_real(questions: list[Question], args: argparse.Namespace) -> str:
    import selfware.context.classifier as classifier_module
    import selfware.context.embedder as embedder_module

    tally = Tally()
    tally.wrap(classifier_module, "call")
    tally.wrap(embedder_module, "embed")
    retrieve = make_real_retrieve(args.chroma)
    metrics: dict[str, ScoreFn] = {
        f"hit@{args.k}": hit_at_k(args.k),
        "mrr": reciprocal_rank,
    }

    if args.retrieval_only:
        answer = no_answer
        warning = (
            f"RETRIEVAL-ONLY run over {args.chroma.name}: real retrieval, no "
            "answers. The abstention table uses the retrieval signal only."
        )
    else:
        from selfware.agent.answer import make_answerer
        from selfware.core.llm import call_with_logprobs

        def counted_llm_call(tier, messages, **kwargs):
            result = call_with_logprobs(tier, messages, **kwargs)
            tally.add(result.tier_call)
            return result

        answer = make_answerer(Path(".cache"), llm_call=counted_llm_call)
        warning = None

    records = run_harness(questions, retrieve, answer, k=args.k, workers=args.workers)

    judges = []
    if args.real:
        from selfware.eval.ragas_judge import TokenFactoryJudge, make_ragas_judge
        from selfware.eval.ragas_runner import make_ragas_scorer

        for name in ("context_precision", "context_recall"):
            judge = TokenFactoryJudge()
            judges.append(judge)
            metrics[name] = make_ragas_scorer(name, make_ragas_judge(name, judge))

    report = _report_sections(questions, records, metrics, args, warning)
    for judge in judges:
        for tier_call in judge.tier_calls:
            tally.add(tier_call)
    print("Token Factory spend:\n" + tally.summary(), file=sys.stderr)
    return report


if __name__ == "__main__":
    path = main()
    print(f"Report written to {path}", file=sys.stderr)
