"""Test doubles satisfying the team contracts.

This lives apart from the shared schemas on purpose: those are consumed by all
four modules, and a test double has no business travelling with them. Here it
can grow without polluting the contract.

What this module solves: `harness.run()` is written and tested, but has never
run end to end because `retrieve()` belongs to Person 2 and does not exist yet.
`retrieve_fake` fills that hole and unblocks the full run today, with no network
and no budget spent (R6).

**This is NOT official and produces no project results.** It is scaffolding to
exercise the pipeline. Any number coming out of a run against this module is
good for checking that rows are generated, that the D8 zeros are counted and
that truncation is flagged -- **never for answering H1**. Real runs start the
day Person 2's `retrieve()` arrives.

And there is one point where the double departs from the real system on purpose
(R17): the real retriever is going to **classify the question** to choose the
PARA folder, because contract C2 has no way to receive the category. Here the
folder comes out of a hash, which is arbitrary and models no classifier at all.
It was built this way so as not to fake a capability that does not exist yet: a
double that appeared to classify well would invite reading its results as if
they meant something.
"""

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from typing import Literal

from selfware.core.schemas import Chunk

Strategy = Literal["flat", "para"]

#: The PARA folders the filter can choose from. **`archive/2026` is deliberate
#: and holds not a single chunk in `CORPUS`.** That is how the D8 case is
#: provoked: when the filter lands on that folder, the list comes back empty.
#: There is no special `if` forcing it; it falls out of the same mechanism D8
#: describes -- the filter leaves the folder with nothing -- exactly as it would
#: with the real retriever.
#:
#: The empty drawer is not a whim: R7 measured that the real inbox has 0 emails
#: in `archive`. The double reproduces that shape.
PARA_PATHS: tuple[str, ...] = (
    "projects/atlas",
    "areas/finance",
    "resources/newsletters",
    "archive/2026",
)

#: Small fixed corpus. The text is deliberately synthetic: nobody should be able
#: to mistake a run against this corpus for a real one.
CORPUS: tuple[Chunk, ...] = (
    Chunk(
        text="FAKE: project note about the September deliverable.",
        item_id="itm-01",
        para_path="projects/atlas",
        ts=datetime(2026, 9, 1, tzinfo=UTC),
        similarity=0.0,
    ),
    Chunk(
        text="FAKE: minutes of the weekly project meeting.",
        item_id="itm-02",
        para_path="projects/atlas",
        ts=datetime(2026, 9, 8, tzinfo=UTC),
        similarity=0.0,
    ),
    Chunk(
        text="FAKE: monthly receipt for a service, amount and reference number.",
        item_id="itm-03",
        para_path="areas/finance",
        ts=datetime(2026, 7, 9, tzinfo=UTC),
        similarity=0.0,
    ),
    Chunk(
        text="FAKE: next month's receipt, same service, different reference.",
        item_id="itm-04",
        para_path="areas/finance",
        ts=datetime(2026, 8, 9, tzinfo=UTC),
        similarity=0.0,
    ),
    Chunk(
        text="FAKE: subscription renewal notice.",
        item_id="itm-05",
        para_path="areas/finance",
        ts=datetime(2026, 9, 9, tzinfo=UTC),
        similarity=0.0,
    ),
    Chunk(
        text="FAKE: tech newsletter, morning edition.",
        item_id="itm-06",
        para_path="resources/newsletters",
        ts=datetime(2026, 9, 14, tzinfo=UTC),
        similarity=0.0,
    ),
    Chunk(
        text="FAKE: tech newsletter from the same day, another edition.",
        item_id="itm-07",
        para_path="resources/newsletters",
        ts=datetime(2026, 9, 14, tzinfo=UTC),
        similarity=0.0,
    ),
    Chunk(
        text="FAKE: tech newsletter from the previous week.",
        item_id="itm-08",
        para_path="resources/newsletters",
        ts=datetime(2026, 9, 7, tzinfo=UTC),
        similarity=0.0,
    ),
)


