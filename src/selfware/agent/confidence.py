"""Confidence estimation for an answer. Produces `Answer.confidence` (C3).

It combines two independent signals:

    generation_confidence   how sure the model was while writing the answer
    retrieval_confidence    how relevant the best retrieved chunk was

They are orthogonal, and that is why one is not enough: the model can be
absolutely sure of an answer built on an irrelevant chunk -- that is exactly a
confident hallucination -- and the generation signal alone would not see it.
They are combined with `min()`: the system is only as reliable as its weakest
signal.

This module only MEASURES. The decision to abstain belongs to `abstain.py`,
which compares this number against a threshold in Python code (D13). The model
never decides.
"""

import math
from dataclasses import dataclass

from selfware.core.schemas import Chunk

THINK_CLOSE_TAG = "</think>"

# Chat-format markers (e.g. `<|im_end|>`) arrive INSIDE `logprobs.content`.
# Verified on 14 Sep with a real call.
SPECIAL_PREFIX = "<|"
SPECIAL_SUFFIX = "|>"


class ThinkTagNotFoundError(Exception):
    """The logprobs array does not contain `</think>`.

    D14 requires measuring only over the answer, never over the reasoning.
    Without the marker there is no way to know where the answer begins.

    It raises instead of returning a number because the alternative --
    averaging the whole sequence -- would yield a plausible but contaminated
    value, and nobody would notice. The harness flags these responses
    separately, the same way D17 does with `finish_reason != "stop"`. A visible
    failure is worth more than a dirty number.
    """


@dataclass(frozen=True)
class TokenLogprob:
    """A generated token together with the log-probability the model gave it.

    Minimal replica of `choices[0].logprobs.content[i]` from the SDK, with the
    same field names so the conversion is trivial. It exists so this module
    does not depend on the OpenAI SDK: the tests build these objects by hand,
    with no network and no budget spent. The conversion from the real response
    lives in `answer.py`, not here.

    Attributes:
        token: the token text.
        logprob: NATURAL logarithm of its probability, always <= 0.
            logprob = -0.01  ->  p ~ 0.99
            logprob = -2.30  ->  p ~ 0.10
    """

    token: str
    logprob: float


def _is_special_marker(text: str) -> bool:
    """Is this token text a chat-format marker, like `<|im_end|>`?

    The leading underscore in the name is a Python convention: it means "this
    is for internal use by the module, not part of its API". The language does
    not enforce it; it is an agreement between the people reading the code.
    """
    return text.startswith(SPECIAL_PREFIX) and text.endswith(SPECIAL_SUFFIX)


def answer_tokens(tokens: list[TokenLogprob]) -> list[TokenLogprob]:
    """Return the answer tokens: those after `</think>` (D14), with trailing
    special markers stripped.

    The logprobs array is one single continuous sequence:

        reasoning...  </think>  answer...  <|im_end|>

    The SDK presents `reasoning_content` and `content` as separate fields, but
    that is the server splitting the TEXT at `</think>`. The logprobs do not
    come split: they have to be cut here.

    Verified against the real system on 14 Sep (`verificar_logprobs.py`):
    `</think>` arrives as ONE token -- comparing by equality is enough -- and
    `<|im_end|>` DOES appear inside `logprobs.content`. That marker is not
    content: it is the closing of the chat format and its probability is very
    high. Including it would inflate confidence, and since it weighs more the
    shorter the answer is, it would introduce a length bias -- exactly what the
    geometric mean is there to avoid.

    Args:
        tokens: the full sequence, reasoning included.

    Returns:
        The tokens AFTER the marker, removing from the END any that look like a
        special marker (`<|...|>`). Empty list if none are left.
        Only trailing ones are removed: a marker in the middle of the answer
        would be unexpected, and deleting it silently would hide the problem
        instead of surfacing it.

    Raises:
        ThinkTagNotFoundError: if `</think>` does not appear in the sequence.
    """
    answer = []
    past = False
    for token in tokens:
        if past:
            answer.append(token)
        if token.token == THINK_CLOSE_TAG:
            past = True

    if not past:
        raise ThinkTagNotFoundError("</think> not found in the sequence")

    while answer and _is_special_marker(answer[-1].token):
        answer.pop()

    return answer


