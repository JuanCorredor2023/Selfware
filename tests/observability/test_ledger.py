from selfware.core.schemas import TierCall
from selfware.observability.ledger import CallLedger, tier_of

NANO = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
ULTRA = "nvidia/Nemotron-3-Ultra-550b-a55b"


def call(model, tin, tout, latency, cost):
    return TierCall(
        model=model, tokens_in=tin, tokens_out=tout, latency_ms=latency, cost_usd=cost
    )


def test_tier_of_known_and_unknown_models():
    assert tier_of(NANO) == "nano"
    assert tier_of(ULTRA) == "ultra"
    assert tier_of("some/other-model") == "other"


def test_empty_ledger_summary_is_all_zeros():
    s = CallLedger().summary()
    assert s["total_usd"] == 0.0 and s["per_query_usd"] == 0.0
    assert s["avg_latency_ms"] == 0.0 and s["tiers"] == []


def test_summary_sums_and_averages():
    ledger = CallLedger()
    ledger.record_query(
        [call(NANO, 100, 10, 200.0, 0.001), call(ULTRA, 1000, 100, 1000.0, 0.009)]
    )
    ledger.record_query([call(ULTRA, 2000, 200, 1800.0, 0.011)])
    s = ledger.summary()
    assert round(s["total_usd"], 6) == 0.021
    assert s["query_count"] == 2 and s["call_count"] == 3
    assert round(s["per_query_usd"], 6) == 0.0105
    assert s["avg_latency_ms"] == 1000.0
    assert s["tokens_in"] == 3100 and s["tokens_out"] == 310


def test_unknown_models_are_grouped_as_other():
    ledger = CallLedger()
    ledger.record_query([call("mystery", 1, 1, 1.0, 0.5)])
    assert ledger.summary()["tiers"][0]["tier"] == "other"


def test_zero_total_cost_does_not_divide_by_zero():
    ledger = CallLedger()
    ledger.record_query([call(NANO, 1, 1, 1.0, 0.0)])
    assert ledger.summary()["tiers"][0]["cost_share"] == 0.0


def test_reset_clears_everything():
    ledger = CallLedger()
    ledger.record_query([call(NANO, 1, 1, 1.0, 0.1)])
    ledger.reset()
    assert ledger.summary()["call_count"] == 0
