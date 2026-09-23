"""Invariants of `retrieve_fake`.

These tests do not check that the double retrieves *well* -- it retrieves
nothing, the similarities come from a hash. They check that it satisfies
**contract C2**, which is all `harness.py` needs to run end to end.

If any of these fails, the harness will produce rows that look reasonable on top
of a retriever that lies in a different way from the one it was designed to.
"""

import pytest

from tests.fakes.retrieve_fake import (
    CORPUS,
    PARA_PATHS,
    _similarity,
    _target_folder,
    retrieve_fake,
)

#: Verified: its hash lands on `archive/2026`, the folder with no chunks. This is
#: how the D8 case is provoked. If `PARA_PATHS` changes, this constant stops
#: holding and has to be recomputed.
QUERY_EMPTY_FOLDER = "how much did I pay?"

#: Verified: its hash lands on `resources/newsletters`, which does have chunks.
QUERY_FULL_FOLDER = "which antivirus did I buy?"


def test_is_deterministic():
    """Two identical calls give exactly the same thing.

    This is the invariant holding up D7. If the double varied between runs, there
    would be no way to tell whether a change in the number came from a change of
    our own or from chance -- and the D16 cache would serve answers that no longer
    correspond.
    """
    a = retrieve_fake(QUERY_FULL_FOLDER, "flat", 5)
    b = retrieve_fake(QUERY_FULL_FOLDER, "flat", 5)
    assert a == b


def test_comes_sorted_by_similarity_descending():
    """D9: the first element is the most relevant.

    `confidence.py` uses the `similarity` of the first chunk as its retrieval
    signal (D24). Without this order, that signal is noise.
    """
    chunks = retrieve_fake(QUERY_FULL_FOLDER, "flat", 8)
    sims = [c.similarity for c in chunks]
    assert sims == sorted(sims, reverse=True)


def test_retrieved_similarity_falls_in_zero_one():
    """D10: cosine in [0,1], higher = more relevant. It is not a distance."""
    for c in retrieve_fake(QUERY_FULL_FOLDER, "flat", 8):
        assert 0.0 <= c.similarity <= 1.0


def test_never_returns_more_than_k():
    for k in (1, 3, 5):
        assert len(retrieve_fake(QUERY_FULL_FOLDER, "flat", k)) <= k


def test_the_flat_arm_never_comes_back_empty():
    """As long as `CORPUS` holds something, `flat` always brings something.

    It matters for reading the results: if `n_chunks=0` shows up in the flat arm
    of a run, the failure is not the PARA filter's.
    """
    assert retrieve_fake(QUERY_EMPTY_FOLDER, "flat", 5) != []
    assert retrieve_fake(QUERY_FULL_FOLDER, "flat", 5) != []


def test_the_para_arm_can_come_back_empty():
    """D8: the filter leaves the folder empty and `[]` is returned. No falling
    back to flat.

    This is the test that gives the whole double its point. `agent/answer.py` has
    to handle zero chunks without breaking, and `harness.py` has to count those
    zeros: "PARA retrieves nothing in N% of cases" is a finding, not an error.
    """
    assert retrieve_fake(QUERY_EMPTY_FOLDER, "para", 5) == []


def test_the_para_arm_brings_only_one_folder():
    """The filter really filters: everything returned is from the same folder."""
    chunks = retrieve_fake(QUERY_FULL_FOLDER, "para", 8)
    assert chunks, "this query should land on a folder that has chunks"
    assert len({c.para_path for c in chunks}) == 1


def test_the_two_arms_do_not_return_the_same():
    """If `flat` and `para` agreed, the double would be testing nothing.

    The harness compares two arms; a double that made them identical would
    produce a difference of zero and look like a result.
    """
    flat = retrieve_fake(QUERY_FULL_FOLDER, "flat", 5)
    para = retrieve_fake(QUERY_FULL_FOLDER, "para", 5)
    assert [c.item_id for c in flat] != [c.item_id for c in para]


def test_the_similarity_formula_is_pinned():
    """Pins two concrete values so the formula cannot change without warning.

    If someone changes the hash, what gets hashed, or the byte order, the
    similarities move and old runs stop being comparable with new ones -- in
    silence. This test turns that change into a noisy failure.
    """
    flat = retrieve_fake(QUERY_FULL_FOLDER, "flat", 8)
    by_id = {c.item_id: c.similarity for c in flat}
    assert by_id["itm-01"] == pytest.approx(0.0826673626434058)
    assert by_id["itm-06"] == pytest.approx(0.36267701303586364)


def test_the_corpus_has_no_chunks_in_the_empty_folder():
    """`archive/2026` is in `PARA_PATHS` and has no chunks. On purpose.

    It is what makes the D8 case provokable without a special `if`, and it
    reproduces the shape of the real corpus: R7 measured 0 emails in `archive`.
    """
    assert "archive/2026" in PARA_PATHS
    assert not [c for c in CORPUS if c.para_path == "archive/2026"]


# --------------------------------------------------------------------------
# The two helpers, tested separately.
# Start here: if these two pass, `retrieve_fake` is just plumbing.
# --------------------------------------------------------------------------


def test_similarity_returns_the_pinned_values():
    """Pins the whole formula: what is hashed, how many bytes, what order, over what."""
    assert _similarity("which antivirus did I buy?", "itm-01") == pytest.approx(0.0826673626434058)
    assert _similarity("which antivirus did I buy?", "itm-06") == pytest.approx(0.36267701303586364)


def test_similarity_falls_in_zero_one():
    for item_id in ("itm-01", "itm-04", "itm-08"):
        s = _similarity("just some question", item_id)
        assert 0.0 <= s < 1.0


def test_similarity_changes_with_the_question():
    """If it did not, every question would see the same order and the double
    would be useless."""
    assert _similarity("question A", "itm-01") != _similarity("question B", "itm-01")


def test_target_folder_returns_the_pinned_folders():
    assert _target_folder(QUERY_EMPTY_FOLDER) == "archive/2026"
    assert _target_folder(QUERY_FULL_FOLDER) == "resources/newsletters"


def test_target_folder_is_always_one_of_PARA_PATHS():
    for q in ("a", "b", "c", "d", "e", "f", "g", "h"):
        assert _target_folder(q) in PARA_PATHS
