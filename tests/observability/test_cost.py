from selfware.observability.cost import estimate_cost_usd


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
