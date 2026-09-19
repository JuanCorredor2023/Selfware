from core.schemas import TierCall
from observability.otel import record_tier_call, setup_tracing


def test_setup_tracing_is_idempotent():
    setup_tracing("test-service")
    setup_tracing("test-service")  # no debe truenar ni duplicar nada


def test_record_tier_call_does_not_raise():
    tc = TierCall(
        model="mock/no-model",
        tokens_in=10,
        tokens_out=5,
        latency_ms=42.0,
        cost_usd=0.0,
    )
    record_tier_call(tc)