def _similarity(query: str, item_id: str) -> float:
    """Fake similarity between a question and a chunk. Deterministic.

    Two inputs, one output, no state. It can be tested in one line from the
    interpreter, and that is exactly the point of keeping it apart:
    `retrieve_fake` has a filter, an ordering and a cut competing for your
    attention; here there is nothing but the formula.

    The string being hashed is `f"{query}||{item_id}"`. The `||` is a separator
    and it is not decorative: without it, `("ab", "c")` and `("a", "bc")` would
    produce the same string and therefore the same similarity.

    Args:
        query: the question, as is.
        item_id: the chunk id. The id is hashed rather than the text because the
            id is short, stable and unique: if the text of a chunk is corrected
            tomorrow, the similarities do not move.

    Returns:
        A value in **[0, 1)**. It can be 0.0, never exactly 1.0 -- it is 4 bytes,
        that is an integer from 0 to 2**32 - 1, divided by 2**32.
    """

    combined = f"{query}||{item_id}"
    raw = combined.encode()
    digest = hashlib.sha256(raw).digest()
    value = int.from_bytes(digest[:4], "big")

    return value / (1 << 32)


def _target_folder(query: str) -> str:
    """The PARA folder the filter will look at for this question.

    Same machinery as `_similarity` but over the query alone, and instead of
    dividing it takes modulo `len(PARA_PATHS)` to turn the integer into an index.

    **It is not a classifier and does not pretend to be one** (R17). Person 2's
    real retriever will classify the question; here the folder is arbitrary on
    purpose, so as not to fake a capability that does not exist.

    Args:
        query: the question, as is.

    Returns:
        One of the `PARA_PATHS`. It can be `archive/2026`, which has no chunks:
        that is where the D8 empty case comes from.
    """

    raw = query.encode()
    digest = hashlib.sha256(raw).digest()
    index = int.from_bytes(digest[:4], "big") % len(PARA_PATHS)

    return PARA_PATHS[index]


def retrieve_fake(query: str, strategy: Strategy, k: int) -> list[Chunk]:
    """Fake retriever satisfying contract C2. Deterministic, no network.

    **It retrieves nothing semantically.** The similarities come from a hash, so
    the relationship between the question and whichever chunk comes out first is
    pure arithmetic coincidence. That is deliberate: a double that *appeared* to
    retrieve well would invite reading the numbers of a test run as if they meant
    something.

    What it does reproduce faithfully are the contract **invariants**, which is
    all `harness.py` needs to run end to end.

    The two formulas, and they have to be exactly these because the tests pin
    concrete values that depend on them:

        chunk similarity:
            sha256(f"{query}||{chunk.item_id}") -> first 4 bytes as a big-endian
            integer -> divided by 2**32

        target folder of the PARA arm:
            sha256(query) -> first 4 bytes as a big-endian integer
            -> modulo len(PARA_PATHS) -> index into PARA_PATHS

    `item_id` is hashed rather than the text: the id is short, stable and unique,
    and if the text of a chunk is ever edited the similarities do not move.

    A hash and not `random.seed()`: `random` has global state, so any other part
    of the process using it shifts the sequence, and the run stops being
    reproducible without raising any error. The hash depends on nothing external.

    Args:
        query: the question. It enters both formulas, so two different questions
            see different similarities and, almost always, different folders.
        strategy: `"flat"` looks at all of `CORPUS`. `"para"` looks only at the
            chunks of the target folder.
        k: how many to return at most. The same value goes to both arms (D11),
            but that is guaranteed by the caller, not by this function.

    Returns:
        Up to `k` chunks, **sorted by `similarity` descending** (D9), each with
        its `similarity` computed in [0,1) (D10). The `Chunk`s in `CORPUS` carry
        `similarity=0.0` because they are immutable and the real value depends on
        the query: copies with the similarity set have to be returned, not the
        originals.

        **It can return an empty list**, and only in the PARA arm: when the
        target folder is `archive/2026`, which has no chunks (D8). The `flat` arm
        never comes back empty as long as `CORPUS` holds something.

    Hint for the body: it is four steps. Choose where you start from (the whole
    corpus or one folder), compute the similarity of each candidate, sort, cut at
    `k`. To create the chunk with its similarity, `dataclasses.replace()` gives
    you a copy with one field changed, which is exactly what is needed with a
    frozen dataclass.
    """
    folders = []
    chunks = []
    if strategy == "para":
        folders.append(_target_folder(query))
    else:
        folders = PARA_PATHS

    for chunk in CORPUS:
        if chunk.para_path in folders:
            new_chunk = replace(
                chunk, similarity=_similarity(query=query, item_id=chunk.item_id)
            )
            chunks.append(new_chunk)

    chunks.sort(key=lambda c: c.similarity, reverse=True)

    while len(chunks) > k:
        chunks.pop()

    return chunks
