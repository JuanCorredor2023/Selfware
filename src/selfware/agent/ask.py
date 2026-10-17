"""The entry point `/ask` calls: a question in, an `Answer` out (contract C3).

By decision D1 of the 2026-09-30 meeting, `retrieve()` is called by `agent/`,
not by `api/`, and `/ask` calls one function of this lane:

    answer_question(query, strategy) -> Answer

This module builds that function. It does no retrieval and no answering of its
own: it joins "retrieve, then answer" behind the exact signature `/ask` expects.

**Everything is injected.** `agent/` cannot import `context/` (architecture
rule 1), so it cannot build Person 2's `Retrieve`; nor `eval/`, where
`Retrieved` lives. Whoever builds the API (`api/app.py`, Person 4) or the
evaluation (`scripts/run_eval.py`) hands the pieces in -- option 3 of
integration item C1. The same pattern as `make_answerer`: a factory receives the
dependencies once and returns the function with the shape the caller needs.

What Person 4 pastes into `api/app.py` the day real data exists (integration
step 11), replacing the mock import:

    answer_question = make_answer_question(
        retrieve=lambda q, s, k: [
            c.to_contract() for c in person_2_retrieve.retrieve(q, Strategy(s), k).chunks
        ],
        answer=make_answerer(Path(".cache")),
    )
"""

from collections.abc import Callable

from selfware.core.schemas import Answer, Chunk

#: The two arms, as plain strings: what `/ask`, the front end and contract C2
#: speak. Repeated from `eval/harness.py` on purpose: `agent/` cannot import
#: `eval/` (rule 1). When `Retrieved` and these move to `core/schemas.py`
#: (integration step 10), both copies become one import.
VALID_STRATEGIES: tuple[str, ...] = ("flat", "para")

#: What `agent/` needs from retrieval: just the chunks, sorted by similarity
#: descending (D9). The caller adapts whatever the real retriever returns --
#: Person 2's `RetrievalResult`, or the evaluation's `Retrieved` -- with one
#: `.chunks`. Answering needs nothing else; if the agent ever has to know that
#: PARA fell back to flat (e.g. to abstain), this is the type that grows.
ChunkRetrieveFn = Callable[[str, str, int], list[Chunk]]

#: What `make_answerer` returns: `(question, chunks) -> Answer`.
AnswerFn = Callable[[str, list[Chunk]], Answer]

#: What this module returns, and what `/ask` calls.
AnswerQuestionFn = Callable[[str, str], Answer]


def make_answer_question(
    retrieve: ChunkRetrieveFn,
    answer: AnswerFn,
    k: int = 5,
) -> AnswerQuestionFn:
    """Return `answer_question(query, strategy) -> Answer` for `/ask`.

    The returned function, in this order:

    1. Checks `strategy` is one of `VALID_STRATEGIES` -- exactly, so `"PARA"`
       or `"Flat"` are rejected -- and raises `ValueError` otherwise, **before**
       retrieving anything. `/ask` already restricts the value, but `agent/`
       does not trust every caller to (integration item F5): a typo here would
       otherwise reach the retriever and silently filter nothing.
    2. `chunks = retrieve(query, strategy, k)`.
    3. Returns `answer(query, chunks)` as is: the `Answer` -- with its
       provenance and its `tier_calls` -- is exactly what the agent produced.
       `/ask` prices those `tier_calls` and records them for `/cost`.

    Nothing is called when the factory runs: retrieval and answering happen
    only when a question arrives.

    Args:
        retrieve: see `ChunkRetrieveFn`.
        answer: see `AnswerFn`; normally `make_answerer(...)`.
        k: chunks per query. 5 by default, the same as the evaluation (D11), so
            the demo runs the same configuration as the report's number.

    Raises:
        ValueError: here, if `k < 1`. A `k` of 0 would make every answer a
            no-chunks answer, which looks like PARA failing.
    """
    if k < 1:
        raise ValueError(f"k must be at least 1, got {k}")

    def answer_question(query: str, strategy: str) -> Answer:
        if strategy not in VALID_STRATEGIES:
            raise ValueError(
                f"unsupported strategy {strategy!r}; expected one of {VALID_STRATEGIES}"
            )
        chunks = retrieve(query, strategy, k)
        return answer(query, chunks)

    return answer_question
