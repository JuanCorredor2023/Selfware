"""End to end: `scripts/run_eval.py --fake` from question files to report file.

No network, no budget: everything behind `--fake` is a deterministic double.
The question files are written to `tmp_path` and say nothing about anyone.
"""

import json
from pathlib import Path

import pytest

from scripts.run_eval import FAKE_WARNING, load_all, main


def write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def answerable(qid: str, category: str) -> dict:
    return {
        "id": qid,
        "q": f"fake question {qid}?",
        "expected": "fake",
        "category": category,
        "evidence": "fake",
        "answerable": True,
        "hops": 1,
        "source": "human",
    }


def unanswerable(qid: str) -> dict:
    return {
        "id": qid,
        "q": f"fake question {qid}?",
        "expected": None,
        "category": None,
        "evidence": None,
        "answerable": False,
        "hops": None,
        "source": "human",
    }


@pytest.fixture
def question_files(tmp_path):
    cats = ["areas", "projects", "resources"]
    good = write_jsonl(
        tmp_path / "answerable.jsonl",
        [answerable(f"q{i:02}", cats[i % 3]) for i in range(24)],
    )
    abstain = write_jsonl(
        tmp_path / "abstain.jsonl", [unanswerable(f"a{i}") for i in range(5)]
    )
    return good, abstain


def run_main(tmp_path, files, *extra):
    args = ["--fake", "--run", "test-run", "--threshold", "0.3"]
    for f in files:
        args += ["--questions", str(f)]
    args += ["--n-resamples", "200", "--out", str(tmp_path / "report.md"), *extra]
    return main(args)


def test_it_writes_the_report(tmp_path, question_files):
    out = run_main(tmp_path, question_files)

    assert out == tmp_path / "report.md"
    assert out.read_text(encoding="utf-8").startswith("# Atlas — flat vs PARA\n")


def test_a_fake_report_always_carries_the_warning(tmp_path, question_files):
    md = run_main(tmp_path, question_files).read_text(encoding="utf-8")

    assert f"> ⚠️ {FAKE_WARNING}" in md


def test_the_report_has_every_section(tmp_path, question_files):
    md = run_main(tmp_path, question_files).read_text(encoding="utf-8")

    for heading in (
        "## Operational, by arm",
        "## fake_score overall",
        "## fake_score by category",
        "## fake_score by hard_case",
        "## fake_score by source",
        "## fake_score by hops",
        "## Abstention (threshold 0.30)",
    ):
        assert heading in md


def test_both_files_are_loaded(tmp_path, question_files):
    """24 answerable rows per arm, and the unanswerable file in the abstention
    table. Up to 5: `answer_fake` truncates about 1 in 20 and truncated rows are
    not counted there (2c, decision 3), so the exact n is not pinned."""
    md = run_main(tmp_path, question_files).read_text(encoding="utf-8")
    abstention = md.split("## Abstention")[1]
    flat_row = next(x for x in abstention.splitlines() if x.startswith("| flat |"))
    n_unanswerable = int(flat_row.split("|")[2].split("/")[1].split(" ")[0])

    assert "| flat | 24 |" in md
    assert 1 <= n_unanswerable <= 5


def test_running_twice_gives_the_same_report(tmp_path, question_files):
    a = run_main(tmp_path, question_files).read_text(encoding="utf-8")
    b = run_main(tmp_path, question_files).read_text(encoding="utf-8")

    assert a == b


def test_the_default_output_goes_under_dot_cache(tmp_path, question_files, monkeypatch):
    """Gitignored, so a fake report can never be committed by accident."""
    monkeypatch.chdir(tmp_path)
    args = ["--fake", "--run", "r1", "--threshold", "0.3", "--n-resamples", "200"]
    for f in question_files:
        args += ["--questions", str(f)]

    out = main(args)

    assert out == Path(".cache") / "reports" / "r1.md"
    assert (tmp_path / out).exists()


def test_without_a_mode_it_refuses(tmp_path, question_files):
    """One of --fake, --retrieval-only or --real is required: no silent default
    that spends credits."""
    with pytest.raises(SystemExit) as exc:
        main(
            ["--run", "r", "--threshold", "0.3", "--questions", str(question_files[0])]
        )

    assert exc.value.code != 0


def test_the_threshold_is_mandatory(question_files):
    with pytest.raises(SystemExit):
        main(["--fake", "--run", "r", "--questions", str(question_files[0])])


@pytest.mark.parametrize("value", ["-0.1", "1.5"])
def test_a_threshold_outside_0_1_is_rejected(question_files, value):
    with pytest.raises(SystemExit):
        main(
            ["--fake", "--run", "r", "--threshold", value]
            + ["--questions", str(question_files[0])]
        )