def generation_confidence(tokens: list[TokenLogprob]) -> float:
    """How sure the model was while writing the answer. Returns [0,1].

    Formula:

        exp( mean of the logprobs of the answer tokens )

    which is the geometric mean of the per-token probabilities. Its reciprocal
    is per-token perplexity, the standard metric in language modelling: it is
    not a formula invented for this project.

    Why the MEAN and not the sum: the sum of logprobs is the joint probability
    of the whole answer, and its magnitude grows with length. Using it would
    turn confidence into a disguised measure of length, and `abstain.py` would
    end up abstaining from long answers instead of unsure ones.

    Why `exp()`: it maps the number back into probability space, where it falls
    in (0,1] without inventing any arbitrary squashing function.

    It receives the COMPLETE sequence and cuts internally with
    `answer_tokens()`. The cut is not the caller's responsibility: if every
    consumer had to remember to cut, one of them would forget (same argument as
    D9).

    Args:
        tokens: the full sequence, reasoning included.

    Returns:
        Geometric mean of the probabilities of the answer tokens, in [0,1].
        Returns 0.0 if there is no token after `</think>`: an empty answer
        supports no confidence at all. This is not a contaminated number, it is
        the correct reading, so it does not raise.

    Raises:
        ThinkTagNotFoundError: if `</think>` does not appear in the sequence.
    """
    answer_tokens_list = answer_tokens(tokens)

    if not answer_tokens_list:
        return 0.0

    avg = sum(token.logprob for token in answer_tokens_list) / len(answer_tokens_list)

    return math.exp(avg)


def retrieval_confidence(chunks: list[Chunk]) -> float:
    """How relevant the best retrieved chunk was. Returns [0,1].

    It is the `similarity` of the FIRST chunk. It trusts the D9 invariant (the
    list arrives sorted descending) instead of looking for the maximum: if
    Person 2 breaks the order, this returns a wrong number and the invariant
    test catches it. Taking the maximum here would hide the contract violation.

    Args:
        chunks: result of `retrieve()`, sorted by similarity descending.

    Returns:
        `chunks[0].similarity`, or 0.0 if the list is empty. An empty list is a
        legitimate result of the PARA arm (D8), not an error: it means the
        filter left the folder with nothing. With no chunks there is nothing
        supporting the answer, so retrieval confidence is zero.

    Raises:
        ValueError: if the `similarity` used falls outside [0,1]. D10: the real
            risk is receiving a DISTANCE instead of a similarity, which would
            invert the signal without raising. This guard catches the case
            where the distance falls out of range.
    """

    if not chunks:
        return 0.0

    if 0.0 <= chunks[0].similarity <= 1.0:
        return chunks[0].similarity

    raise ValueError(f"similarity out of [0,1]: {chunks[0].similarity}")


def confidence(tokens: list[TokenLogprob], chunks: list[Chunk]) -> float:
    """Final confidence of the answer, in [0,1]. This is `Answer.confidence` (C3).

    The minimum of the two signals: if either one is unsure, the system should
    doubt. Discarded alternative: a weighted average
    `w*generation + (1-w)*retrieval`, which requires a `w` we have no data to
    calibrate today and no argument to defend in front of a judge.

    Args:
        tokens: the full logprobs sequence, reasoning included.
        chunks: the chunks used to answer.

    Returns:
        The lesser of `generation_confidence(tokens)` and
        `retrieval_confidence(chunks)`.

    Raises:
        ThinkTagNotFoundError: if `</think>` does not appear in the sequence.
        ValueError: if the `similarity` used falls outside [0,1].
    """

    return min(retrieval_confidence(chunks), generation_confidence(tokens))
