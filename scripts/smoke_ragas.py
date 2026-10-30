"""
scripts/smoke_ragas.py -- Person 3.

Manual smoke test of the real RAGAS judge (integration step R4). Makes REAL
calls to Token Factory -- the `judge` tier, Qwen3-235B, never Ultra -- through
the exact chain the evaluation will use:

    ragas.evaluate -> TokenFactoryJudge -> core.llm.call("judge") -> Token Factory

This is NOT part of `pytest` on purpose, like `scripts/e2e_smoke.py`: it costs
money and needs the network, and neither belongs in the automated suite.

Three synthetic cases whose scores are known in advance, so the run checks the
judge, not just that it answers:

    1. only the relevant context            -> precision 1.0, recall 1.0
    2. an irrelevant context, then the relevant one
                                            -> precision ~0.5, recall 1.0
    3. only an irrelevant context           -> precision 0.0, recall 0.0

Calls: precision makes one per retrieved context (1 + 2 + 1 = 4), recall one
per case (3): 7 in total. At the end it prints the tokens actually consumed and
their cost, from the judge's own `TierCall`s (`CLAUDE.md`). It never prints the
prompts, and never reads or prints the API key: `core/llm.py` loads it from
`.env`.

Usage, from the repo root, with NEBIUS_API_KEY in `.env`:

    uv run python -m scripts.smoke_ragas
"""

from selfware.eval.ragas_judge import TokenFactoryJudge, make_ragas_judge
from selfware.eval.ragas_runner import JudgeInput
from selfware.observability.cost import with_cost

RELEVANT = (
    "Registration confirmed: the Python workshop starts on Tuesday, November 3, "
    "2026 at 6:00 pm, in room 204 of building B."
)
IRRELEVANT = (
    "Weekly newsletter: the new browser release makes tabs faster and adds a "
    "reading mode."
)
QUESTION = "When does the Python workshop start?"
REFERENCE = "Tuesday, November 3, 2026 at 6:00 pm"

CASES = [
    # (label, contexts, expected precision, expected recall)
    ("1 relevant only", (RELEVANT,), 1.0, 1.0),
    ("2 irrelevant, then relevant", (IRRELEVANT, RELEVANT), 0.5, 1.0),
    ("3 irrelevant only", (IRRELEVANT,), 0.0, 0.0),
]


def main() -> None:
    inputs = [
        JudgeInput(f"smoke-{i}", "flat", QUESTION, contexts, REFERENCE, REFERENCE)
        for i, (_, contexts, _, _) in enumerate(CASES, start=1)
    ]

    judges = {}
    results = {}
    for metric in ("context_precision", "context_recall"):
        judges[metric] = TokenFactoryJudge()
        results[metric] = make_ragas_judge(metric, judges[metric])(inputs)

    print(f"{'case':30} {'precision':>18} {'recall':>18}")
    for i, (label, _, exp_p, exp_r) in enumerate(CASES):
        p = results["context_precision"][i]
        r = results["context_recall"][i]
        print(f"{label:30} {p:8.3f} (exp {exp_p:.1f}) {r:8.3f} (exp {exp_r:.1f})")

    calls = [tc for j in judges.values() for tc in j.tier_calls]
    tokens_in = sum(tc.tokens_in for tc in calls)
    tokens_out = sum(tc.tokens_out for tc in calls)
    cost = sum(with_cost(tc).cost_usd for tc in calls)
    models = sorted({tc.model for tc in calls})
    print()
    print(f"judge calls: {len(calls)}  models: {models}")
    print(f"tokens: {tokens_in} in, {tokens_out} out  cost: US${cost:.4f}")


if __name__ == "__main__":
    main()
