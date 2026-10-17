"""When the agent stays quiet instead of answering (D13).

The decision is **a comparison in Python, not the model choosing**. The model
only reports a fact -- its tokens' probabilities, or the abstention sentinel
(R18) -- and `answer.py` turns that into a `confidence`. This module compares it
against a threshold. There is no tool calling and no prompt asking the model
whether it is sure.

What abstaining leads to is integration step 9: a web search with Tavily
instead of the email answer (`Answer.used_web`). This module only decides.

The threshold is **received, never defaulted here**. Choosing it is the
calibration of week 4 (`eval/calibrate.py`, integration step 8b), against the
report's abstention table; any number written here today would be made up.

The same rule, `confidence < threshold`, also lives inside
`eval/report.py::abstention_table`: `agent/` and `eval/` cannot import each
other (architecture rule 1). A test compares the two on the same rows, so they
cannot drift apart silently.
"""

from selfware.core.schemas import Answer


def should_abstain(answer: Answer, threshold: float) -> bool:
    """Whether this answer must not be shown to the user.

    It abstains when **either**:

    1. `answer.confidence < threshold` -- strictly less: exactly at the
       threshold it answers, like `abstention_table`. The sentinel (R18) and
       the no-chunks case both have confidence 0.0, so they abstain at any
       threshold above 0.
    2. `answer.finish_reason != "stop"` -- the answer did not end normally,
       whatever its confidence. A truncated answer (`"length"`) is cut
       mid-sentence, and a no-chunks one (`"no_chunks"`) is empty: neither may
       ever reach the user. This second rule is what the product adds on top of
       the evaluation, where those rows are simply excluded (D17, 2c decision
       3) -- so on normal rows both places agree exactly.

    Args:
        answer: what `make_answerer` returned.
        threshold: in [0, 1], the same range as `confidence`.

    Raises:
        ValueError: if `threshold` is outside [0, 1]. Above 1 everything
            abstains and below 0 nothing does: both are typos, not choices.
    """
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(f"threshold must be in [0, 1], got {threshold}")

    return answer.confidence < threshold or answer.finish_reason != "stop"
