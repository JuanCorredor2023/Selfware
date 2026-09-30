"""On-disk cache of model responses (D16).

The budget is ~$50 per person and the evaluation is going to be run ten or
fifteen times while it is being debugged. Without a cache, every run pays again
for answers identical to the previous run's -- and a harness you have to run in
full every time is a harness that will not get run.

Key design:

    key = sha256( final prompt + model + sampling parameters )

The **final** prompt is hashed, not its ingredients. By D15 the prompt is
already `[instructions] -> [chunks] -> [question]`, which means it contains the
question, the retrieved chunks and the instructions, all together. Hashing
literally what gets sent makes it impossible to forget a field.

What does **not** go in the key: the strategy (`flat` / `para`), the question
id, and any other experiment metadata. If both arms produce the same prompt, the
answer is the same and they should share the entry: you pay once. Metadata is
stored *next to* the result, not inside the key.

The asymmetry that settles the doubts:

    A key that is too WIDE costs money, and you see it on tomorrow's bill.
    A key that is too NARROW serves old answers for a new configuration, in
    silence, and contaminates the number.

When in doubt, put the field in.

On-disk format: one JSON file per entry, named after the key. Each entry is
independent, so an interrupted run keeps everything that had already finished --
the corollary of D16.
"""

import hashlib
import json
from pathlib import Path


def cache_key(prompt: str, model: str, params: dict) -> str:
    """Derive the cache key for one call.

    Args:
        prompt: the final text about to be sent, complete.
        model: model identifier, e.g. `nvidia/Nemotron-3-Ultra-550b-a55b`. It
            goes separately from `params` on purpose: D12 requires the judge to
            be a different model from the generator, and if the model fell out
            of the key, the generator's answers would be served as if they were
            the judge's. That is the most expensive silent error possible here.
        params: the sampling parameters that **affect the response** --
            `temperature`, `max_tokens`, `logprobs`, `top_logprobs`. Only what
            changes the output: a network `timeout` does not go in, because it
            does not change it.

    Returns:
        The SHA-256 digest in hexadecimal: 64 characters, only `0-9` and `a-f`.
        It is used directly as a filename, so it cannot carry `/` or spaces.

    Note on `params`, and this is the trap of this function: two dictionaries
    with the same pairs in a different order have to produce the **same** key. A
    Python dictionary preserves the order the keys were written in, so turning
    it into text as is would give different hashes for identical
    configurations. A **canonical order** has to be imposed before hashing.
    Otherwise the cache fails intermittently depending on how somebody typed the
    dictionary, and that is about as hard to debug as it gets.
    """

    material = {"prompt": prompt, "model": model, "params": params}

    canonical = json.dumps(material, sort_keys=True)

    key = hashlib.sha256(canonical.encode()).hexdigest()

    return key


def _cache_path(cache_dir: Path, key: str) -> Path:
    """Return the final Path joining the folder and the json file.

    This keeps `load` and `save` from ever disagreeing about the name.
    """
    return cache_dir / f"{key}.json"


def load(cache_dir: Path, key: str) -> dict | None:
    """Read one cache entry.

    Args:
        cache_dir: folder where the cache lives.
        key: the key returned by `cache_key()`.

    Returns:
        The dictionary that was stored, or `None` if there is nothing for that
        key. `None` is not an error: it is the normal case the first time a
        question is run, and it is the signal that the API has to be called.
    """

    load_path = _cache_path(cache_dir, key)

    if load_path.exists():
        raw = load_path.read_text(encoding="utf-8")
        entry = json.loads(raw)
        return entry
    return None


def save(cache_dir: Path, key: str, payload: dict) -> None:
    """Store one cache entry.

    Creates `cache_dir` if it does not exist. If the key was already there, it
    is overwritten.

    `load()` and `save()` have to agree on how the filename is built from the
    key. Since that rule lives on both sides, it is better for it to exist in
    exactly one place.

    Args:
        cache_dir: folder where the cache lives.
        key: the key returned by `cache_key()`.
        payload: whatever you want to store. This module neither knows nor cares
            what is inside -- the answer, `usage`, `finish_reason` (D17), the
            strategy, the question id. All of that is experiment metadata and it
            is only passing through here. Single requirement: it must be JSON
            serializable.
    """

    cache_dir.mkdir(parents=True, exist_ok=True)

    save_path = _cache_path(cache_dir, key)

    serialized = json.dumps(payload, sort_keys=True)

    save_path.write_text(serialized, encoding="utf-8")