@pytest.mark.parametrize("label", ["../escape", "a/b", "with space", ".."])
def test_a_run_label_that_breaks_the_file_name_is_rejected(question_files, label):
    with pytest.raises(SystemExit):
        main(
            ["--fake", "--run", label, "--threshold", "0.3"]
            + ["--questions", str(question_files[0])]
        )


def test_an_id_repeated_across_files_raises(tmp_path):
    a = write_jsonl(tmp_path / "a.jsonl", [answerable("q1", "areas")])
    b = write_jsonl(tmp_path / "b.jsonl", [unanswerable("q1")])

    with pytest.raises(ValueError, match="q1"):
        load_all([a, b])


def test_retrieval_only_scores_against_the_evidence(
    tmp_path, question_files, monkeypatch
):
    """The real-mode wiring with Person 2's retriever swapped for a double: the
    flat arm always brings the evidence first, PARA never does."""
    from datetime import UTC, datetime

    from scripts import run_eval
    from selfware.core.schemas import Chunk
    from selfware.eval.harness import Retrieved

    def fake_real_retrieve(chroma, classifier=None):
        def retrieve(query, strategy, k):
            item = "fake" if strategy == "flat" else "other"
            chunk = Chunk("t", item, "areas", datetime(2001, 1, 1, tzinfo=UTC), 0.8)
            category = "areas" if strategy == "para" else None
            return Retrieved(chunks=[chunk], query_category=category)

        return retrieve

    monkeypatch.setattr(run_eval, "make_real_retrieve", fake_real_retrieve)
    out = tmp_path / "r.md"
    main(
        [
            "--retrieval-only",
            "--chroma",
            str(tmp_path),
            "--run",
            "ro",
            "--threshold",
            "0.3",
            "--n-resamples",
            "200",
            "--out",
            str(out),
            *[a for f in question_files for a in ("--questions", str(f))],
        ]
    )
    text = out.read_text(encoding="utf-8")
    assert "RETRIEVAL-ONLY" in text
    assert "hit@5" in text and "mrr" in text
    assert "## PARA routing" in text


def test_real_modes_need_an_index(tmp_path, question_files):
    with pytest.raises(SystemExit):
        main(
            [
                "--real",
                "--run",
                "x",
                "--threshold",
                "0.3",
                "--questions",
                str(question_files[0]),
            ]
        )


def test_the_oracle_routes_by_the_question_category():
    from scripts.run_eval import OracleClassifier
    from selfware.context.domain import ParaFolder
    from selfware.core.schemas import Question

    q = Question("q1", "when?", "x", "areas", "mail-1", True, 1)
    assert OracleClassifier([q]).classify_query("when?") == ParaFolder.AREAS


def test_the_oracle_refuses_unanswerable_questions():
    from scripts.run_eval import OracleClassifier
    from selfware.core.schemas import Question

    q = Question("x1", "who?", None, None, None, False, None)
    with pytest.raises(SystemExit):
        OracleClassifier([q])


def test_oracle_needs_a_real_mode(question_files):
    with pytest.raises(SystemExit):
        main(
            [
                "--fake",
                "--oracle",
                "--run",
                "x",
                "--threshold",
                "0.3",
                "--questions",
                str(question_files[0]),
            ]
        )


def test_load_accepted_reads_evidence_alt(tmp_path):
    from scripts.run_eval import load_accepted

    row = answerable("q1", "areas") | {"evidence_alt": ["mail-2", "mail-3"]}
    path = write_jsonl(tmp_path / "q.jsonl", [row, answerable("q2", "areas")])
    assert load_accepted([path]) == {"q1": frozenset({"mail-2", "mail-3"})}


def test_the_nano_router_sends_the_query_prompt_to_nano(monkeypatch):
    from scripts.run_eval import make_nano_router
    from selfware.context import classifier as classifier_module
    from selfware.context.domain import ParaFolder

    seen = {}

    def fake_call(tier, messages, **kwargs):
        seen["tier"], seen["system"] = tier, messages[0]["content"]
        return "areas", None

    monkeypatch.setattr(classifier_module, "call", fake_call)
    assert make_nano_router().classify_query("q") == ParaFolder.AREAS
    assert seen["tier"] == "nano"
    assert seen["system"] == classifier_module._QUERY_PROMPT


def test_oracle_and_router_do_not_mix(tmp_path, question_files):
    with pytest.raises(SystemExit):
        main(
            [
                "--retrieval-only",
                "--oracle",
                "--router",
                "nano",
                "--chroma",
                str(tmp_path),
                "--run",
                "x",
                "--threshold",
                "0.3",
                "--questions",
                str(question_files[0]),
            ]
        )
