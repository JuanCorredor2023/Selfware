from selfware.context import classifier as classifier_module
from selfware.context.classifier import Classifier
from selfware.context.domain import ParaFolder
from selfware.core.schemas import TierCall


def test_classifier_reports_its_tier_call_to_the_hook(monkeypatch):
    tier_call = TierCall(
        model="m", tokens_in=3, tokens_out=1, latency_ms=1.0, cost_usd=0.0
    )
    monkeypatch.setattr(classifier_module, "call", lambda *a, **k: ("areas", tier_call))
    seen = []

    result = Classifier(on_tier_call=seen.append).classify_query("my gym plan")

    assert result == ParaFolder.AREAS
    assert seen == [tier_call]


def test_classifier_without_a_hook_still_works(monkeypatch):
    tier_call = TierCall(
        model="m", tokens_in=3, tokens_out=1, latency_ms=1.0, cost_usd=0.0
    )
    monkeypatch.setattr(
        classifier_module, "call", lambda *a, **k: ("projects", tier_call)
    )

    assert Classifier().classify_document("hello") == ParaFolder.PROJECTS
