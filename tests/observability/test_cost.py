from selfware.observability import cost as cost_module
from selfware.observability.cost import estimate_cost_usd, is_priced


def test_estimate_cost_unknown_model_is_zero():
    assert estimate_cost_usd("unknown-model", 1000, 1000) == 0.0


def test_estimate_cost_nano_matches_price_list():
    # 1M in @ $0.06 + 1M out @ $0.24 = $0.30 (eu-north1, valid from 01 Jan 2026)
    cost = estimate_cost_usd(
        "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", 1_000_000, 1_000_000
    )
    assert round(cost, 6) == 0.30


def test_estimate_cost_ultra_matches_price_list():
    # 1M in @ $1.00 + 1M out @ $3.00 = $4.00 (eu-north1, valid from 01 Jun 2026)
    cost = estimate_cost_usd("nvidia/Nemotron-3-Ultra-550b-a55b", 1_000_000, 1_000_000)
    assert round(cost, 6) == 4.00


def test_estimate_cost_model_id_casing_must_match_exactly():
    # Regression guard: core.llm.MODEL_IDS uses this exact casing. A
    # lowercased or otherwise mismatched key here would silently price
    # every real call at $0.0 instead of raising -- this test would catch
    # that the moment someone "cleans up" the casing in one file only.
    cost = estimate_cost_usd(
        "nvidia/nvidia-nemotron-3-nano-30b-a3b", 1_000_000, 1_000_000
    )
    assert cost == 0.0


def test_estimate_cost_judge_matches_the_model_catalog():
    # 1M in @ $0.20 + 1M out @ $0.60 = $0.80 (Token Factory model catalog)
    cost = estimate_cost_usd("Qwen/Qwen3-235B-A22B-Instruct-2507", 1_000_000, 1_000_000)
    assert round(cost, 6) == 0.80


def test_every_model_id_in_core_llm_has_a_price():
    # If someone adds a tier to core.llm.MODEL_IDS without pricing it, its
    # calls would silently cost $0.00 (integration_p3.md, B5).
    from selfware.core.llm import MODEL_IDS

    for tier, model_id in MODEL_IDS.items():
        assert is_priced(model_id), f"tier {tier!r} ({model_id}) has no price"


def test_unknown_model_logs_a_warning_once(caplog):
    cost_module._warned_models.discard("mystery/model")
    with caplog.at_level("WARNING", logger="selfware.observability.cost"):
        estimate_cost_usd("mystery/model", 10, 10)
        estimate_cost_usd("mystery/model", 10, 10)
    warnings = [r for r in caplog.records if "mystery/model" in r.getMessage()]
    assert len(warnings) == 1
    assert "understated" in warnings[0].getMessage()


def test_known_models_do_not_warn(caplog):
    with caplog.at_level("WARNING", logger="selfware.observability.cost"):
        estimate_cost_usd("nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", 10, 10)
    assert caplog.records == []
