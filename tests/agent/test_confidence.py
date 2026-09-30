"""Tests for `confidence.py`. None of them makes network calls or spends budget.

The numbers are chosen so you can verify them by hand: when every token has the
same probability p, the geometric mean is exactly p.
"""

import math
from datetime import UTC, datetime

import pytest

from selfware.agent.confidence import (
    ThinkTagNotFoundError,
    TokenLogprob,
    answer_tokens,
    confidence,
    generation_confidence,
    retrieval_confidence,
)
from selfware.core.schemas import Chunk


def tok(text: str, p: float) -> TokenLogprob:
    """Token with probability `p`. Written as a probability because it reads better."""
    return TokenLogprob(token=text, logprob=math.log(p))


def think() -> TokenLogprob:
    """The marker separating reasoning from answer."""
    return TokenLogprob(token="</think>", logprob=math.log(0.99))


def end() -> TokenLogprob:
    """Closing of the chat format. Verified on 14 Sep: it does arrive in the
    array, and with a very high probability."""
    return TokenLogprob(token="<|im_end|>", logprob=math.log(0.999))


def chunk(similarity: float) -> Chunk:
    """Filler chunk: only `similarity` matters here."""
    return Chunk(
        text="does not matter",
        item_id="itm-001",
        para_path="areas/finance",
        ts=datetime(2026, 8, 14, tzinfo=UTC),
        similarity=similarity,
    )


# --------------------------------------------------------------------------
# answer_tokens — the D14 cut
# --------------------------------------------------------------------------


def test_answer_tokens_cuts_at_the_marker():
    """Real shape of the sequence, verified on 14 Sep."""
    tokens = [tok("thinking", 0.5), think(), tok("fourteen", 0.9), tok(".", 0.9), end()]
    assert [t.token for t in answer_tokens(tokens)] == ["fourteen", "."]


def test_answer_tokens_without_marker_raises():
    with pytest.raises(ThinkTagNotFoundError):
        answer_tokens([tok("fourteen", 0.9)])


def test_answer_tokens_marker_at_the_end_returns_empty():
    assert answer_tokens([tok("thinking", 0.5), think()]) == []


def test_answer_tokens_only_closing_marker_returns_empty():
    assert answer_tokens([tok("thinking", 0.5), think(), end()]) == []


# --------------------------------------------------------------------------
# generation_confidence
# --------------------------------------------------------------------------


def test_generation_is_high_when_the_model_is_sure():
    tokens = [think()] + [tok("x", 0.95) for _ in range(10)]
    assert generation_confidence(tokens) == pytest.approx(0.95)


def test_generation_is_low_when_the_model_doubts():
    tokens = [think()] + [tok("x", 0.20) for _ in range(10)]
    assert generation_confidence(tokens) == pytest.approx(0.20)


def test_generation_is_geometric_mean_not_arithmetic():
    """With 0.9 and 0.1: geometric = sqrt(0.09) = 0.3; arithmetic would give 0.5."""
    tokens = [think(), tok("a", 0.9), tok("b", 0.1)]
    assert generation_confidence(tokens) == pytest.approx(0.3)


def test_generation_does_not_depend_on_length():
    """The trap. If this fails, confidence is a disguised measure of length and
    `abstain.py` would abstain from long answers, not from unsure ones."""
    short = [think()] + [tok("x", 0.8) for _ in range(3)]
    long = [think()] + [tok("x", 0.8) for _ in range(80)]
    assert generation_confidence(short) == pytest.approx(generation_confidence(long))


def test_generation_ignores_reasoning_tokens():
    """D14: reasoning full of doubt must not drag down the confidence of an
    answer that came out firm."""
    tokens = [tok("hmm", 0.01), tok("maybe", 0.01), think()] + [
        tok("x", 0.9) for _ in range(4)
    ]
    assert generation_confidence(tokens) == pytest.approx(0.9)


def test_generation_is_not_inflated_by_the_closing_marker():
    """`<|im_end|>` arrives with probability ~0.999 and is not content. If it
    slips in, this would give ~0.63 instead of 0.50, and the bias would grow the
    shorter the answer is."""
    tokens = [think(), tok("x", 0.5), tok("x", 0.5), end()]
    assert generation_confidence(tokens) == pytest.approx(0.5)


def test_generation_empty_answer_is_zero():
    assert generation_confidence([tok("thinking", 0.5), think()]) == 0.0


def test_generation_without_marker_raises():
    with pytest.raises(ThinkTagNotFoundError):
        generation_confidence([tok("fourteen", 0.9)])


# --------------------------------------------------------------------------
# retrieval_confidence
# --------------------------------------------------------------------------


def test_retrieval_uses_the_first_one():
    """D9: the list arrives sorted. The first one is the best, no need to search."""
    assert retrieval_confidence(
        [chunk(0.82), chunk(0.71), chunk(0.65)]
    ) == pytest.approx(0.82)


def test_retrieval_empty_list_is_zero():
    """D8: PARA legitimately returns [] when the filter leaves the folder empty.
    It is not an error: it is zero confidence, and the threshold does the rest."""
    assert retrieval_confidence([]) == 0.0


def test_retrieval_rejects_similarity_out_of_range():
    """D10: if a distance arrives instead of a similarity, the signal inverts."""
    with pytest.raises(ValueError):
        retrieval_confidence([chunk(1.7)])


# --------------------------------------------------------------------------
# confidence — the combination
# --------------------------------------------------------------------------


def test_confidence_takes_retrieval_when_it_is_the_weakest():
    """Model extremely sure over a bad chunk: confident hallucination."""
    tokens = [think()] + [tok("x", 0.95) for _ in range(5)]
    assert confidence(tokens, [chunk(0.30)]) == pytest.approx(0.30)


def test_confidence_takes_generation_when_it_is_the_weakest():
    """Excellent chunk but the model did not know what to do with it."""
    tokens = [think()] + [tok("x", 0.25) for _ in range(5)]
    assert confidence(tokens, [chunk(0.90)]) == pytest.approx(0.25)
