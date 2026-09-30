"""Tests for `cache.py`. None of them touches the network or spends budget.

`tmp_path` is a temporary folder pytest creates **fresh for each test** and
deletes afterwards. It is a `pathlib.Path`, the same type `load()` and `save()`
receive. Asking for it is as simple as naming it as a parameter: pytest injects
it when it sees the name.
"""

from selfware.agent.cache import cache_key, load, save

# Throwaway fixture. Unlike the real prompt in `answer.py`, nothing is coupled to
# this text: the tests only compare keys against each other, so its wording is
# free.
PROMPT = (
    "Answer using only the given chunks.\n\n"
    "[1] The subscription is charged on the 14th.\n\n"
    "Question: which day of the month is it charged?"
)
MODEL = "nvidia/Nemotron-3-Ultra-550b-a55b"
PARAMS = {"temperature": 0, "max_tokens": 2000, "logprobs": True, "top_logprobs": 5}


# --------------------------------------------------------------------------
# cache_key
# --------------------------------------------------------------------------


def test_the_key_is_stable():
    """Same in, same out. Without this there is no cache at all."""
    assert cache_key(PROMPT, MODEL, PARAMS) == cache_key(PROMPT, MODEL, PARAMS)


def test_the_key_works_as_a_filename():
    key = cache_key(PROMPT, MODEL, PARAMS)
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)


def test_the_order_of_params_does_not_change_the_key():
    """The same pairs in a different order are the SAME configuration.
    If this fails, the cache hits or misses depending on how somebody typed the
    dictionary."""
    a = {"temperature": 0, "max_tokens": 2000}
    b = {"max_tokens": 2000, "temperature": 0}
    assert cache_key(PROMPT, MODEL, a) == cache_key(PROMPT, MODEL, b)


def test_changing_the_prompt_changes_the_key():
    """Even a trailing space. The key derives from the exact content being sent."""
    assert cache_key(PROMPT, MODEL, PARAMS) != cache_key(PROMPT + " ", MODEL, PARAMS)


def test_changing_the_model_changes_the_key():
    """D12: the judge is a different model. If the model did not enter the key,
    the generator's answers would be served as if the judge had given them."""
    judge = "Qwen/Qwen3-235B-A22B-Instruct-2507"  # D12/R2, chosen 20 Sep
    assert cache_key(PROMPT, MODEL, PARAMS) != cache_key(PROMPT, judge, PARAMS)


def test_changing_one_parameter_changes_the_key():
    others = dict(PARAMS)  # a copy: `others = PARAMS` would share the dictionary
    others["temperature"] = 0.7
    assert cache_key(PROMPT, MODEL, PARAMS) != cache_key(PROMPT, MODEL, others)


# --------------------------------------------------------------------------
# load / save
# --------------------------------------------------------------------------


def test_load_returns_none_when_there_is_nothing(tmp_path):
    """An empty cache is not an error: it means "the API has to be called"."""
    assert load(tmp_path, "akeythatdoesnotexist") is None


def test_saving_and_reading_returns_the_same(tmp_path):
    payload = {
        "text": "11",
        "finish_reason": "stop",
        "usage": {"completion_tokens": 60, "reasoning_tokens": 56},
        "strategy": "para",
        "question_id": "sd-001",
    }
    key = cache_key(PROMPT, MODEL, PARAMS)
    save(tmp_path, key, payload)
    assert load(tmp_path, key) == payload


def test_save_creates_the_folder_if_it_does_not_exist(tmp_path):
    target = tmp_path / "cache" / "ultra"
    save(target, "abc123", {"x": 1})
    assert load(target, "abc123") == {"x": 1}


def test_two_keys_do_not_overwrite_each_other(tmp_path):
    save(tmp_path, "key_a", {"which": "a"})
    save(tmp_path, "key_b", {"which": "b"})
    assert load(tmp_path, "key_a") == {"which": "a"}
    assert load(tmp_path, "key_b") == {"which": "b"}


def test_saving_the_same_key_twice_overwrites(tmp_path):
    save(tmp_path, "key", {"v": 1})
    save(tmp_path, "key", {"v": 2})
    assert load(tmp_path, "key") == {"v": 2}


def test_each_entry_is_an_independent_file(tmp_path):
    """Corollary of D16: the harness must be interruptible without losing work.
    With one file per entry, a Ctrl-C keeps everything that already finished."""
    save(tmp_path, "a", {"x": 1})
    save(tmp_path, "b", {"x": 2})
    assert len(list(tmp_path.glob("*.json"))) == 2
